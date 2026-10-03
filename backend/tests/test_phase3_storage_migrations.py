"""R32F tests for forward-only transactional Phase 3 migrations."""

from datetime import datetime, timezone
import sqlite3

import pytest

from backend.phase3 import (
    DurableStoreIntegrityError,
    MigrationApplyError,
    MigrationForwardOnlyError,
    MigrationIntegrityError,
    Phase3DurableStateStore,
    Phase3Migration,
    STORE_FORMAT,
    STORE_MIGRATIONS,
    STORE_SCHEMA_CHECKSUM,
    STORE_SCHEMA_VERSION,
    apply_phase3_migrations,
    migration_chain_checksum,
    validate_migration_plan,
)
from backend.phase3 import durable_store


NOW = datetime(2026, 10, 3, 15, 0, tzinfo=timezone.utc)


def next_migration(*statements, name="test_forward_migration"):
    return Phase3Migration(
        version=STORE_SCHEMA_VERSION + 1,
        name=name,
        statements=tuple(statements),
    )


def apply(connection, migrations, *, applied_at=NOW):
    return apply_phase3_migrations(
        connection,
        store_format=STORE_FORMAT,
        bootstrap_checksum=durable_store._BOOTSTRAP_SCHEMA_CHECKSUM,
        migrations=migrations,
        applied_at=applied_at,
    )


def raw_current_store(tmp_path):
    path = tmp_path / "phase3.sqlite3"
    Phase3DurableStateStore.create(path).close()
    connection = sqlite3.connect(path, isolation_level=None)
    connection.execute("PRAGMA foreign_keys=ON")
    return path, connection


def raw_bootstrap_store(tmp_path):
    path = tmp_path / "phase3-v1.sqlite3"
    connection = sqlite3.connect(path, isolation_level=None)
    connection.execute("PRAGMA foreign_keys=ON")
    durable_store.Phase3DurableStateStore._bootstrap(connection)
    connection.close()
    return path


def test_builtin_migration_upgrades_bootstrap_store_on_writable_open(tmp_path):
    path = raw_bootstrap_store(tmp_path)
    with Phase3DurableStateStore.open(path) as store:
        assert store.schema_version == STORE_SCHEMA_VERSION == 6
        history = store._connection.execute(
            "SELECT version, name, checksum FROM phase3_schema_migrations ORDER BY version"
        ).fetchall()
        assert history[1:] == [
            (migration.version, migration.name, migration.checksum)
            for migration in STORE_MIGRATIONS
        ]
        indexes = {
            row[0] for row in store._connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index'"
            )
        }
        assert "phase3_records_commit_time" in indexes


def test_writable_startup_is_idempotent_when_current(tmp_path):
    path, connection = raw_current_store(tmp_path)
    before = connection.execute(
        "SELECT version, name, checksum, applied_at FROM phase3_schema_migrations"
    ).fetchall()
    connection.close()
    with Phase3DurableStateStore.open(path) as first:
        assert first.schema_version == STORE_SCHEMA_VERSION
    with Phase3DurableStateStore.open(path) as second:
        after = second._connection.execute(
            "SELECT version, name, checksum, applied_at FROM phase3_schema_migrations"
        ).fetchall()
    assert after == before


def test_read_only_open_does_not_apply_pending_migration(tmp_path):
    path = raw_bootstrap_store(tmp_path)
    before = path.read_bytes()
    with pytest.raises(DurableStoreIntegrityError, match="metadata mismatch"):
        Phase3DurableStateStore.open(path, read_only=True)
    assert path.read_bytes() == before
    with Phase3DurableStateStore.open(path) as upgraded:
        assert upgraded.schema_version == STORE_SCHEMA_VERSION


def test_custom_forward_migration_is_atomic_and_idempotent(tmp_path):
    _, connection = raw_current_store(tmp_path)
    migration = next_migration(
        "CREATE TABLE test_migration_marker (id INTEGER PRIMARY KEY)",
    )
    plan = STORE_MIGRATIONS + (migration,)
    first = apply(connection, plan)
    assert first.from_version == STORE_SCHEMA_VERSION
    assert first.to_version == migration.version
    assert first.applied_versions == (migration.version,)
    assert first.changed is True
    assert first.execution_authorized is False
    second = apply(connection, plan)
    assert second.from_version == migration.version
    assert second.to_version == migration.version
    assert second.applied_versions == ()
    assert second.changed is False
    assert connection.execute(
        "SELECT COUNT(*) FROM phase3_schema_migrations WHERE version = ?",
        (migration.version,),
    ).fetchone() == (1,)
    connection.close()


