"""R47D synthetic database failure containment tests.

These tests exercise the production PostgreSQL boundary without a driver or
network.  Every injected failure must leave zero committed writes and must not
cause the registry to select another backend.
"""

from dataclasses import fields
from datetime import datetime, timedelta, timezone

import pytest

from backend.phase4 import (
    DatabaseAccessMode,
    DatabaseAdapterRegistry,
    DatabaseBackend,
    DatabaseError,
    DatabaseTarget,
    REQUIRED_CAPABILITIES,
)
from backend.phase4.postgresql_adapter import (
    PostgresDatabaseAdapter,
    PostgresDocument,
    PostgresRecordKind,
)


NOW = datetime(2026, 10, 3, 20, 0, tzinfo=timezone.utc)


class FailureCursor:
    def __init__(self, connection):
        self.connection = connection
        self.rowcount = -1
        self.result = None

    def execute(self, query, parameters=()):
        self.connection.queries.append((query, parameters))
        if query.startswith("SELECT schema_version"):
            self.result = (1,)
            self.rowcount = 1
            return self
        if query.startswith("INSERT INTO "):
            if self.connection.failure == "timeout":
                raise TimeoutError("postgres://user:secret@private-host timed out")
            table = query.split()[2]
            key = (table, parameters[0], parameters[1])
            self.connection.pending[key] = tuple(parameters[2:])
            self.rowcount = 1
            self.result = None
            return self
        if query.startswith("SELECT payload_sha256"):
            if self.connection.failure == "transaction_abort":
                raise RuntimeError("transaction is aborted: password=secret")
            table = query.split("FROM ", 1)[1].split()[0]
            key = (table, parameters[0], parameters[1])
            row = self.connection.pending.get(key)
            self.result = None if row is None else (row[1],)
            self.rowcount = 0 if row is None else 1
            return self
        raise AssertionError(f"unexpected query: {query}")

    def fetchone(self):
        return self.result

    def close(self):
        return None


class FailureConnection:
    def __init__(self, failure):
        self.failure = failure
        self.queries = []
        self.pending = {}
        self.rows = {}
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def cursor(self):
        return FailureCursor(self)

    def commit(self):
        self.rows.update(self.pending)
        self.pending.clear()
        self.commits += 1

    def rollback(self):
        self.pending.clear()
        self.rollbacks += 1

    def close(self):
        self.closed = True


class ForbiddenFallbackAdapter:
    backend = DatabaseBackend.SQLITE
    capabilities = REQUIRED_CAPABILITIES

    def __init__(self):
        self.connect_calls = 0

    def connect(self, target):
        self.connect_calls += 1
        raise AssertionError("an unavailable PostgreSQL target must not fall back")


def _target():
    return DatabaseTarget(
        backend=DatabaseBackend.POSTGRESQL,
        database_name="arms_phase4",
        access_mode=DatabaseAccessMode.READ_WRITE,
        connection_reference="secrets/arms/staging/postgres",
    )


def _document(record_id):
    return PostgresDocument(
        tenant_id="tenant-a",
        record_id=record_id,
        kind=PostgresRecordKind.OUTBOX,
        payload=b'{"event":"synthetic"}',
        occurred_at=NOW,
    )


def test_connection_unavailable_does_not_fall_back_to_another_backend():
    fallback = ForbiddenFallbackAdapter()

    def unavailable(*_):
        raise ConnectionError("postgres://user:secret@private-host unavailable")

    registry = DatabaseAdapterRegistry(
        (PostgresDatabaseAdapter(unavailable), fallback)
    )

    with pytest.raises(DatabaseError, match="PostgreSQL connection unavailable") as error:
        registry.connect(_target())

    assert "secret" not in str(error.value)
    assert fallback.connect_calls == 0


@pytest.mark.parametrize("failure", ("timeout", "transaction_abort"))
def test_write_failure_rolls_back_without_commit_or_fallback(failure):
    raw = FailureConnection(failure)
    fallback = ForbiddenFallbackAdapter()
    registry = DatabaseAdapterRegistry(
        (PostgresDatabaseAdapter(lambda *_: raw), fallback)
    )
    connection = registry.connect(_target())

    with pytest.raises(DatabaseError, match="PostgreSQL transaction failed") as error:
        connection.tenant("tenant-a").append(
            _document(f"failure-{failure}"),
            stored_at=NOW + timedelta(seconds=1),
        )

    assert "secret" not in str(error.value)
    assert raw.rollbacks >= 2  # health check plus failed transaction
    assert raw.commits == 0
    assert raw.pending == {}
    assert raw.rows == {}
    assert fallback.connect_calls == 0


def test_failed_write_cannot_be_observed_as_a_committed_record():
    raw = FailureConnection("transaction_abort")
    connection = PostgresDatabaseAdapter(lambda *_: raw).connect(_target())

    with pytest.raises(DatabaseError):
        connection.tenant("tenant-a").append(
            _document("aborted-record"),
            stored_at=NOW + timedelta(seconds=1),
        )

    assert not any(key[2] == "aborted-record" for key in raw.rows)
    assert raw.commits == 0


def test_read_replica_routing_is_not_supported_or_silently_inferred():
    target_fields = {item.name for item in fields(DatabaseTarget)}
    assert "read_replica" not in target_fields
    assert "replica_lag" not in target_fields

    with pytest.raises(TypeError, match="unexpected keyword argument"):
        DatabaseTarget(
            backend=DatabaseBackend.POSTGRESQL,
            database_name="arms_phase4",
            access_mode=DatabaseAccessMode.READ_ONLY,
            connection_reference="secrets/arms/staging/postgres",
            read_replica="stale-replica",  # type: ignore[call-arg]
        )
