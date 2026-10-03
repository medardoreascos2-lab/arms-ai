"""R40B containerless tests for the PostgreSQL adapter foundation."""

from datetime import datetime, timedelta, timezone

import pytest

from backend.phase4 import (
    DatabaseAccessMode,
    DatabaseAdapterRegistry,
    DatabaseAvailability,
    DatabaseBackend,
    DatabaseError,
    DatabaseReadOnlyError,
    DatabaseTarget,
    DatabaseTenantIsolationError,
)
from backend.phase4.postgresql_adapter import (
    POSTGRES_TABLES,
    PostgresDatabaseAdapter,
    PostgresDocument,
    PostgresRecordKind,
)


OCCURRED = datetime(2026, 10, 3, 16, 0, tzinfo=timezone.utc)
STORED = OCCURRED + timedelta(seconds=1)


class FakeCursor:
    def __init__(self, connection):
        self.connection = connection
        self.rowcount = -1
        self.result = None
        self.closed = False

    def execute(self, query, parameters=()):
        self.connection.queries.append((query, parameters))
        if self.connection.fail_query and self.connection.fail_query in query:
            raise RuntimeError("fake credential must never escape")
        if query.startswith("SELECT schema_version"):
            self.result = (self.connection.schema_version,)
            self.rowcount = 1
            return self
        if query.startswith("INSERT INTO "):
            table = query.split()[2]
            tenant_id, record_id, payload, payload_hash, occurred_at, stored_at = parameters
            key = (table, tenant_id, record_id)
            if key in self.connection.rows:
                self.rowcount = 0
            else:
                self.connection.pending[key] = (
                    payload,
                    payload_hash,
                    occurred_at,
                    stored_at,
                )
                self.rowcount = 1
            self.result = None
            return self
        if query.startswith("SELECT payload_sha256"):
            table = query.split("FROM ", 1)[1].split()[0]
            key = (table, parameters[0], parameters[1])
            row = self.connection.pending.get(key) or self.connection.rows.get(key)
            self.result = None if row is None else (row[1],)
            self.rowcount = 0 if row is None else 1
            return self
        if query.startswith("SELECT payload,"):
            table = query.split("FROM ", 1)[1].split()[0]
            key = (table, parameters[0], parameters[1])
            self.result = self.connection.rows.get(key)
            self.rowcount = 0 if self.result is None else 1
            return self
        raise AssertionError(f"unexpected query: {query}")

    def fetchone(self):
        return self.result

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, *, schema_version=1, fail_query=None):
        self.schema_version = schema_version
        self.fail_query = fail_query
        self.queries = []
        self.rows = {}
        self.pending = {}
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.rows.update(self.pending)
        self.pending.clear()
        self.commits += 1

    def rollback(self):
        self.pending.clear()
        self.rollbacks += 1

    def close(self):
        self.closed = True


def _target(mode=DatabaseAccessMode.READ_WRITE):
    return DatabaseTarget(
        backend=DatabaseBackend.POSTGRESQL,
        database_name="arms_phase4",
        access_mode=mode,
        connection_reference="secrets/arms/staging/postgres",
    )


def _document(kind, tenant_id="tenant-a", record_id="record-1", payload=b'{"ok":true}'):
    return PostgresDocument(
        tenant_id=tenant_id,
        record_id=record_id,
        kind=kind,
        payload=payload,
        occurred_at=OCCURRED,
    )


def test_adapter_uses_opaque_reference_and_reports_sanitized_health():
    raw = FakeConnection()
    calls = []

    def factory(reference, mode):
        calls.append((reference, mode))
        return raw

    checked = datetime(2026, 10, 3, 16, 1, tzinfo=timezone.utc)
    adapter = PostgresDatabaseAdapter(factory, clock=lambda: checked)
    with adapter.connect(_target()) as connection:
        health = connection.health()
        assert calls == [("secrets/arms/staging/postgres", DatabaseAccessMode.READ_WRITE)]
        assert health.availability is DatabaseAvailability.AVAILABLE
        assert health.detail_code == "postgresql_available"
        assert health.checked_at == checked
        assert health.schema_version == 1
        assert connection.execution_authorized is False
        assert connection.production_mutation_authorized is False
    assert raw.closed is True