def test_failed_migration_rolls_back_every_statement_and_metadata(tmp_path):
    path, connection = raw_current_store(tmp_path)
    before_metadata = connection.execute(
        "SELECT schema_version, schema_checksum FROM phase3_store_metadata"
    ).fetchone()
    before_history = connection.execute(
        "SELECT version, name, checksum FROM phase3_schema_migrations"
    ).fetchall()
    migration = next_migration(
        "CREATE TABLE test_partial_table (id INTEGER PRIMARY KEY)",
        "CREATE INDEX test_invalid_index ON missing_table(id)",
        name="test_rollback_migration",
    )
    with pytest.raises(MigrationApplyError, match="transaction failed"):
        apply(connection, STORE_MIGRATIONS + (migration,))
    assert connection.execute(
        "SELECT name FROM sqlite_master WHERE name = 'test_partial_table'"
    ).fetchone() is None
    assert connection.execute(
        "SELECT schema_version, schema_checksum FROM phase3_store_metadata"
    ).fetchone() == before_metadata
    assert connection.execute(
        "SELECT version, name, checksum FROM phase3_schema_migrations"
    ).fetchall() == before_history
    connection.close()
    with Phase3DurableStateStore.open(path) as recovered:
        assert recovered.schema_version == STORE_SCHEMA_VERSION


def test_runner_does_not_adopt_or_roll_back_a_callers_transaction(tmp_path):
    _, connection = raw_current_store(tmp_path)
    connection.execute("BEGIN")
    connection.execute("CREATE TABLE caller_owned_transaction(id INTEGER)")
    migration = next_migration("CREATE TABLE test_never_started(id INTEGER)")
    with pytest.raises(MigrationApplyError, match="active transaction"):
        apply(connection, STORE_MIGRATIONS + (migration,))
    assert connection.in_transaction is True
    assert connection.execute(
        "SELECT name FROM sqlite_master WHERE name = 'caller_owned_transaction'"
    ).fetchone() == ("caller_owned_transaction",)
    assert connection.execute(
        "SELECT name FROM sqlite_master WHERE name = 'test_never_started'"
    ).fetchone() is None
    connection.execute("ROLLBACK")
    connection.close()


def test_runner_requires_foreign_keys_before_any_schema_write(tmp_path):
    _, connection = raw_current_store(tmp_path)
    connection.execute("PRAGMA foreign_keys=OFF")
    migration = next_migration("CREATE TABLE test_fk_disabled(id INTEGER)")
    with pytest.raises(MigrationIntegrityError, match="foreign-key enforcement"):
        apply(connection, STORE_MIGRATIONS + (migration,))
    assert connection.in_transaction is False
    assert connection.execute(
        "SELECT name FROM sqlite_master WHERE name = 'test_fk_disabled'"
    ).fetchone() is None
    connection.close()


@pytest.mark.parametrize(
    "statement",
    [
        "DROP TABLE phase3_state_records",
        "DELETE FROM phase3_state_records",
        "UPDATE phase3_store_metadata SET schema_version = 1",
        "ALTER TABLE phase3_state_records DROP COLUMN payload",
        "PRAGMA foreign_keys=OFF",
        "CREATE TABLE safe(id INTEGER); DROP TABLE phase3_state_records",
    ],
)
def test_destructive_or_mutating_migration_sql_is_rejected(statement):
    with pytest.raises(ValueError, match="forbidden"):
        next_migration(statement)


@pytest.mark.parametrize(
    "statement",
    [
        "SELECT 1",
        "ALTER TABLE phase3_state_records RENAME TO changed",
        " create table leading_space(id integer)",
        "CREATE TABLE trailing_space(id integer) ",
        "CREATE TABLE commented(id integer) -- comment",
    ],
)
def test_non_forward_or_noncanonical_migration_sql_is_rejected(statement):
    with pytest.raises(ValueError):
        next_migration(statement)


def test_only_restrictive_append_only_triggers_are_allowed():
    trigger = next_migration(
        "CREATE TRIGGER test_no_update BEFORE UPDATE ON test_rows "
        "BEGIN SELECT RAISE(ABORT, 'rows are append only'); END"
    )
    assert trigger.statements[0].startswith("CREATE TRIGGER")
    with pytest.raises(ValueError, match="forbidden"):
        next_migration(
            "CREATE TRIGGER test_mutating AFTER UPDATE ON test_rows "
            "BEGIN DELETE FROM test_rows; END"
        )


