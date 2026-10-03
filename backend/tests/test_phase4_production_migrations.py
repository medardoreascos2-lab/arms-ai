"""R40C containerless tests for transactional PostgreSQL migrations."""

from copy import deepcopy
from datetime import datetime, timezone

import pytest

from backend.phase4 import POSTGRES_TABLES
from backend.phase4.production_migrations import (
    POSTGRES_EMPTY_SCHEMA_CHECKSUM,
    POSTGRES_MIGRATIONS,
    POSTGRES_SCHEMA_CHECKSUM,
    POSTGRES_SCHEMA_VERSION,
    PostgresMigration,
    ProductionMigrationApplyError,
    ProductionMigrationForwardOnlyError,
    ProductionMigrationIntegrityError,
    ProductionMigrationReadOnlyError,
    ProductionMigrationRunner,
    postgres_migration_chain_checksum,
    validate_postgres_migration_plan,
)


NOW = datetime(2026, 10, 3, 17, 0, tzinfo=timezone.utc)
NOW_TEXT = "2026-10-03T17:00:00.000000Z"


class FakeMigrationCursor:
    def __init__(self, connection):
        self.connection = connection
        self.result = None
        self.results = []
        self.closed = False

    def execute(self, query, parameters=()):
        self.connection.queries.append((query, parameters))
        if self.connection.fail_marker and self.connection.fail_marker in query:
            raise RuntimeError("driver leaked fake-password-value")
        if query.startswith("SELECT pg_advisory_xact_lock"):
            self.result = (None,)
            return self
        if query.startswith("SELECT to_regclass"):
            self.result = (
                ("phase4_store_metadata",)
                if self.connection.tables_present
                else (None,)
            )
            return self
        if query.startswith("SELECT schema_version"):
            self.result = self.connection.metadata
            return self
        if query.startswith("SELECT version, name"):
            self.results = list(self.connection.history)
            return self
        if query.startswith(("CREATE TABLE ", "CREATE INDEX ", "ALTER TABLE ")):
            self.connection.pending_ddl.append(query)
            self.result = None
            return self
        if query.startswith("INSERT INTO phase4_schema_migrations"):
            self.connection.pending_history.append(tuple(parameters))
            self.result = None
            return self
        if query.startswith("INSERT INTO phase4_store_metadata"):
            version, checksum, created_at, updated_at = parameters
            self.connection.pending_metadata = (
                version,
                checksum,
                created_at,
                updated_at,
            )
            self.result = None
            return self
        raise AssertionError(f"unexpected migration query: {query}")

    def fetchone(self):
        return self.result

    def fetchall(self):
        return list(self.results)

    def close(self):
        self.closed = True


class FakeMigrationConnection:
    def __init__(
        self,
        *,
        tables_present=False,
        metadata=None,
        history=None,
        fail_marker=None,
        autocommit=False,
    ):
        self.autocommit = autocommit
        self.tables_present = tables_present
        self.metadata = metadata
        self.history = list(history or [])
        self.fail_marker = fail_marker
        self.queries = []
        self.applied_ddl = []
        self.pending_ddl = []
        self.pending_history = []
        self.pending_metadata = None
        self.commits = 0
        self.rollbacks = 0

    def cursor(self):
        return FakeMigrationCursor(self)

    def commit(self):
        self.applied_ddl.extend(self.pending_ddl)
        if self.pending_ddl:
            self.tables_present = True
        self.history.extend(self.pending_history)
        if self.pending_metadata is not None:
            version, checksum, created_at, updated_at = self.pending_metadata
            if self.metadata is not None and self.history:
                created_at = self.metadata[2] if len(self.metadata) > 2 else created_at
            self.metadata = (version, checksum)
        self._clear_pending()
        self.commits += 1

    def rollback(self):
        self._clear_pending()
        self.rollbacks += 1

    def _clear_pending(self):
        self.pending_ddl = []
        self.pending_history = []
        self.pending_metadata = None


def _version_two(*statements):
    return PostgresMigration(
        version=2,
        name="add_research_provenance",
        statements=tuple(statements),
    )


def test_builtin_plan_covers_every_phase4_record_table_and_has_stable_checksum():
    assert POSTGRES_SCHEMA_VERSION == 1
    assert POSTGRES_SCHEMA_CHECKSUM == postgres_migration_chain_checksum(
        POSTGRES_MIGRATIONS
    )
    assert POSTGRES_SCHEMA_CHECKSUM != POSTGRES_EMPTY_SCHEMA_CHECKSUM
    statements = "\n".join(POSTGRES_MIGRATIONS[0].statements)
    for table in POSTGRES_TABLES:
        assert f"CREATE TABLE {table} " in statements


def test_plan_validation_is_contiguous_forward_only_and_blocks_unsafe_sql():
    assert validate_postgres_migration_plan(POSTGRES_MIGRATIONS) is POSTGRES_MIGRATIONS
    with pytest.raises(ProductionMigrationForwardOnlyError, match="contiguous"):
        validate_postgres_migration_plan(
            (
                PostgresMigration(
                    version=2,
                    name="gap",
                    statements=("CREATE TABLE gap_table (id INTEGER)",),
                ),
            )
        )
    with pytest.raises(ValueError, match="data-mutating"):
        PostgresMigration(
            version=1,
            name="unsafe",
            statements=("DROP TABLE phase4_store_metadata",),
        )


