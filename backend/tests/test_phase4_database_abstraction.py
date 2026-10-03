"""R40A tests for the Phase 4 database abstraction."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
from pathlib import Path

import pytest

from backend.phase3 import (
    AccountIdentity,
    DecimalUnit,
    DurableDecimal,
    DurableStateKind,
    DurableStatePayload,
    DurableStateRecord,
    PropFirmProfileIdentity,
    SchemaIdentity,
    SourceIdentity,
    TenantIdentity,
)
from backend.phase4 import (
    DatabaseAccessMode,
    DatabaseAdapterRegistry,
    DatabaseAdapterUnavailableError,
    DatabaseAvailability,
    DatabaseBackend,
    DatabaseConfigurationError,
    DatabaseReadOnlyError,
    DatabaseTarget,
    DatabaseTenantIsolationError,
    REQUIRED_CAPABILITIES,
    SQLiteDatabaseAdapter,
    decode_exact_decimal,
    encode_exact_decimal,
)


OBSERVED = datetime(2026, 10, 3, 15, 0, tzinfo=timezone.utc)
COMMITTED = OBSERVED + timedelta(seconds=1)


def _record(tenant_id: str = "tenant-a", record_id: str = "snapshot-1"):
    return DurableStateRecord(
        record_id=record_id,
        schema=SchemaIdentity("arms.phase3", "account_snapshot", 1),
        kind=DurableStateKind.ACCOUNT_SNAPSHOT,
        observed_at=OBSERVED,
        tenant=TenantIdentity(tenant_id),
        source=SourceIdentity("runtime://paper/account-1", "snapshot-v1", True),
        payload=DurableStatePayload((
            ("balance", DurableDecimal(D("52341.0700"), DecimalUnit.CURRENCY, "USD")),
            ("risk_complete", True),
        )),
        account=AccountIdentity(tenant_id, "account-1"),
        profile=PropFirmProfileIdentity(
            "lucid",
            "lucidpro_funded_no_dll",
            "funded",
            DurableDecimal(D("50000.00"), DecimalUnit.CURRENCY, "USD"),
            "2026-10-03",
            "a" * 64,
        ),
    )


def _sqlite_target(path: Path, mode=DatabaseAccessMode.READ_WRITE):
    return DatabaseTarget(
        backend=DatabaseBackend.SQLITE,
        database_name="arms_phase4",
        access_mode=mode,
        sqlite_path=path,
    )


def test_database_targets_are_secret_free_and_backend_specific(tmp_path):
    sqlite = _sqlite_target(tmp_path / "phase4.sqlite3")
    postgres = DatabaseTarget(
        backend=DatabaseBackend.POSTGRESQL,
        database_name="arms_phase4",
        access_mode=DatabaseAccessMode.READ_ONLY,
        connection_reference="secrets/arms/staging/postgres",
    )
    assert sqlite.connection_reference is None
    assert postgres.sqlite_path is None
    with pytest.raises(DatabaseConfigurationError, match="raw PostgreSQL"):
        DatabaseTarget(
            backend=DatabaseBackend.POSTGRESQL,
            database_name="arms_phase4",
            access_mode=DatabaseAccessMode.READ_WRITE,
            connection_reference="postgresql://user:password@host/database",
        )


def test_postgresql_candidate_fails_closed_until_adapter_is_registered():
    registry = DatabaseAdapterRegistry((SQLiteDatabaseAdapter(),))
    target = DatabaseTarget(
        backend=DatabaseBackend.POSTGRESQL,
        database_name="arms_phase4",
        access_mode=DatabaseAccessMode.READ_WRITE,
        connection_reference="secrets/arms/staging/postgres",
    )
    with pytest.raises(DatabaseAdapterUnavailableError, match="not registered"):
        registry.connect(target)


def test_sqlite_adapter_creates_healthy_versioned_transactional_store(tmp_path):
    checked_at = datetime(2026, 10, 3, 15, 1, tzinfo=timezone.utc)
    adapter = SQLiteDatabaseAdapter(clock=lambda: checked_at)
    with adapter.connect(_sqlite_target(tmp_path / "phase4.sqlite3")) as connection:
        health = connection.health()
        assert connection.capabilities == REQUIRED_CAPABILITIES
        assert connection.schema_version == 7
        assert health.availability is DatabaseAvailability.AVAILABLE
        assert health.schema_version == 7
        assert health.checked_at == checked_at
        assert health.read_only is False
        assert health.detail_code == "sqlite_available"
        assert health.execution_authorized is False
        assert connection.execution_authorized is False
        assert connection.production_mutation_authorized is False


def test_tenant_session_round_trip_preserves_exact_decimal(tmp_path):
    registry = DatabaseAdapterRegistry((SQLiteDatabaseAdapter(),))
    with registry.connect(_sqlite_target(tmp_path / "phase4.sqlite3")) as connection:
        tenant = connection.tenant("tenant-a")
        result = tenant.append(_record(), committed_at=COMMITTED)
        restored = tenant.get(record_id="snapshot-1")
        assert result.inserted is True
        assert restored is not None
        assert restored.record == _record()
        assert restored.record.payload.get("balance").value == D("52341.07")
        assert tenant.count() == 1
        assert tenant.execution_authorized is False


def test_tenant_session_rejects_cross_tenant_write_and_hides_cross_tenant_read(tmp_path):
    with SQLiteDatabaseAdapter().connect(
        _sqlite_target(tmp_path / "phase4.sqlite3")
    ) as connection:
        tenant_a = connection.tenant("tenant-a")
        tenant_b = connection.tenant("tenant-b")
        tenant_a.append(_record(), committed_at=COMMITTED)
        with pytest.raises(DatabaseTenantIsolationError, match="does not match"):
            tenant_b.append(_record(), committed_at=COMMITTED)
        assert tenant_b.get(record_id="snapshot-1") is None
        assert tenant_b.count() == 0
        assert tenant_a.count() == 1


def test_read_only_mode_health_is_available_and_writes_fail_closed(tmp_path):
    path = tmp_path / "phase4.sqlite3"
    with SQLiteDatabaseAdapter().connect(_sqlite_target(path)) as writer:
        writer.tenant("tenant-a").append(_record(), committed_at=COMMITTED)
    with SQLiteDatabaseAdapter().connect(
        _sqlite_target(path, DatabaseAccessMode.READ_ONLY)
    ) as reader:
        health = reader.health()
        assert health.availability is DatabaseAvailability.AVAILABLE
        assert health.read_only is True
        assert health.detail_code == "sqlite_read_only"
        assert reader.tenant("tenant-a").count() == 1
        with pytest.raises(DatabaseReadOnlyError, match="read-only"):
            reader.tenant("tenant-a").append(
                replace(_record(), record_id="snapshot-2"),
                committed_at=COMMITTED,
            )


def test_read_only_missing_database_fails_closed(tmp_path):
    with pytest.raises(DatabaseReadOnlyError, match="does not exist"):
        SQLiteDatabaseAdapter().connect(
            _sqlite_target(tmp_path / "missing.sqlite3", DatabaseAccessMode.READ_ONLY)
        )


def test_closed_connection_health_is_unavailable_without_exception_details(tmp_path):
    connection = SQLiteDatabaseAdapter().connect(
        _sqlite_target(tmp_path / "phase4.sqlite3")
    )
    connection.close()
    health = connection.health()
    assert health.availability is DatabaseAvailability.UNAVAILABLE
    assert health.schema_version is None
    assert health.detail_code == "sqlite_unavailable"


def test_exact_decimal_codec_rejects_noncanonical_or_nonfinite_values():
    assert encode_exact_decimal(D("52341.0700")) == "52341.07"
    assert decode_exact_decimal("52341.07") == D("52341.07")
    for value in ("52341.0700", "NaN", " 1", ""):
        with pytest.raises(ValueError):
            decode_exact_decimal(value)
    with pytest.raises(ValueError):
        encode_exact_decimal(D("Infinity"))


def test_registry_rejects_duplicate_backend_registration():
    with pytest.raises(DatabaseConfigurationError, match="already registered"):
        DatabaseAdapterRegistry((SQLiteDatabaseAdapter(), SQLiteDatabaseAdapter()))


def test_health_contains_sqlite_driver_failure_as_unavailable(tmp_path):
    connection = SQLiteDatabaseAdapter().connect(
        _sqlite_target(tmp_path / "phase4.sqlite3")
    )
    connection._store._connection.close()
    health = connection.health()
    assert health.availability is DatabaseAvailability.UNAVAILABLE
    assert health.schema_version is None
    assert health.detail_code == "sqlite_unavailable"