def test_plan_requires_immutable_contiguous_unique_migrations():
    migration = Phase3Migration(2, "first", ("CREATE TABLE test_first(id INTEGER)",))
    assert validate_migration_plan((migration,)) == (migration,)
    with pytest.raises(ValueError, match="immutable tuple"):
        validate_migration_plan([migration])
    with pytest.raises(MigrationForwardOnlyError, match="contiguous"):
        validate_migration_plan((Phase3Migration(
            3, "gap", ("CREATE TABLE test_gap(id INTEGER)",)
        ),))
    with pytest.raises(ValueError, match="unique"):
        validate_migration_plan((
            migration,
            Phase3Migration(3, "first", ("CREATE TABLE test_second(id INTEGER)",)),
        ))


def test_migration_and_chain_checksums_are_stable_and_content_sensitive():
    first = Phase3Migration(2, "first", ("CREATE TABLE test_first(id INTEGER)",))
    same = Phase3Migration(2, "first", ("CREATE TABLE test_first(id INTEGER)",))
    changed = Phase3Migration(2, "first", ("CREATE TABLE test_first(id TEXT)",))
    assert first.checksum == same.checksum
    assert first.checksum != changed.checksum
    bootstrap = "a" * 64
    assert migration_chain_checksum(bootstrap, (first,)) == migration_chain_checksum(
        bootstrap, (same,)
    )
    assert migration_chain_checksum(bootstrap, (first,)) != migration_chain_checksum(
        bootstrap, (changed,)
    )


def test_tampered_applied_history_fails_before_schema_write(tmp_path):
    _, connection = raw_current_store(tmp_path)
    connection.execute("DROP TRIGGER phase3_migrations_no_update")
    connection.execute(
        "UPDATE phase3_schema_migrations SET checksum = ? WHERE version = 2",
        ("0" * 64,),
    )
    migration = next_migration("CREATE TABLE test_must_not_exist(id INTEGER)")
    with pytest.raises(MigrationIntegrityError, match="history checksum mismatch"):
        apply(connection, STORE_MIGRATIONS + (migration,))
    assert connection.execute(
        "SELECT name FROM sqlite_master WHERE name = 'test_must_not_exist'"
    ).fetchone() is None
    connection.close()


def test_newer_store_cannot_be_downgraded_by_shorter_plan(tmp_path):
    _, connection = raw_current_store(tmp_path)
    migration = next_migration("CREATE TABLE test_newer(id INTEGER)")
    apply(connection, STORE_MIGRATIONS + (migration,))
    with pytest.raises(MigrationForwardOnlyError, match="newer"):
        apply(connection, STORE_MIGRATIONS)
    assert connection.execute(
        "SELECT schema_version FROM phase3_store_metadata"
    ).fetchone() == (migration.version,)
    connection.close()


def test_invalid_time_and_unknown_database_fail_without_migration(tmp_path):
    _, connection = raw_current_store(tmp_path)
    migration = next_migration("CREATE TABLE test_time(id INTEGER)")
    with pytest.raises(ValueError, match="timezone-aware"):
        apply(
            connection,
            STORE_MIGRATIONS + (migration,),
            applied_at=datetime(2026, 10, 3),
        )
    connection.close()

    unknown = sqlite3.connect(tmp_path / "unknown.sqlite3", isolation_level=None)
    unknown.execute("CREATE TABLE legacy(value REAL)")
    with pytest.raises(MigrationIntegrityError, match="invalid phase3 migration schema"):
        apply(unknown, STORE_MIGRATIONS)
    assert unknown.execute(
        "SELECT name FROM sqlite_master WHERE name = 'legacy'"
    ).fetchone() == ("legacy",)
    unknown.close()


def test_current_store_checksum_matches_registered_migration_chain():
    expected = migration_chain_checksum(
        durable_store._BOOTSTRAP_SCHEMA_CHECKSUM,
        STORE_MIGRATIONS,
    )
    assert STORE_SCHEMA_CHECKSUM == expected
    assert STORE_SCHEMA_VERSION == 1 + len(STORE_MIGRATIONS)


def test_migration_module_has_no_execution_or_network_dependencies():
    from pathlib import Path
    from backend.phase3 import storage_migrations

    source = Path(storage_migrations.__file__).read_text(encoding="utf-8")
    forbidden = (
        "backend.execution",
        "broker_connector",
        "requests",
        "httpx",
        "subprocess",
    )
    assert all(token not in source for token in forbidden)