def test_bootstrap_is_transactional_records_history_and_is_idempotent():
    raw = FakeMigrationConnection()
    runner = ProductionMigrationRunner(raw)
    first = runner.apply(POSTGRES_MIGRATIONS, applied_at=NOW)
    assert first.from_version == 0
    assert first.to_version == 1
    assert first.applied_versions == (1,)
    assert first.changed is True
    assert first.execution_authorized is False
    assert first.production_mutation_authorized is False
    assert raw.metadata == (1, POSTGRES_SCHEMA_CHECKSUM)
    assert raw.history == [
        (
            1,
            POSTGRES_MIGRATIONS[0].name,
            POSTGRES_MIGRATIONS[0].checksum,
            NOW_TEXT,
        )
    ]
    before = (deepcopy(raw.metadata), deepcopy(raw.history), deepcopy(raw.applied_ddl))
    second = runner.apply(POSTGRES_MIGRATIONS, applied_at=NOW)
    assert second.applied_versions == ()
    assert second.changed is False
    assert (raw.metadata, raw.history, raw.applied_ddl) == before


def test_forward_migration_updates_checksum_and_preserves_complete_history():
    raw = FakeMigrationConnection()
    runner = ProductionMigrationRunner(raw)
    runner.apply(POSTGRES_MIGRATIONS, applied_at=NOW)
    migration = _version_two(
        "ALTER TABLE phase4_research_metadata ADD COLUMN provenance TEXT"
    )
    plan = POSTGRES_MIGRATIONS + (migration,)
    result = runner.apply(plan, applied_at=NOW)
    assert result.from_version == 1
    assert result.to_version == 2
    assert result.applied_versions == (2,)
    assert raw.metadata == (2, postgres_migration_chain_checksum(plan))
    assert [row[0] for row in raw.history] == [1, 2]
    assert raw.history[-1][1:3] == (migration.name, migration.checksum)


def test_tampered_history_and_newer_database_fail_closed_before_schema_writes():
    migration = POSTGRES_MIGRATIONS[0]
    tampered = FakeMigrationConnection(
        tables_present=True,
        metadata=(1, POSTGRES_SCHEMA_CHECKSUM),
        history=[(1, migration.name, "0" * 64, NOW_TEXT)],
    )
    with pytest.raises(ProductionMigrationIntegrityError, match="history checksum"):
        ProductionMigrationRunner(tampered).apply(POSTGRES_MIGRATIONS, applied_at=NOW)
    assert tampered.applied_ddl == []
    assert tampered.commits == 0
    assert tampered.rollbacks == 1

    newer = FakeMigrationConnection(
        tables_present=True,
        metadata=(2, "1" * 64),
        history=[],
    )
    with pytest.raises(ProductionMigrationForwardOnlyError, match="newer"):
        ProductionMigrationRunner(newer).apply(POSTGRES_MIGRATIONS, applied_at=NOW)
    assert newer.commits == 0
    assert newer.rollbacks == 1


def test_failed_migration_rolls_back_ddl_history_and_metadata_without_leakage():
    raw = FakeMigrationConnection(fail_marker="failure_marker")
    runner = ProductionMigrationRunner(raw)
    migration = _version_two(
        "CREATE TABLE partial_table (id INTEGER PRIMARY KEY)",
        "CREATE INDEX failure_marker ON missing_table (id)",
    )
    plan = POSTGRES_MIGRATIONS + (migration,)
    runner.apply(POSTGRES_MIGRATIONS, applied_at=NOW)
    before = (deepcopy(raw.metadata), deepcopy(raw.history), deepcopy(raw.applied_ddl))
    with pytest.raises(ProductionMigrationApplyError, match="transaction failed") as error:
        runner.apply(plan, applied_at=NOW)
    assert "password" not in str(error.value)
    assert (raw.metadata, raw.history, raw.applied_ddl) == before
    assert raw.pending_ddl == []
    assert raw.pending_history == []
    assert raw.rollbacks == 1


def test_read_only_and_autocommit_connections_are_rejected_before_sql():
    raw = FakeMigrationConnection()
    runner = ProductionMigrationRunner(raw, read_only=True)
    with pytest.raises(ProductionMigrationReadOnlyError, match="read-only"):
        runner.apply(POSTGRES_MIGRATIONS, applied_at=NOW)
    assert raw.queries == []

    with pytest.raises(ValueError, match="disable autocommit"):
        ProductionMigrationRunner(FakeMigrationConnection(autocommit=True))


def test_noncanonical_history_timestamp_fails_integrity_validation():
    migration = POSTGRES_MIGRATIONS[0]
    raw = FakeMigrationConnection(
        tables_present=True,
        metadata=(1, POSTGRES_SCHEMA_CHECKSUM),
        history=[
            (1, migration.name, migration.checksum, "2026-10-03T17:00:00+00:00")
        ],
    )
    with pytest.raises(ProductionMigrationIntegrityError, match="canonical UTC"):
        ProductionMigrationRunner(raw).apply(POSTGRES_MIGRATIONS, applied_at=NOW)
    assert raw.commits == 0
    assert raw.rollbacks == 1
