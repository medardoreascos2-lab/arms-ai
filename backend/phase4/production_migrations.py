"""Forward-only PostgreSQL schema migrations with containerless execution seams."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Protocol

from .postgresql_adapter import POSTGRES_TABLES


_HASH = re.compile(r"^[0-9a-f]{64}$")
_NAME = re.compile(r"^[a-z][a-z0-9_]{0,127}$")
_FORBIDDEN_SQL = re.compile(
    r"\b(DROP|DELETE|UPDATE|INSERT|REPLACE|VACUUM|ATTACH|DETACH|"
    r"REINDEX|TRUNCATE|GRANT|REVOKE|COPY|CALL|EXECUTE)\b",
    re.IGNORECASE,
)
_LOCK_KEY = 1_881_907_044
POSTGRES_EMPTY_SCHEMA_CHECKSUM = hashlib.sha256(
    b"ARMS_PHASE4_POSTGRESQL_EMPTY_SCHEMA_V1"
).hexdigest()


class ProductionMigrationError(RuntimeError):
    """Base error for Phase 4 production schema migration failures."""


class ProductionMigrationIntegrityError(ProductionMigrationError):
    pass


class ProductionMigrationForwardOnlyError(ProductionMigrationError):
    pass


class ProductionMigrationApplyError(ProductionMigrationError):
    pass


class ProductionMigrationReadOnlyError(ProductionMigrationError):
    pass


def _canonical_utc(value: datetime, name: str) -> str:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def _validate_stored_utc(value: object, name: str) -> None:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ProductionMigrationIntegrityError(f"{name} is not canonical UTC")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        raise ProductionMigrationIntegrityError(f"{name} is invalid") from None
    if _canonical_utc(parsed, name) != value:
        raise ProductionMigrationIntegrityError(f"{name} is not canonical UTC")


def _validate_forward_statement(statement: str) -> None:
    if not isinstance(statement, str) or not statement or statement != statement.strip():
        raise ValueError("migration statements must be nonempty stripped strings")
    if ";" in statement or "--" in statement or "/*" in statement or "*/" in statement:
        raise ValueError("migration SQL comments and statement separators are forbidden")
    if _FORBIDDEN_SQL.search(statement) is not None:
        raise ValueError("destructive, data-mutating, or authority SQL is forbidden")
    normalized = " ".join(statement.split())
    upper = normalized.upper()
    if " SELECT " in f" {upper} ":
        raise ValueError("migration SQL cannot copy or query runtime data")
    create_allowed = upper.startswith(
        ("CREATE TABLE ", "CREATE INDEX ", "CREATE UNIQUE INDEX ")
    )
    alter_allowed = upper.startswith("ALTER TABLE ") and " ADD COLUMN " in upper
    if not (create_allowed or alter_allowed):
        raise ValueError("migration SQL must create an object or add a column")


@dataclass(frozen=True)
class PostgresMigration:
    version: int
    name: str
    statements: tuple[str, ...]

    def __post_init__(self) -> None:
        if type(self.version) is not int or self.version < 1:
            raise ValueError("migration version must be a positive integer")
        if not isinstance(self.name, str) or _NAME.fullmatch(self.name) is None:
            raise ValueError("migration name must be a lowercase identifier")
        if not isinstance(self.statements, tuple) or not self.statements:
            raise ValueError("migration statements must be a nonempty tuple")
        for statement in self.statements:
            _validate_forward_statement(statement)

    @property
    def checksum(self) -> str:
        payload = json.dumps(
            {
                "name": self.name,
                "statements": self.statements,
                "version": self.version,
            },
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
        return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class ProductionMigrationResult:
    from_version: int
    to_version: int
    applied_versions: tuple[int, ...]
    changed: bool
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if any(
            type(value) is not int or value < 0
            for value in (self.from_version, self.to_version)
        ):
            raise ValueError("migration result versions must be nonnegative integers")
        if not isinstance(self.applied_versions, tuple) or any(
            type(value) is not int for value in self.applied_versions
        ):
            raise ValueError("applied_versions must be an immutable integer tuple")
        if type(self.changed) is not bool or self.changed != bool(self.applied_versions):
            raise ValueError("changed must match applied_versions")
        if self.to_version < self.from_version:
            raise ValueError("migration results cannot move backward")
        expected = tuple(range(self.from_version + 1, self.to_version + 1))
        if self.applied_versions != expected:
            raise ValueError("applied_versions must exactly cover the forward range")


def validate_postgres_migration_plan(
    migrations: tuple[PostgresMigration, ...],
) -> tuple[PostgresMigration, ...]:
    if not isinstance(migrations, tuple) or not migrations:
        raise ValueError("migrations must be a nonempty immutable tuple")
    names: set[str] = set()
    for expected, migration in enumerate(migrations, start=1):
        if not isinstance(migration, PostgresMigration):
            raise ValueError("migration plan contains an invalid entry")
        if migration.version != expected:
            raise ProductionMigrationForwardOnlyError(
                "migration versions must be contiguous from 1"
            )
        if migration.name in names:
            raise ValueError("migration names must be unique")
        names.add(migration.name)
    return migrations


def postgres_migration_chain_checksum(
    migrations: tuple[PostgresMigration, ...],
) -> str:
    current = POSTGRES_EMPTY_SCHEMA_CHECKSUM
    for migration in validate_postgres_migration_plan(migrations):
        current = hashlib.sha256(
            f"{current}:{migration.version}:{migration.checksum}".encode("ascii")
        ).hexdigest()
    return current


class ProductionMigrationCursor(Protocol):
    def execute(self, query: str, parameters: tuple[object, ...] = ()) -> object: ...

    def fetchone(self) -> tuple[object, ...] | None: ...

    def fetchall(self) -> list[tuple[object, ...]]: ...

    def close(self) -> None: ...


class ProductionMigrationConnection(Protocol):
    autocommit: bool

    def cursor(self) -> ProductionMigrationCursor: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...


def _record_table_statement(table_name: str) -> str:
    return (
        f"CREATE TABLE {table_name} ("
        "tenant_id TEXT NOT NULL, record_id TEXT NOT NULL, payload BYTEA NOT NULL, "
        "payload_sha256 CHAR(64) NOT NULL, occurred_at TEXT NOT NULL, "
        "stored_at TEXT NOT NULL, PRIMARY KEY (tenant_id, record_id))"
    )


POSTGRES_MIGRATIONS = (
    PostgresMigration(
        version=1,
        name="phase4_postgresql_bootstrap",
        statements=(
            "CREATE TABLE phase4_store_metadata (singleton BOOLEAN PRIMARY KEY, "
            "schema_version INTEGER NOT NULL, schema_checksum CHAR(64) NOT NULL, "
            "created_at TEXT NOT NULL, updated_at TEXT NOT NULL, CHECK (singleton))",
            "CREATE TABLE phase4_schema_migrations (version INTEGER PRIMARY KEY, "
            "name TEXT NOT NULL UNIQUE, checksum CHAR(64) NOT NULL, "
            "applied_at TEXT NOT NULL)",
        )
        + tuple(_record_table_statement(table) for table in POSTGRES_TABLES),
    ),
)
POSTGRES_SCHEMA_VERSION = POSTGRES_MIGRATIONS[-1].version
POSTGRES_SCHEMA_CHECKSUM = postgres_migration_chain_checksum(POSTGRES_MIGRATIONS)


class ProductionMigrationRunner:
    """Apply a complete PostgreSQL migration plan in one driver transaction."""

    execution_authorized = False
    production_mutation_authorized = False

    def __init__(
        self,
        connection: ProductionMigrationConnection,
        *,
        read_only: bool = False,
    ):
        if connection is None or not callable(getattr(connection, "cursor", None)):
            raise ValueError("connection must provide a DB-API cursor")
        if getattr(connection, "autocommit", None) is not False:
            raise ValueError("migration connection must disable autocommit")
        if type(read_only) is not bool:
            raise ValueError("read_only must be boolean")
        self._connection = connection
        self.read_only = read_only

    def _rollback(self) -> None:
        try:
            self._connection.rollback()
        except Exception:
            pass

    def apply(
        self,
        migrations: tuple[PostgresMigration, ...],
        *,
        applied_at: datetime,
    ) -> ProductionMigrationResult:
        if self.read_only:
            raise ProductionMigrationReadOnlyError(
                "read-only connections cannot run migrations"
            )
        plan = validate_postgres_migration_plan(migrations)
        applied_text = _canonical_utc(applied_at, "applied_at")
        cursor = self._connection.cursor()
        try:
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", (_LOCK_KEY,))
            cursor.execute("SELECT to_regclass(%s)", ("phase4_store_metadata",))
            registration = cursor.fetchone()
            if registration is None or len(registration) != 1:
                raise ProductionMigrationIntegrityError(
                    "PostgreSQL schema registration result is invalid"
                )

            if registration[0] is None:
                current_version = 0
                current_checksum = POSTGRES_EMPTY_SCHEMA_CHECKSUM
                history: list[tuple[object, ...]] = []
            else:
                cursor.execute(
                    "SELECT schema_version, schema_checksum FROM "
                    "phase4_store_metadata WHERE singleton = TRUE"
                )
                metadata = cursor.fetchone()
                cursor.execute(
                    "SELECT version, name, checksum, applied_at FROM "
                    "phase4_schema_migrations ORDER BY version"
                )
                history = cursor.fetchall()
                if metadata is None or len(metadata) != 2:
                    raise ProductionMigrationIntegrityError(
                        "PostgreSQL schema metadata is missing"
                    )
                current_version, current_checksum = metadata

            target_version = plan[-1].version
            if type(current_version) is not int or current_version < 0:
                raise ProductionMigrationIntegrityError(
                    "PostgreSQL schema version is invalid"
                )
            if current_version > target_version:
                raise ProductionMigrationForwardOnlyError(
                    "database schema is newer than the migration plan"
                )
            if not isinstance(current_checksum, str) or _HASH.fullmatch(
                current_checksum
            ) is None:
                raise ProductionMigrationIntegrityError(
                    "PostgreSQL schema checksum is invalid"
                )
            if len(history) != current_version:
                raise ProductionMigrationIntegrityError(
                    "PostgreSQL migration history is incomplete"
                )
            for index, row in enumerate(history):
                migration = plan[index]
                expected = (migration.version, migration.name, migration.checksum)
                if len(row) != 4 or row[:3] != expected:
                    raise ProductionMigrationIntegrityError(
                        "PostgreSQL migration history checksum mismatch"
                    )
                _validate_stored_utc(row[3], f"migration_{migration.version}_applied_at")

            expected_checksum = (
                POSTGRES_EMPTY_SCHEMA_CHECKSUM
                if current_version == 0
                else postgres_migration_chain_checksum(plan[:current_version])
            )
            if current_checksum != expected_checksum:
                raise ProductionMigrationIntegrityError(
                    "PostgreSQL current schema checksum mismatch"
                )

            pending = plan[current_version:]
            running_checksum = current_checksum
            for migration in pending:
                for statement in migration.statements:
                    cursor.execute(statement)
                running_checksum = hashlib.sha256(
                    f"{running_checksum}:{migration.version}:"
                    f"{migration.checksum}".encode("ascii")
                ).hexdigest()
                cursor.execute(
                    "INSERT INTO phase4_schema_migrations "
                    "(version, name, checksum, applied_at) VALUES (%s, %s, %s, %s)",
                    (
                        migration.version,
                        migration.name,
                        migration.checksum,
                        applied_text,
                    ),
                )
                cursor.execute(
                    "INSERT INTO phase4_store_metadata "
                    "(singleton, schema_version, schema_checksum, created_at, updated_at) "
                    "VALUES (TRUE, %s, %s, %s, %s) "
                    "ON CONFLICT (singleton) DO UPDATE SET "
                    "schema_version = EXCLUDED.schema_version, "
                    "schema_checksum = EXCLUDED.schema_checksum, "
                    "updated_at = EXCLUDED.updated_at",
                    (
                        migration.version,
                        running_checksum,
                        applied_text,
                        applied_text,
                    ),
                )
            self._connection.commit()
        except ProductionMigrationError:
            self._rollback()
            raise
        except Exception:
            self._rollback()
            raise ProductionMigrationApplyError(
                "PostgreSQL migration transaction failed"
            ) from None
        finally:
            try:
                cursor.close()
            except Exception:
                pass

        return ProductionMigrationResult(
            from_version=current_version,
            to_version=target_version,
            applied_versions=tuple(migration.version for migration in pending),
            changed=bool(pending),
        )
