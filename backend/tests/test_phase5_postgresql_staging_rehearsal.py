"""R51B static PostgreSQL rehearsal while no isolated server is available.

These tests exercise the PostgreSQL DB-API boundary and generated SQL with
in-memory driver doubles. They are not evidence of a real PostgreSQL runtime.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json

from backend.phase3.financial_serialization import canonical_decimal_text
from backend.phase4 import DatabaseAccessMode, DatabaseBackend, DatabaseTarget
from backend.phase4.postgresql_adapter import (
    PostgresDatabaseAdapter,
    PostgresDocument,
    PostgresRecordKind,
)
from backend.phase4.production_migrations import (
    POSTGRES_MIGRATIONS,
    POSTGRES_SCHEMA_CHECKSUM,
    POSTGRES_SCHEMA_VERSION,
    ProductionMigrationRunner,
)


RUNTIME_STATUS = "BLOCKED_LOCAL_RUNTIME"
NOW = datetime(2026, 10, 3, 21, 0, tzinfo=timezone.utc)


class StaticMigrationCursor:
    def __init__(self, connection):
        self.connection = connection
        self.result = None
        self.results = []

    def execute(self, query, parameters=()):
        self.connection.queries.append((query, parameters))
        if query.startswith("SELECT pg_advisory_xact_lock"):
            self.result = (None,)
        elif query.startswith("SELECT to_regclass"):
            self.result = (None,)
        elif query.startswith(("CREATE TABLE ", "CREATE INDEX ", "ALTER TABLE ")):
            self.connection.pending_ddl.append(query)
        elif query.startswith("INSERT INTO phase4_schema_migrations"):
            self.connection.pending_history.append(tuple(parameters))
        elif query.startswith("INSERT INTO phase4_store_metadata"):
            self.connection.pending_metadata = tuple(parameters)
        else:
            raise AssertionError(f"unexpected migration query: {query}")
        return self

    def fetchone(self):
        return self.result

    def fetchall(self):
        return list(self.results)

    def close(self):
        return None


class StaticMigrationConnection:
    autocommit = False

    def __init__(self):
        self.queries = []
        self.pending_ddl = []
        self.pending_history = []
        self.pending_metadata = None
        self.applied_ddl = []
        self.history = []
        self.metadata = None
        self.commits = 0
        self.rollbacks = 0

    def cursor(self):
        return StaticMigrationCursor(self)

    def commit(self):
        self.applied_ddl.extend(self.pending_ddl)
        self.history.extend(self.pending_history)
        self.metadata = self.pending_metadata
        self.pending_ddl = []
        self.pending_history = []
        self.pending_metadata = None
        self.commits += 1

    def rollback(self):
        self.pending_ddl = []
        self.pending_history = []
        self.pending_metadata = None
        self.rollbacks += 1


class StaticStoreCursor:
    def __init__(self, connection):
        self.connection = connection
        self.rowcount = -1
        self.result = None

    def execute(self, query, parameters=()):
        self.connection.queries.append((query, parameters))
        if query.startswith("SELECT schema_version"):
            self.result = (POSTGRES_SCHEMA_VERSION,)
            self.rowcount = 1
        elif query.startswith("INSERT INTO "):
            table = query.split()[2]
            key = (table, parameters[0], parameters[1])
            if key in self.connection.rows:
                self.rowcount = 0
            else:
                self.connection.pending[key] = tuple(parameters[2:])
                self.rowcount = 1
            self.result = None
        elif query.startswith("SELECT payload_sha256"):
            table = query.split("FROM ", 1)[1].split()[0]
            key = (table, parameters[0], parameters[1])
            row = self.connection.pending.get(key) or self.connection.rows.get(key)
            self.result = None if row is None else (row[1],)
            self.rowcount = 0 if row is None else 1
        elif query.startswith("SELECT payload,"):
            table = query.split("FROM ", 1)[1].split()[0]
            key = (table, parameters[0], parameters[1])
            self.result = self.connection.rows.get(key)
            self.rowcount = 0 if self.result is None else 1
        else:
            raise AssertionError(f"unexpected store query: {query}")
        return self

    def fetchone(self):
        return self.result

    def close(self):
        return None


class StaticStoreConnection:
    def __init__(self):
        self.queries = []
        self.rows = {}
        self.pending = {}
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def cursor(self):
        return StaticStoreCursor(self)

    def commit(self):
        self.rows.update(self.pending)
        self.pending.clear()
        self.commits += 1

    def rollback(self):
        self.pending.clear()
        self.rollbacks += 1

    def close(self):
        self.closed = True


def _target():
    return DatabaseTarget(
        backend=DatabaseBackend.POSTGRESQL,
        database_name="arms_phase5",
        access_mode=DatabaseAccessMode.READ_WRITE,
        connection_reference="secrets/arms/staging/postgres",
    )


def test_static_rehearsal_is_explicitly_blocked_from_claiming_runtime_evidence():
    assert RUNTIME_STATUS == "BLOCKED_LOCAL_RUNTIME"


def test_static_schema_migration_covers_every_required_staging_record_table():
    raw = StaticMigrationConnection()
    result = ProductionMigrationRunner(raw).apply(POSTGRES_MIGRATIONS, applied_at=NOW)

    assert result.applied_versions == (1,)
    assert result.to_version == POSTGRES_SCHEMA_VERSION
    assert result.execution_authorized is False
    assert result.production_mutation_authorized is False
    assert raw.commits == 1
    assert raw.rollbacks == 0
    assert raw.metadata[:2] == (POSTGRES_SCHEMA_VERSION, POSTGRES_SCHEMA_CHECKSUM)
    applied = "\n".join(raw.applied_ddl)
    for kind in PostgresRecordKind:
        assert f"CREATE TABLE {kind.table_name} " in applied


def test_static_snapshot_evaluation_audit_outbox_and_research_metadata_persist():
    raw = StaticStoreConnection()
    connection = PostgresDatabaseAdapter(lambda *_: raw).connect(_target())
    repository = connection.tenant("tenant-staging")

    for index, kind in enumerate(PostgresRecordKind):
        document = PostgresDocument(
            tenant_id="tenant-staging",
            record_id=f"rehearsal-{kind.value.lower()}",
            kind=kind,
            payload=json.dumps(
                {"kind": kind.value, "simulated": True},
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8"),
            occurred_at=NOW + timedelta(seconds=index),
        )
        result = repository.append(
            document,
            stored_at=NOW + timedelta(minutes=1, seconds=index),
        )
        restored = repository.get(kind=kind, record_id=document.record_id)

        assert result.inserted is True
        assert restored is not None
        assert restored.document == document
        assert restored.document.payload_sha256 == document.payload_sha256
        assert restored.document.execution_authorized is False
        assert restored.document.production_mutation_authorized is False

    assert raw.commits == len(PostgresRecordKind)
    assert len(raw.rows) == len(PostgresRecordKind)


def test_static_postgresql_payload_preserves_extreme_decimal_exactly():
    value = Decimal("123456789012345678901234567890.000000000000000000123456789")
    canonical = canonical_decimal_text(value)
    payload = json.dumps(
        {"unit": "USD", "value": canonical},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    document = PostgresDocument(
        tenant_id="tenant-staging",
        record_id="rehearsal-exact-decimal",
        kind=PostgresRecordKind.SNAPSHOT,
        payload=payload,
        occurred_at=NOW,
    )
    raw = StaticStoreConnection()
    repository = PostgresDatabaseAdapter(lambda *_: raw).connect(_target()).tenant(
        "tenant-staging"
    )

    repository.append(document, stored_at=NOW + timedelta(minutes=1))
    restored = repository.get(kind=document.kind, record_id=document.record_id)

    assert restored is not None
    assert restored.document.payload == payload
    decoded = json.loads(restored.document.payload.decode("utf-8"))
    assert decoded["value"] == canonical
    assert Decimal(decoded["value"]) == value
    assert canonical_decimal_text(Decimal(decoded["value"])) == canonical
