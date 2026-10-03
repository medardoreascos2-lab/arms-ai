"""Forward-only transactional migrations for the isolated Phase 3 store."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import re
import sqlite3


_HASH = re.compile(r"^[0-9a-f]{64}$")
_NAME = re.compile(r"^[a-z][a-z0-9_]{0,127}$")
_DESTRUCTIVE = re.compile(
    r"\b(DROP|DELETE|UPDATE|INSERT|REPLACE|VACUUM|ATTACH|DETACH|PRAGMA|"
    r"REINDEX|TRUNCATE)\b",
    re.IGNORECASE,
)


class MigrationError(RuntimeError):
    """Base error for Phase 3 schema migration failures."""


class MigrationIntegrityError(MigrationError):
    """Stored schema metadata or migration history is invalid."""


class MigrationForwardOnlyError(MigrationError):
    """The requested plan would require a downgrade or contains a gap."""


class MigrationApplyError(MigrationError):
    """A pending migration failed and its transaction was rolled back."""


def _canonical_utc(value: datetime, name: str) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def _validate_stored_utc(value: object, name: str) -> None:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise MigrationIntegrityError(f"{name} is not canonical UTC")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise MigrationIntegrityError(f"{name} is invalid") from exc
    if _canonical_utc(parsed, name) != value:
        raise MigrationIntegrityError(f"{name} is not canonical UTC")


def _validate_forward_statement(statement: str) -> None:
    if not isinstance(statement, str) or not statement or statement != statement.strip():
        raise ValueError("migration statements must be nonempty stripped strings")
    if "--" in statement or "/*" in statement or "*/" in statement:
        raise ValueError("migration SQL comments are forbidden")
    if _DESTRUCTIVE.search(statement) is not None:
        raise ValueError("destructive or data-mutating migration SQL is forbidden")
    normalized = " ".join(statement.upper().split())
    create_allowed = normalized.startswith((
        "CREATE TABLE ",
        "CREATE INDEX ",
        "CREATE UNIQUE INDEX ",
        "CREATE TRIGGER ",
    ))
    alter_allowed = normalized.startswith("ALTER TABLE ") and " ADD COLUMN " in normalized
    if not (create_allowed or alter_allowed):
        raise ValueError("migration SQL must create an object or add a column")


@dataclass(frozen=True)
class Phase3Migration:
    version: int
    name: str
    statements: tuple[str, ...]

    def __post_init__(self) -> None:
        if type(self.version) is not int or self.version < 2:
            raise ValueError("migration version must be an integer of at least 2")
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
class MigrationApplyResult:
    from_version: int
    to_version: int
    applied_versions: tuple[int, ...]
    changed: bool
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)
    canonical_admin_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if any(type(value) is not int or value < 1 for value in (
            self.from_version, self.to_version
        )):
            raise ValueError("migration result versions must be positive integers")
        if not isinstance(self.applied_versions, tuple) or any(
            type(value) is not int for value in self.applied_versions
        ):
            raise ValueError("applied_versions must be an immutable integer tuple")
        if type(self.changed) is not bool:
            raise ValueError("changed must be boolean")
        if self.changed != bool(self.applied_versions):
            raise ValueError("changed must match applied_versions")
        if self.to_version < self.from_version:
            raise ValueError("migration results cannot move backward")
        expected = tuple(range(self.from_version + 1, self.to_version + 1))
        if self.applied_versions != expected:
            raise ValueError("applied_versions must exactly cover the forward range")


def validate_migration_plan(
    migrations: tuple[Phase3Migration, ...],
) -> tuple[Phase3Migration, ...]:
    if not isinstance(migrations, tuple):
        raise ValueError("migrations must be an immutable tuple")
    expected = 2
    names: set[str] = set()
    for migration in migrations:
        if not isinstance(migration, Phase3Migration):
            raise ValueError("migration plan contains an invalid entry")
        if migration.version != expected:
            raise MigrationForwardOnlyError("migration versions must be contiguous from 2")
        if migration.name in names:
            raise ValueError("migration names must be unique")
        names.add(migration.name)
        expected += 1
    return migrations


def migration_chain_checksum(
    bootstrap_checksum: str,
    migrations: tuple[Phase3Migration, ...],
) -> str:
    if not isinstance(bootstrap_checksum, str) or _HASH.fullmatch(bootstrap_checksum) is None:
        raise ValueError("bootstrap_checksum must be a lowercase sha256 digest")
    validated = validate_migration_plan(migrations)
    current = bootstrap_checksum
    for migration in validated:
        current = hashlib.sha256(
            f"{current}:{migration.version}:{migration.checksum}".encode("ascii")
        ).hexdigest()
    return current


def _read_state(
    connection: sqlite3.Connection,
) -> tuple[tuple[object, ...], list[tuple[object, ...]]]:
    try:
        metadata = connection.execute(
            """
            SELECT store_format, schema_version, schema_checksum, created_at
            FROM phase3_store_metadata WHERE singleton = 1
            """
        ).fetchone()
        history = connection.execute(
            """
            SELECT version, name, checksum, applied_at
            FROM phase3_schema_migrations ORDER BY version
            """
        ).fetchall()
    except sqlite3.DatabaseError as exc:
        raise MigrationIntegrityError("invalid phase3 migration schema") from exc
    if metadata is None:
        raise MigrationIntegrityError("phase3 store metadata is missing")
    return metadata, history


def apply_phase3_migrations(
    connection: sqlite3.Connection,
    *,
    store_format: str,
    bootstrap_checksum: str,
    migrations: tuple[Phase3Migration, ...],
    applied_at: datetime,
) -> MigrationApplyResult:
    """Validate history and atomically apply all pending forward migrations."""
    if not isinstance(connection, sqlite3.Connection):
        raise ValueError("connection must be a sqlite3.Connection")
    if connection.in_transaction:
        raise MigrationApplyError(
            "migration requires a connection without an active transaction"
        )
    if not isinstance(store_format, str) or not store_format:
        raise ValueError("store_format must be nonempty")
    if not isinstance(bootstrap_checksum, str) or _HASH.fullmatch(bootstrap_checksum) is None:
        raise ValueError("bootstrap_checksum must be a lowercase sha256 digest")
    plan = validate_migration_plan(migrations)
    applied_text = _canonical_utc(applied_at, "applied_at")
    try:
        connection.execute("BEGIN IMMEDIATE")
        metadata, history = _read_state(connection)
        stored_format, current_version, current_checksum, created_at = metadata
        if stored_format != store_format:
            raise MigrationIntegrityError("phase3 store format mismatch")
        if type(current_version) is not int or current_version < 1:
            raise MigrationIntegrityError("invalid current schema version")
        if not isinstance(current_checksum, str) or _HASH.fullmatch(current_checksum) is None:
            raise MigrationIntegrityError("invalid current schema checksum")
        _validate_stored_utc(created_at, "created_at")
        if connection.execute("PRAGMA foreign_keys").fetchone() != (1,):
            raise MigrationIntegrityError("foreign-key enforcement is disabled")
        if connection.execute("PRAGMA quick_check").fetchone() != ("ok",):
            raise MigrationIntegrityError("phase3 store quick_check failed")

        target_version = 1 + len(plan)
        if current_version > target_version:
            raise MigrationForwardOnlyError(
                "store schema is newer than the migration plan"
            )
        if len(history) != current_version:
            raise MigrationIntegrityError("migration history is incomplete")
        expected_history = [(1, "phase3_bootstrap", bootstrap_checksum)]
        expected_history.extend(
            (migration.version, migration.name, migration.checksum)
            for migration in plan[: current_version - 1]
        )
        for index, row in enumerate(history):
            if len(row) != 4 or row[:3] != expected_history[index]:
                raise MigrationIntegrityError("migration history checksum mismatch")
            _validate_stored_utc(row[3], f"migration_{row[0]}_applied_at")
        expected_current_checksum = migration_chain_checksum(
            bootstrap_checksum, plan[: current_version - 1]
        )
        if current_checksum != expected_current_checksum:
            raise MigrationIntegrityError("current schema checksum mismatch")

        pending = plan[current_version - 1 :]
        if not pending:
            connection.execute("COMMIT")
            return MigrationApplyResult(
                from_version=current_version,
                to_version=current_version,
                applied_versions=(),
                changed=False,
            )

        for migration in pending:
            for statement in migration.statements:
                connection.execute(statement)
            connection.execute(
                """
                INSERT INTO phase3_schema_migrations(
                    version, name, checksum, applied_at
                ) VALUES (?, ?, ?, ?)
                """,
                (migration.version, migration.name, migration.checksum, applied_text),
            )
        final_checksum = migration_chain_checksum(bootstrap_checksum, plan)
        connection.execute(
            """
            UPDATE phase3_store_metadata
            SET schema_version = ?, schema_checksum = ?
            WHERE singleton = 1
            """,
            (target_version, final_checksum),
        )
        connection.execute("COMMIT")
    except (MigrationIntegrityError, MigrationForwardOnlyError):
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise
    except sqlite3.DatabaseError as exc:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise MigrationApplyError("phase3 migration transaction failed") from exc
    except BaseException:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise

    return MigrationApplyResult(
        from_version=current_version,
        to_version=target_version,
        applied_versions=tuple(item.version for item in pending),
        changed=True,
    )