@pytest.mark.parametrize("kind", tuple(PostgresRecordKind))
def test_all_required_record_types_round_trip_with_parameterized_tenant_scope(kind):
    raw = FakeConnection()
    connection = PostgresDatabaseAdapter(lambda *_: raw).connect(_target())
    document = _document(kind, record_id=f"record-{kind.value.lower()}")
    result = connection.tenant("tenant-a").append(document, stored_at=STORED)
    restored = connection.tenant("tenant-a").get(
        kind=kind,
        record_id=document.record_id,
    )
    assert result.inserted is True
    assert result.duplicate is False
    assert restored is not None
    assert restored.document == document
    assert restored.stored_at == STORED
    insert_query, insert_parameters = next(
        item for item in raw.queries if item[0].startswith("INSERT INTO")
    )
    assert "%s" in insert_query
    assert "tenant-a" not in insert_query
    assert insert_parameters[0:2] == ("tenant-a", document.record_id)
    assert kind.table_name in POSTGRES_TABLES


def test_duplicate_is_idempotent_and_conflicting_payload_fails_closed():
    raw = FakeConnection()
    repository = PostgresDatabaseAdapter(lambda *_: raw).connect(_target()).tenant(
        "tenant-a"
    )
    document = _document(PostgresRecordKind.SNAPSHOT)
    first = repository.append(document, stored_at=STORED)
    second = repository.append(document, stored_at=STORED)
    assert first.inserted is True
    assert second.duplicate is True
    with pytest.raises(DatabaseError, match="immutable record conflict"):
        repository.append(
            _document(PostgresRecordKind.SNAPSHOT, payload=b'{"ok":false}'),
            stored_at=STORED,
        )
    assert raw.rollbacks >= 1


def test_tenant_scope_blocks_cross_tenant_write_and_read():
    raw = FakeConnection()
    connection = PostgresDatabaseAdapter(lambda *_: raw).connect(_target())
    tenant_a = connection.tenant("tenant-a")
    tenant_b = connection.tenant("tenant-b")
    document = _document(PostgresRecordKind.EVALUATION)
    tenant_a.append(document, stored_at=STORED)
    with pytest.raises(DatabaseTenantIsolationError, match="does not match"):
        tenant_b.append(document, stored_at=STORED)
    assert tenant_b.get(kind=document.kind, record_id=document.record_id) is None
    assert tenant_a.get(kind=document.kind, record_id=document.record_id) is not None


def test_read_only_connection_rejects_writes_before_cursor_use():
    raw = FakeConnection()
    connection = PostgresDatabaseAdapter(lambda *_: raw).connect(
        _target(DatabaseAccessMode.READ_ONLY)
    )
    before = len(raw.queries)
    with pytest.raises(DatabaseReadOnlyError, match="read-only"):
        connection.tenant("tenant-a").append(
            _document(PostgresRecordKind.AUDIT),
            stored_at=STORED,
        )
    assert len(raw.queries) == before
    assert connection.health().read_only is True
    assert connection.health().detail_code == "postgresql_read_only"


def test_transaction_failure_rolls_back_and_sanitizes_driver_error():
    raw = FakeConnection(fail_query="INSERT INTO phase4_outbox")
    repository = PostgresDatabaseAdapter(lambda *_: raw).connect(_target()).tenant(
        "tenant-a"
    )
    with pytest.raises(DatabaseError, match="transaction failed") as error:
        repository.append(
            _document(PostgresRecordKind.OUTBOX),
            stored_at=STORED,
        )
    assert "credential" not in str(error.value)
    assert raw.rollbacks >= 1
    assert raw.rows == {}


def test_schema_mismatch_and_connection_failure_are_fail_closed():
    stale = FakeConnection(schema_version=2)
    with pytest.raises(DatabaseError, match="failed health validation"):
        PostgresDatabaseAdapter(lambda *_: stale).connect(_target())
    assert stale.closed is True

    def unavailable(*_):
        raise RuntimeError("host includes sensitive diagnostic")

    with pytest.raises(DatabaseError, match="connection unavailable") as error:
        PostgresDatabaseAdapter(unavailable).connect(_target())
    assert "sensitive" not in str(error.value)


def test_registry_accepts_postgresql_adapter_without_driver_dependency():
    raw = FakeConnection()
    registry = DatabaseAdapterRegistry((PostgresDatabaseAdapter(lambda *_: raw),))
    with registry.connect(_target()) as connection:
        assert connection.backend is DatabaseBackend.POSTGRESQL
        assert connection.schema_version == 1
