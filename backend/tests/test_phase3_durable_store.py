"""R32E tests for the isolated append-only Phase 3 SQLite store."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
import sqlite3

import pytest

from backend.phase3 import (
    AccountIdentity,
    DecimalUnit,
    DurableDecimal,
    DurableStateKind,
    DurableStatePayload,
    DurableStateRecord,
    DurableStoreConflictError,
    DurableStoreError,
    DurableStoreIntegrityError,
    DurableStoreReadOnlyError,
    Phase3DurableStateStore,
    PropFirmProfileIdentity,
    STORE_FORMAT,
    STORE_MIGRATIONS,
    STORE_SCHEMA_CHECKSUM,
    STORE_SCHEMA_VERSION,
    SchemaIdentity,
    SourceIdentity,
    TenantIdentity,
    state_record_hash,
)


OBSERVED = datetime(2026, 10, 3, 14, 30, tzinfo=timezone.utc)
COMMITTED = OBSERVED + timedelta(seconds=1)


def state(**changes):
    values = dict(
        record_id="snapshot-1",
        schema=SchemaIdentity("arms.phase3", "account_snapshot", 1),
        kind=DurableStateKind.ACCOUNT_SNAPSHOT,
        observed_at=OBSERVED,
        tenant=TenantIdentity("tenant-a"),
        source=SourceIdentity("runtime://paper/account-1", "snapshot-v1", True),
        payload=DurableStatePayload((
            ("balance", DurableDecimal(D("52341.0700"), DecimalUnit.CURRENCY, "USD")),
            ("drawdown", DurableDecimal(D("125.500"), DecimalUnit.CURRENCY, "USD")),
            ("risk_complete", True),
        )),
        account=AccountIdentity("tenant-a", "account-1"),
        profile=PropFirmProfileIdentity(
            "lucid",
            "lucidpro_funded_no_dll",
            "funded",
            DurableDecimal(D("50000.00"), DecimalUnit.CURRENCY, "USD"),
            "2026-10-03",
            "a" * 64,
        ),
    )
    values.update(changes)
    return DurableStateRecord(**values)


def test_create_bootstraps_isolated_versioned_store(tmp_path):
    path = tmp_path / "phase3-state.sqlite3"
    with Phase3DurableStateStore.create(path) as store:
        assert store.path == path.resolve()
        assert store.schema_version == STORE_SCHEMA_VERSION == 5
        assert store.read_only is False
        assert store.execution_authorized is False
        assert store.production_mutation_authorized is False
        assert store.canonical_admin_authorized is False
        metadata = store._connection.execute(
            "SELECT store_format, schema_version, schema_checksum FROM phase3_store_metadata"
        ).fetchone()
        assert metadata == (STORE_FORMAT, 5, STORE_SCHEMA_CHECKSUM)
        assert store._connection.execute("PRAGMA foreign_keys").fetchone() == (1,)
        assert store._connection.execute("PRAGMA synchronous").fetchone() == (2,)
        assert store._connection.execute("PRAGMA journal_mode").fetchone() == ("wal",)


def test_bootstrap_records_checksumed_migration_history(tmp_path):
    with Phase3DurableStateStore.create(tmp_path / "phase3.sqlite3") as store:
        rows = store._connection.execute(
            "SELECT version, name, checksum FROM phase3_schema_migrations"
        ).fetchall()
        assert rows[0][0:2] == (1, "phase3_bootstrap")
        assert rows[1:] == [
            (migration.version, migration.name, migration.checksum)
            for migration in STORE_MIGRATIONS
        ]


def test_append_round_trip_preserves_exact_canonical_record(tmp_path):
    path = tmp_path / "phase3.sqlite3"
    original = state()
    with Phase3DurableStateStore.create(path) as store:
        result = store.append(original, committed_at=COMMITTED)
        assert result.inserted is True
        assert result.duplicate is False
        assert result.content_hash == state_record_hash(original)
        assert result.execution_authorized is False
        restored = store.get(tenant_id="tenant-a", record_id="snapshot-1")
        assert restored is not None
        assert restored.record == original
        assert restored.content_hash == state_record_hash(original)
        assert restored.committed_at == COMMITTED
        assert restored.execution_authorized is False

        payload_type, payload = store._connection.execute(
            "SELECT typeof(payload), payload FROM phase3_state_records"
        ).fetchone()
        assert payload_type == "blob"
        assert b'"value":"52341.07"' in payload
        assert b"52341.0700" not in payload


def test_reopen_recovers_committed_record_without_runtime_authority(tmp_path):
    path = tmp_path / "phase3.sqlite3"
    with Phase3DurableStateStore.create(path) as store:
        store.append(state(), committed_at=COMMITTED)
    with Phase3DurableStateStore.open(path) as reopened:
        assert reopened.count() == 1
        assert reopened.get(tenant_id="tenant-a", record_id="snapshot-1").record == state()
        assert reopened.execution_authorized is False


def test_exact_duplicate_is_idempotent_and_does_not_add_rows(tmp_path):
    with Phase3DurableStateStore.create(tmp_path / "phase3.sqlite3") as store:
        first = store.append(state(), committed_at=COMMITTED)
        second = store.append(state(), committed_at=COMMITTED + timedelta(minutes=1))
        assert first.inserted is True
        assert second.inserted is False
        assert second.duplicate is True
        assert second.content_hash == first.content_hash
        assert store.count() == 1


def test_same_record_identity_with_different_content_fails_closed(tmp_path):
    changed = replace(
        state(),
        payload=DurableStatePayload((
            ("balance", DurableDecimal(D("52000"), DecimalUnit.CURRENCY, "USD")),
            ("drawdown", DurableDecimal(D("125.5"), DecimalUnit.CURRENCY, "USD")),
            ("risk_complete", True),
        )),
    )
    with Phase3DurableStateStore.create(tmp_path / "phase3.sqlite3") as store:
        store.append(state(), committed_at=COMMITTED)
        with pytest.raises(DurableStoreConflictError, match="different immutable"):
            store.append(changed, committed_at=COMMITTED)
        assert store.count() == 1
        assert store.get(tenant_id="tenant-a", record_id="snapshot-1").record == state()


def test_record_identity_is_scoped_by_tenant(tmp_path):
    tenant_b = replace(
        state(),
        tenant=TenantIdentity("tenant-b"),
        account=AccountIdentity("tenant-b", "account-1"),
    )
    with Phase3DurableStateStore.create(tmp_path / "phase3.sqlite3") as store:
        store.append(state(), committed_at=COMMITTED)
        store.append(tenant_b, committed_at=COMMITTED)
        assert store.count() == 2
        assert store.count(tenant_id="tenant-a") == 1
        assert store.count(tenant_id="tenant-b") == 1
        assert store.get(tenant_id="tenant-c", record_id="snapshot-1") is None


def test_read_only_reopen_performs_reads_and_rejects_writes(tmp_path):
    path = tmp_path / "phase3.sqlite3"
    with Phase3DurableStateStore.create(path) as store:
        store.append(state(), committed_at=COMMITTED)
    with Phase3DurableStateStore.open(path, read_only=True) as reader:
        assert reader.read_only is True
        assert reader.count() == 1
        assert reader.get(tenant_id="tenant-a", record_id="snapshot-1") is not None
        assert reader._connection.execute("PRAGMA query_only").fetchone() == (1,)
        with pytest.raises(DurableStoreReadOnlyError, match="read-only"):
            reader.append(replace(state(), record_id="snapshot-2"), committed_at=COMMITTED)
        assert reader.count() == 1


@pytest.mark.parametrize("statement", [
    "UPDATE phase3_state_records SET kind = 'account'",
    "DELETE FROM phase3_state_records",
])
def test_state_records_are_enforced_append_only(tmp_path, statement):
    with Phase3DurableStateStore.create(tmp_path / "phase3.sqlite3") as store:
        store.append(state(), committed_at=COMMITTED)
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            store._connection.execute(statement)
        assert store.count() == 1


def test_failed_record_insert_rolls_back_identity_rows_atomically(tmp_path):
    new_state = replace(
        state(),
        record_id="snapshot-new",
        tenant=TenantIdentity("tenant-new"),
        account=AccountIdentity("tenant-new", "account-new"),
    )
    with Phase3DurableStateStore.create(tmp_path / "phase3.sqlite3") as store:
        store._connection.execute(
            """
            CREATE TRIGGER test_fail_insert BEFORE INSERT ON phase3_state_records
            BEGIN SELECT RAISE(ABORT, 'synthetic insert failure'); END
            """
        )
        with pytest.raises(sqlite3.IntegrityError, match="synthetic"):
            store.append(new_state, committed_at=COMMITTED)
        assert store.count() == 0
        assert store._connection.execute(
            "SELECT COUNT(*) FROM phase3_tenants WHERE tenant_id = 'tenant-new'"
        ).fetchone() == (0,)
        assert store._connection.execute(
            "SELECT COUNT(*) FROM phase3_accounts WHERE tenant_id = 'tenant-new'"
        ).fetchone() == (0,)


def test_foreign_key_integrity_is_clean_after_append(tmp_path):
    with Phase3DurableStateStore.create(tmp_path / "phase3.sqlite3") as store:
        store.append(state(), committed_at=COMMITTED)
        assert store._connection.execute("PRAGMA foreign_key_check").fetchall() == []
        with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
            store._connection.execute(
                "INSERT INTO phase3_accounts VALUES ('unknown', 'account-x', ?)",
                (COMMITTED.isoformat(),),
            )


def test_hash_corruption_is_detected_on_read(tmp_path):
    with Phase3DurableStateStore.create(tmp_path / "phase3.sqlite3") as store:
        store.append(state(), committed_at=COMMITTED)
        store._connection.execute("DROP TRIGGER phase3_records_no_update")
        store._connection.execute(
            "UPDATE phase3_state_records SET payload_sha256 = ?",
            ("0" * 64,),
        )
        with pytest.raises(DurableStoreIntegrityError, match="hash mismatch"):
            store.get(tenant_id="tenant-a", record_id="snapshot-1")


def test_index_column_corruption_is_detected_on_read(tmp_path):
    with Phase3DurableStateStore.create(tmp_path / "phase3.sqlite3") as store:
        store.append(state(), committed_at=COMMITTED)
        store._connection.execute("DROP TRIGGER phase3_records_no_update")
        store._connection.execute(
            "UPDATE phase3_state_records SET source_version = 'tampered'"
        )
        with pytest.raises(DurableStoreIntegrityError, match="index mismatch"):
            store.get(tenant_id="tenant-a", record_id="snapshot-1")


def test_missing_append_only_schema_object_blocks_reopen(tmp_path):
    path = tmp_path / "phase3.sqlite3"
    with Phase3DurableStateStore.create(path) as store:
        store._connection.execute("DROP TRIGGER phase3_records_no_delete")
    with pytest.raises(DurableStoreIntegrityError, match="schema objects mismatch"):
        Phase3DurableStateStore.open(path)


def test_metadata_mismatch_blocks_reopen(tmp_path):
    path = tmp_path / "phase3.sqlite3"
    with Phase3DurableStateStore.create(path) as store:
        store._connection.execute(
            "UPDATE phase3_store_metadata SET schema_checksum = ? WHERE singleton = 1",
            ("0" * 64,),
        )
    with pytest.raises(DurableStoreIntegrityError, match="migration validation failed"):
        Phase3DurableStateStore.open(path)


def test_unknown_sqlite_database_is_not_adopted_or_migrated(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE legacy(value REAL)")
        connection.execute("INSERT INTO legacy VALUES (1.25)")
    before = path.read_bytes()
    with pytest.raises(DurableStoreIntegrityError, match="migration validation failed"):
        Phase3DurableStateStore.open(path)
    assert path.read_bytes() == before


def test_create_refuses_existing_file_without_overwrite(tmp_path):
    path = tmp_path / "existing.sqlite3"
    path.write_bytes(b"user-data")
    with pytest.raises(DurableStoreConflictError, match="already exists"):
        Phase3DurableStateStore.create(path)
    assert path.read_bytes() == b"user-data"


def test_missing_store_and_invalid_commit_time_fail_without_records(tmp_path):
    with pytest.raises(DurableStoreIntegrityError, match="does not exist"):
        Phase3DurableStateStore.open(tmp_path / "missing.sqlite3")
    with Phase3DurableStateStore.create(tmp_path / "phase3.sqlite3") as store:
        with pytest.raises(ValueError, match="precede"):
            store.append(state(), committed_at=OBSERVED - timedelta(seconds=1))
        with pytest.raises(ValueError, match="timezone-aware"):
            store.append(state(), committed_at=datetime(2026, 10, 3))
        assert store.count() == 0


def test_closed_store_rejects_operations(tmp_path):
    store = Phase3DurableStateStore.create(tmp_path / "phase3.sqlite3")
    store.close()
    store.close()
    with pytest.raises(DurableStoreError, match="closed"):
        store.count()
    with pytest.raises(DurableStoreError, match="closed"):
        store.append(state(), committed_at=COMMITTED)


def test_store_module_isolated_from_legacy_storage_and_execution():
    from pathlib import Path
    from backend.phase3 import durable_store

    source = Path(durable_store.__file__).read_text(encoding="utf-8")
    forbidden = (
        "journal_database",
        "trades.db",
        "backend.execution",
        "broker_connector",
        "EnterLong",
        "EnterShort",
    )
    assert all(token not in source for token in forbidden)
