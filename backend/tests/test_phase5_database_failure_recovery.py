"""R51C fail-closed database recovery tests using PostgreSQL driver doubles.

No local PostgreSQL runtime is available. These tests validate the application
boundary and transaction semantics without claiming server-level recovery.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import RLock

import pytest

from backend.phase4 import (
    DatabaseAccessMode,
    DatabaseError,
    DatabaseReadOnlyError,
    DatabaseTarget,
    DatabaseBackend,
)
from backend.phase4.postgresql_adapter import (
    PostgresDatabaseAdapter,
    PostgresDocument,
    PostgresRecordKind,
)
from backend.phase4.production_migrations import (
    POSTGRES_MIGRATIONS,
    ProductionMigrationApplyError,
    ProductionMigrationRunner,
)


NOW = datetime(2026, 10, 3, 22, 0, tzinfo=timezone.utc)


class SharedStore:
    def __init__(self):
        self.rows = {}
        self.lock = RLock()
        self.committed_writes = 0


class RecoverableCursor:
    def __init__(self, connection):
        self.connection = connection
        self.rowcount = -1
        self.result = None

    def execute(self, query, parameters=()):
        if self.connection.closed:
            raise ConnectionError("connection is closed")
        self.connection.queries.append((query, parameters))
        if query.startswith("SELECT schema_version"):
            self.result = (1,)
            self.rowcount = 1
            return self
        if query.startswith("INSERT INTO "):
            if self.connection.fail_operation == "insert":
                raise ConnectionError("synthetic database connection lost")
            table = query.split()[2]
            key = (table, parameters[0], parameters[1])
            with self.connection.store.lock:
                exists = key in self.connection.store.rows
            if exists or key in self.connection.pending:
                self.rowcount = 0
            else:
                self.connection.pending[key] = tuple(parameters[2:])
                self.rowcount = 1
            self.result = None
            return self
        if query.startswith("SELECT payload_sha256"):
            if self.connection.fail_operation == "hash":
                raise RuntimeError("synthetic transaction aborted")
            table = query.split("FROM ", 1)[1].split()[0]
            key = (table, parameters[0], parameters[1])
            with self.connection.store.lock:
                row = self.connection.pending.get(key) or self.connection.store.rows.get(
                    key
                )
            self.result = None if row is None else (row[1],)
            self.rowcount = 0 if row is None else 1
            return self
        if query.startswith("SELECT payload,"):
            table = query.split("FROM ", 1)[1].split()[0]
            key = (table, parameters[0], parameters[1])
            with self.connection.store.lock:
                self.result = self.connection.store.rows.get(key)
            self.rowcount = 0 if self.result is None else 1
            return self
        raise AssertionError(f"unexpected store query: {query}")

    def fetchone(self):
        return self.result

    def close(self):
        return None


class RecoverableConnection:
    def __init__(self, store, *, fail_operation=None):
        self.store = store
        self.fail_operation = fail_operation
        self.pending = {}
        self.queries = []
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def cursor(self):
        return RecoverableCursor(self)

    def commit(self):
        if self.fail_operation == "commit":
            raise RuntimeError("synthetic commit abort")
        with self.store.lock:
            self.store.rows.update(self.pending)
            self.store.committed_writes += len(self.pending)
        self.pending.clear()
        self.commits += 1

    def rollback(self):
        self.pending.clear()
        self.rollbacks += 1

    def close(self):
        self.closed = True


class InterruptedMigrationCursor:
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
        elif "CREATE TABLE phase4_outbox" in query:
            raise ConnectionError("synthetic migration interruption")
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


class InterruptedMigrationConnection:
    autocommit = False

    def __init__(self):
        self.queries = []
        self.pending_ddl = []
        self.pending_history = []
        self.pending_metadata = None
        self.applied_ddl = []
        self.commits = 0
        self.rollbacks = 0

    def cursor(self):
        return InterruptedMigrationCursor(self)

    def commit(self):
        self.applied_ddl.extend(self.pending_ddl)
        self.pending_ddl = []
        self.pending_history = []
        self.pending_metadata = None
        self.commits += 1

    def rollback(self):
        self.pending_ddl = []
        self.pending_history = []
        self.pending_metadata = None
        self.rollbacks += 1


def _target(mode=DatabaseAccessMode.READ_WRITE):
    return DatabaseTarget(
        backend=DatabaseBackend.POSTGRESQL,
        database_name="arms_phase5",
        access_mode=mode,
        connection_reference="secrets/arms/staging/postgres",
    )


def _document(tenant_id, record_id, *, kind=PostgresRecordKind.SNAPSHOT):
    return PostgresDocument(
        tenant_id=tenant_id,
        record_id=record_id,
        kind=kind,
        payload=f'{{"record":"{record_id}","simulated":true}}'.encode("utf-8"),
        occurred_at=NOW,
    )


@pytest.mark.parametrize("failure", ("insert", "hash", "commit"))
def test_connection_or_transaction_failure_rolls_back_without_durable_write(failure):
    store = SharedStore()
    raw = RecoverableConnection(store, fail_operation=failure)
    repository = PostgresDatabaseAdapter(lambda *_: raw).connect(_target()).tenant(
        "tenant-a"
    )

    with pytest.raises(DatabaseError, match="transaction failed"):
        repository.append(
            _document("tenant-a", f"failed-{failure}"),
            stored_at=NOW + timedelta(seconds=1),
        )

    assert raw.rollbacks >= 1
    assert raw.pending == {}
    assert raw.commits == 0
    assert store.rows == {}
    assert store.committed_writes == 0


def test_unavailable_connection_fails_closed_without_fallback_or_state():
    store = SharedStore()
    calls = 0

    def unavailable(*_):
        nonlocal calls
        calls += 1
        raise ConnectionError("postgres://user:password@private-host unavailable")

    with pytest.raises(DatabaseError, match="connection unavailable") as error:
        PostgresDatabaseAdapter(unavailable).connect(_target())

    assert calls == 1
    assert "password" not in str(error.value)
    assert store.rows == {}
    assert store.committed_writes == 0


def test_interrupted_migration_rolls_back_schema_history_and_metadata():
    raw = InterruptedMigrationConnection()

    with pytest.raises(ProductionMigrationApplyError, match="transaction failed"):
        ProductionMigrationRunner(raw).apply(POSTGRES_MIGRATIONS, applied_at=NOW)

    assert raw.commits == 0
    assert raw.rollbacks == 1
    assert raw.applied_ddl == []
    assert raw.pending_ddl == []
    assert raw.pending_history == []
    assert raw.pending_metadata is None


def test_read_only_mode_rejects_write_before_any_insert():
    store = SharedStore()
    raw = RecoverableConnection(store)
    connection = PostgresDatabaseAdapter(lambda *_: raw).connect(
        _target(DatabaseAccessMode.READ_ONLY)
    )
    before = tuple(raw.queries)

    with pytest.raises(DatabaseReadOnlyError, match="read-only"):
        connection.tenant("tenant-a").append(
            _document("tenant-a", "read-only-rejected"),
            stored_at=NOW + timedelta(seconds=1),
        )

    assert tuple(raw.queries) == before
    assert not any(query.startswith("INSERT INTO ") for query, _ in raw.queries)
    assert store.rows == {}


def test_restart_reopens_shared_state_without_replaying_write():
    store = SharedStore()
    first_raw = RecoverableConnection(store)
    first = PostgresDatabaseAdapter(lambda *_: first_raw).connect(_target())
    document = _document("tenant-a", "restart-record")
    first.tenant("tenant-a").append(
        document,
        stored_at=NOW + timedelta(seconds=1),
    )
    first.close()

    restarted_raw = RecoverableConnection(store)
    restarted = PostgresDatabaseAdapter(lambda *_: restarted_raw).connect(_target())
    restored = restarted.tenant("tenant-a").get(
        kind=document.kind,
        record_id=document.record_id,
    )

    assert first_raw.closed is True
    assert restored is not None
    assert restored.document == document
    assert store.committed_writes == 1
    assert restarted.execution_authorized is False
    assert restarted.production_mutation_authorized is False


def test_duplicate_request_is_idempotent_after_restart():
    store = SharedStore()
    document = _document("tenant-a", "duplicate-record")
    first = PostgresDatabaseAdapter(
        lambda *_: RecoverableConnection(store)
    ).connect(_target())
    first_result = first.tenant("tenant-a").append(
        document,
        stored_at=NOW + timedelta(seconds=1),
    )
    first.close()

    second = PostgresDatabaseAdapter(
        lambda *_: RecoverableConnection(store)
    ).connect(_target())
    duplicate = second.tenant("tenant-a").append(
        document,
        stored_at=NOW + timedelta(seconds=1),
    )

    assert first_result.inserted is True
    assert duplicate.duplicate is True
    assert store.committed_writes == 1
    assert len(store.rows) == 1


def test_concurrent_tenant_workload_stays_isolated_and_complete():
    store = SharedStore()
    tenants = tuple(f"tenant-{index}" for index in range(8))
    records_per_tenant = 12

    def write_tenant(tenant_id):
        raw = RecoverableConnection(store)
        connection = PostgresDatabaseAdapter(lambda *_: raw).connect(_target())
        repository = connection.tenant(tenant_id)
        for index in range(records_per_tenant):
            document = _document(
                tenant_id,
                f"{tenant_id}-record-{index}",
                kind=PostgresRecordKind.EVALUATION,
            )
            result = repository.append(
                document,
                stored_at=NOW + timedelta(seconds=index + 1),
            )
            assert result.inserted is True
        connection.close()

    with ThreadPoolExecutor(max_workers=len(tenants)) as executor:
        tuple(executor.map(write_tenant, tenants))

    assert len(store.rows) == len(tenants) * records_per_tenant
    assert store.committed_writes == len(store.rows)

    verification = PostgresDatabaseAdapter(
        lambda *_: RecoverableConnection(store)
    ).connect(_target())
    for tenant_id in tenants:
        own = verification.tenant(tenant_id).get(
            kind=PostgresRecordKind.EVALUATION,
            record_id=f"{tenant_id}-record-0",
        )
        other_tenant = tenants[(tenants.index(tenant_id) + 1) % len(tenants)]
        cross_tenant = verification.tenant(tenant_id).get(
            kind=PostgresRecordKind.EVALUATION,
            record_id=f"{other_tenant}-record-0",
        )
        assert own is not None
        assert own.document.tenant_id == tenant_id
        assert cross_tenant is None

    assert verification.execution_authorized is False
    assert verification.production_mutation_authorized is False
