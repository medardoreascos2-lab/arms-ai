"""Isolated SQLite persistence for canonical Phase 3 state records."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3

from .financial_serialization import (
    canonical_decimal_text,
    deserialize_state_record,
    serialize_state_record,
    verify_serialized_hash,
)
from .state_contracts import DurableStateRecord
from .storage_migrations import (
    MigrationError,
    Phase3Migration,
    apply_phase3_migrations,
    migration_chain_checksum,
)


STORE_FORMAT = "arms.phase3.sqlite-state-store"
_BOOTSTRAP_SCHEMA_VERSION = 1

_SCHEMA_OBJECTS_SQL = """
CREATE TABLE phase3_store_metadata (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    store_format TEXT NOT NULL,
    schema_version INTEGER NOT NULL CHECK (schema_version > 0),
    schema_checksum TEXT NOT NULL CHECK (length(schema_checksum) = 64),
    created_at TEXT NOT NULL
);

CREATE TABLE phase3_schema_migrations (
    version INTEGER PRIMARY KEY CHECK (version > 0),
    name TEXT NOT NULL UNIQUE,
    checksum TEXT NOT NULL CHECK (length(checksum) = 64),
    applied_at TEXT NOT NULL
);

CREATE TABLE phase3_tenants (
    tenant_id TEXT PRIMARY KEY,
    first_recorded_at TEXT NOT NULL
);

CREATE TABLE phase3_accounts (
    tenant_id TEXT NOT NULL,
    account_id TEXT NOT NULL,
    first_recorded_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, account_id),
    FOREIGN KEY (tenant_id) REFERENCES phase3_tenants(tenant_id)
);

CREATE TABLE phase3_users (
    tenant_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    first_recorded_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, user_id),
    FOREIGN KEY (tenant_id) REFERENCES phase3_tenants(tenant_id)
);

CREATE TABLE phase3_profiles (
    config_hash TEXT PRIMARY KEY CHECK (length(config_hash) = 64),
    firm_id TEXT NOT NULL,
    program_id TEXT NOT NULL,
    stage TEXT NOT NULL,
    profile_version TEXT NOT NULL,
    account_size_payload BLOB NOT NULL,
    first_recorded_at TEXT NOT NULL
);

CREATE TABLE phase3_state_records (
    tenant_id TEXT NOT NULL,
    record_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    schema_namespace TEXT NOT NULL,
    schema_name TEXT NOT NULL,
    schema_version INTEGER NOT NULL CHECK (schema_version > 0),
    observed_at TEXT NOT NULL,
    committed_at TEXT NOT NULL,
    source_id TEXT NOT NULL,
    source_version TEXT NOT NULL,
    source_simulated INTEGER NOT NULL CHECK (source_simulated IN (0, 1)),
    user_id TEXT,
    account_id TEXT,
    profile_config_hash TEXT,
    payload BLOB NOT NULL,
    payload_sha256 TEXT NOT NULL CHECK (length(payload_sha256) = 64),
    PRIMARY KEY (tenant_id, record_id),
    FOREIGN KEY (tenant_id) REFERENCES phase3_tenants(tenant_id),
    FOREIGN KEY (tenant_id, account_id)
        REFERENCES phase3_accounts(tenant_id, account_id),
    FOREIGN KEY (tenant_id, user_id)
        REFERENCES phase3_users(tenant_id, user_id),
    FOREIGN KEY (profile_config_hash)
        REFERENCES phase3_profiles(config_hash)
);

CREATE INDEX phase3_records_kind_time
    ON phase3_state_records(tenant_id, kind, observed_at, record_id);
CREATE INDEX phase3_records_account_time
    ON phase3_state_records(tenant_id, account_id, observed_at, record_id);

CREATE TRIGGER phase3_records_no_update
BEFORE UPDATE ON phase3_state_records
BEGIN
    SELECT RAISE(ABORT, 'phase3 state records are append-only');
END;
CREATE TRIGGER phase3_records_no_delete
BEFORE DELETE ON phase3_state_records
BEGIN
    SELECT RAISE(ABORT, 'phase3 state records are append-only');
END;
CREATE TRIGGER phase3_migrations_no_update
BEFORE UPDATE ON phase3_schema_migrations
BEGIN
    SELECT RAISE(ABORT, 'phase3 migrations are append-only');
END;
CREATE TRIGGER phase3_migrations_no_delete
BEFORE DELETE ON phase3_schema_migrations
BEGIN
    SELECT RAISE(ABORT, 'phase3 migrations are append-only');
END;
""".strip()

_BOOTSTRAP_SCHEMA_CHECKSUM = hashlib.sha256(
    _SCHEMA_OBJECTS_SQL.encode("utf-8")
).hexdigest()

STORE_MIGRATIONS = (
    Phase3Migration(
        version=2,
        name="record_commit_time_index",
        statements=(
            "CREATE INDEX phase3_records_commit_time "
            "ON phase3_state_records(tenant_id, committed_at, record_id)",
        ),
    ),
    Phase3Migration(
        version=3,
        name="account_snapshot_repository",
        statements=(
            """CREATE TABLE phase3_account_snapshots (
                tenant_id TEXT NOT NULL,
                snapshot_id TEXT NOT NULL,
                account_id TEXT NOT NULL,
                source_id TEXT NOT NULL,
                source_version TEXT NOT NULL,
                source_simulated INTEGER NOT NULL CHECK (source_simulated IN (0, 1)),
                profile_config_hash TEXT NOT NULL,
                currency TEXT NOT NULL CHECK (length(currency) = 3),
                sequence INTEGER NOT NULL CHECK (sequence > 0),
                captured_at TEXT NOT NULL,
                received_at TEXT NOT NULL,
                stored_at TEXT NOT NULL,
                snapshot_hash TEXT NOT NULL CHECK (length(snapshot_hash) = 64),
                payload BLOB NOT NULL,
                payload_sha256 TEXT NOT NULL CHECK (length(payload_sha256) = 64),
                PRIMARY KEY (tenant_id, snapshot_id),
                UNIQUE (
                    tenant_id, account_id, source_id, source_version, source_simulated,
                    profile_config_hash, currency, sequence
                ),
                FOREIGN KEY (tenant_id) REFERENCES phase3_tenants(tenant_id),
                FOREIGN KEY (tenant_id, account_id)
                    REFERENCES phase3_accounts(tenant_id, account_id),
                FOREIGN KEY (profile_config_hash)
                    REFERENCES phase3_profiles(config_hash)
            )""",
            """CREATE INDEX phase3_snapshots_latest
                ON phase3_account_snapshots(
                    tenant_id, account_id, source_id, source_version, source_simulated,
                    profile_config_hash, currency, sequence DESC
                )""",
            """CREATE INDEX phase3_snapshots_captured_time
                ON phase3_account_snapshots(
                    tenant_id, account_id, source_id, source_version, source_simulated,
                    profile_config_hash, currency, captured_at, sequence
                )""",
            """CREATE TRIGGER phase3_snapshots_no_update
                BEFORE UPDATE ON phase3_account_snapshots
                BEGIN SELECT RAISE(ABORT, 'phase3 snapshots are append only'); END""",
            """CREATE TRIGGER phase3_snapshots_no_delete
                BEFORE DELETE ON phase3_account_snapshots
                BEGIN SELECT RAISE(ABORT, 'phase3 snapshots are append only'); END""",
        ),
    ),
)
STORE_SCHEMA_VERSION = _BOOTSTRAP_SCHEMA_VERSION + len(STORE_MIGRATIONS)
STORE_SCHEMA_CHECKSUM = migration_chain_checksum(
    _BOOTSTRAP_SCHEMA_CHECKSUM, STORE_MIGRATIONS
)

_REQUIRED_SCHEMA_OBJECTS = frozenset({
    ("index", "phase3_records_account_time"),
    ("index", "phase3_records_commit_time"),
    ("index", "phase3_records_kind_time"),
    ("index", "phase3_snapshots_captured_time"),
    ("index", "phase3_snapshots_latest"),
    ("table", "phase3_accounts"),
    ("table", "phase3_account_snapshots"),
    ("table", "phase3_profiles"),
    ("table", "phase3_schema_migrations"),
    ("table", "phase3_state_records"),
    ("table", "phase3_store_metadata"),
    ("table", "phase3_tenants"),
    ("table", "phase3_users"),
    ("trigger", "phase3_migrations_no_delete"),
    ("trigger", "phase3_migrations_no_update"),
    ("trigger", "phase3_records_no_delete"),
    ("trigger", "phase3_records_no_update"),
    ("trigger", "phase3_snapshots_no_delete"),
    ("trigger", "phase3_snapshots_no_update"),
})


class DurableStoreError(RuntimeError):
    """Base error for fail-closed durable store operations."""


class DurableStoreIntegrityError(DurableStoreError):
    """The store or one of its records failed integrity validation."""


class DurableStoreConflictError(DurableStoreError):
    """An immutable identity was reused with different content."""


class DurableStoreReadOnlyError(DurableStoreError):
    """A write was requested through a read-only store handle."""


@dataclass(frozen=True)
class StoreAppendResult:
    record_id: str
    content_hash: str
    inserted: bool
    duplicate: bool
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)
    canonical_admin_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if type(self.inserted) is not bool or type(self.duplicate) is not bool:
            raise ValueError("inserted and duplicate must be boolean")
        if self.inserted == self.duplicate:
            raise ValueError("append result must be inserted or duplicate")


@dataclass(frozen=True)
class StoredStateRecord:
    record: DurableStateRecord
    content_hash: str
    committed_at: datetime
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)
    canonical_admin_authorized: bool = field(default=False, init=False)


def _canonical_utc(value: datetime, name: str) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def _parse_canonical_utc(value: object, name: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise DurableStoreIntegrityError(f"{name} is not canonical UTC")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise DurableStoreIntegrityError(f"{name} is invalid") from exc
    if _canonical_utc(parsed, name) != value:
        raise DurableStoreIntegrityError(f"{name} is not canonical UTC")
    return parsed


def _profile_account_size_payload(profile: object) -> bytes:
    account_size = getattr(profile, "account_size", None)
    if account_size is None:
        raise ValueError("profile must carry account_size")
    return json.dumps(
        {
            "currency": account_size.currency,
            "unit": account_size.unit.value,
            "value": canonical_decimal_text(account_size.value),
        },
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


class Phase3DurableStateStore:
    """Append-only Phase 3 state store with no execution authority.

    The file is a dedicated Phase 3 database. It never discovers, opens, or
    migrates legacy V8 databases. SQLite transactions, foreign keys, WAL, and
    FULL synchronous mode define the initial crash recovery boundary.
    """

    execution_authorized = False
    production_mutation_authorized = False
    canonical_admin_authorized = False

    def __init__(self, path: Path, connection: sqlite3.Connection, *, read_only: bool):
        self.path = path
        self._connection = connection
        self.read_only = read_only
        self._closed = False

    @classmethod
    def create(cls, path: str | Path) -> "Phase3DurableStateStore":
        resolved = Path(path).expanduser().resolve()
        if resolved.exists():
            raise DurableStoreConflictError("phase3 store already exists")
        resolved.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(resolved, isolation_level=None)
        try:
            cls._configure_writable(connection)
            cls._bootstrap(connection)
            cls._migrate(connection)
            cls._verify_connection(connection)
        except BaseException:
            connection.close()
            raise
        return cls(resolved, connection, read_only=False)

    @classmethod
    def open(
        cls, path: str | Path, *, read_only: bool = False
    ) -> "Phase3DurableStateStore":
        resolved = Path(path).expanduser().resolve()
        if not resolved.is_file():
            raise DurableStoreIntegrityError("phase3 store does not exist")
        if read_only:
            connection = sqlite3.connect(
                resolved.as_uri() + "?mode=ro", uri=True, isolation_level=None
            )
            connection.execute("PRAGMA query_only=ON")
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=5000")
        else:
            connection = sqlite3.connect(resolved, isolation_level=None)
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=5000")
        try:
            if not read_only:
                cls._migrate(connection)
            cls._verify_connection(connection)
            if not read_only:
                cls._configure_writable(connection)
        except BaseException:
            connection.close()
            raise
        return cls(resolved, connection, read_only=read_only)

    @staticmethod
    def _configure_writable(connection: sqlite3.Connection) -> None:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("PRAGMA busy_timeout=5000")

    @staticmethod
    def _bootstrap(connection: sqlite3.Connection) -> None:
        applied_at = datetime.now(timezone.utc).isoformat(
            timespec="microseconds"
        ).replace("+00:00", "Z")
        try:
            connection.executescript("BEGIN IMMEDIATE;\n" + _SCHEMA_OBJECTS_SQL)
            connection.execute(
                """
                INSERT INTO phase3_store_metadata(
                    singleton, store_format, schema_version,
                    schema_checksum, created_at
                ) VALUES (1, ?, ?, ?, ?)
                """,
                (
                    STORE_FORMAT,
                    _BOOTSTRAP_SCHEMA_VERSION,
                    _BOOTSTRAP_SCHEMA_CHECKSUM,
                    applied_at,
                ),
            )
            connection.execute(
                """
                INSERT INTO phase3_schema_migrations(
                    version, name, checksum, applied_at
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    _BOOTSTRAP_SCHEMA_VERSION,
                    "phase3_bootstrap",
                    _BOOTSTRAP_SCHEMA_CHECKSUM,
                    applied_at,
                ),
            )
            connection.execute("COMMIT")
        except BaseException:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise

    @staticmethod
    def _migrate(connection: sqlite3.Connection) -> None:
        try:
            apply_phase3_migrations(
                connection,
                store_format=STORE_FORMAT,
                bootstrap_checksum=_BOOTSTRAP_SCHEMA_CHECKSUM,
                migrations=STORE_MIGRATIONS,
                applied_at=datetime.now(timezone.utc),
            )
        except MigrationError as exc:
            raise DurableStoreIntegrityError(
                f"phase3 store migration validation failed: {exc}"
            ) from exc

    @staticmethod
    def _verify_connection(connection: sqlite3.Connection) -> None:
        try:
            check = connection.execute("PRAGMA quick_check").fetchone()
            metadata = connection.execute(
                """
                SELECT store_format, schema_version, schema_checksum, created_at
                FROM phase3_store_metadata WHERE singleton = 1
                """
            ).fetchone()
            migrations = connection.execute(
                """
                SELECT version, name, checksum, applied_at
                FROM phase3_schema_migrations
                ORDER BY version
                """
            ).fetchall()
            schema_objects = frozenset(connection.execute(
                """
                SELECT type, name FROM sqlite_master
                WHERE name GLOB 'phase3_*'
                """
            ).fetchall())
        except sqlite3.DatabaseError as exc:
            raise DurableStoreIntegrityError("invalid phase3 store schema") from exc
        if check != ("ok",):
            raise DurableStoreIntegrityError("phase3 store quick_check failed")
        if metadata is None or metadata[:3] != (
            STORE_FORMAT,
            STORE_SCHEMA_VERSION,
            STORE_SCHEMA_CHECKSUM,
        ):
            raise DurableStoreIntegrityError("phase3 store metadata mismatch")
        _parse_canonical_utc(metadata[3], "created_at")
        expected_migrations = [(
            _BOOTSTRAP_SCHEMA_VERSION,
            "phase3_bootstrap",
            _BOOTSTRAP_SCHEMA_CHECKSUM,
        )]
        expected_migrations.extend(
            (migration.version, migration.name, migration.checksum)
            for migration in STORE_MIGRATIONS
        )
        if [row[:3] for row in migrations] != expected_migrations:
            raise DurableStoreIntegrityError("phase3 migration history mismatch")
        for version, _, _, applied_at in migrations:
            _parse_canonical_utc(applied_at, f"migration_{version}_applied_at")
        if schema_objects != _REQUIRED_SCHEMA_OBJECTS:
            raise DurableStoreIntegrityError("phase3 schema objects mismatch")
        foreign_keys = connection.execute("PRAGMA foreign_keys").fetchone()
        if foreign_keys != (1,):
            raise DurableStoreIntegrityError("foreign-key enforcement is disabled")

    def _require_open(self) -> sqlite3.Connection:
        if self._closed:
            raise DurableStoreError("phase3 store is closed")
        return self._connection

    def close(self) -> None:
        if not self._closed:
            self._connection.close()
            self._closed = True

    def __enter__(self) -> "Phase3DurableStateStore":
        self._require_open()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    @property
    def schema_version(self) -> int:
        connection = self._require_open()
        row = connection.execute(
            "SELECT schema_version FROM phase3_store_metadata WHERE singleton = 1"
        ).fetchone()
        if row is None or type(row[0]) is not int:
            raise DurableStoreIntegrityError("missing phase3 schema version")
        return row[0]

    def append(
        self, record: DurableStateRecord, *, committed_at: datetime
    ) -> StoreAppendResult:
        connection = self._require_open()
        if self.read_only:
            raise DurableStoreReadOnlyError("phase3 store is read-only")
        if not isinstance(record, DurableStateRecord):
            raise ValueError("record must be a DurableStateRecord")
        committed_text = _canonical_utc(committed_at, "committed_at")
        observed_text = _canonical_utc(record.observed_at, "observed_at")
        if committed_at.astimezone(timezone.utc) < record.observed_at.astimezone(timezone.utc):
            raise ValueError("committed_at cannot precede observed_at")
        payload = serialize_state_record(record)
        content_hash = hashlib.sha256(payload).hexdigest()
        tenant_id = record.tenant.tenant_id

        try:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                """
                SELECT payload_sha256 FROM phase3_state_records
                WHERE tenant_id = ? AND record_id = ?
                """,
                (tenant_id, record.record_id),
            ).fetchone()
            if existing is not None:
                if existing != (content_hash,):
                    raise DurableStoreConflictError(
                        "record identity already has different immutable content"
                    )
                connection.execute("COMMIT")
                return StoreAppendResult(
                    record.record_id, content_hash, inserted=False, duplicate=True
                )

            connection.execute(
                "INSERT OR IGNORE INTO phase3_tenants VALUES (?, ?)",
                (tenant_id, committed_text),
            )
            if record.account is not None:
                connection.execute(
                    "INSERT OR IGNORE INTO phase3_accounts VALUES (?, ?, ?)",
                    (tenant_id, record.account.account_id, committed_text),
                )
            if record.user is not None:
                connection.execute(
                    "INSERT OR IGNORE INTO phase3_users VALUES (?, ?, ?)",
                    (tenant_id, record.user.user_id, committed_text),
                )
            profile_hash = None
            if record.profile is not None:
                profile_hash = record.profile.config_hash
                profile_payload = _profile_account_size_payload(record.profile)
                connection.execute(
                    """
                    INSERT OR IGNORE INTO phase3_profiles(
                        config_hash, firm_id, program_id, stage, profile_version,
                        account_size_payload, first_recorded_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        profile_hash,
                        record.profile.firm_id,
                        record.profile.program_id,
                        record.profile.stage,
                        record.profile.profile_version,
                        profile_payload,
                        committed_text,
                    ),
                )
                saved_profile = connection.execute(
                    """
                    SELECT firm_id, program_id, stage, profile_version,
                           account_size_payload
                    FROM phase3_profiles WHERE config_hash = ?
                    """,
                    (profile_hash,),
                ).fetchone()
                if saved_profile != (
                    record.profile.firm_id,
                    record.profile.program_id,
                    record.profile.stage,
                    record.profile.profile_version,
                    profile_payload,
                ):
                    raise DurableStoreConflictError("profile hash identity conflict")

            connection.execute(
                """
                INSERT INTO phase3_state_records(
                    tenant_id, record_id, kind, schema_namespace, schema_name,
                    schema_version, observed_at, committed_at, source_id,
                    source_version, source_simulated, user_id, account_id,
                    profile_config_hash, payload, payload_sha256
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tenant_id,
                    record.record_id,
                    record.kind.value,
                    record.schema.namespace,
                    record.schema.name,
                    record.schema.version,
                    observed_text,
                    committed_text,
                    record.source.source_id,
                    record.source.source_version,
                    int(record.source.simulated),
                    record.user.user_id if record.user is not None else None,
                    record.account.account_id if record.account is not None else None,
                    profile_hash,
                    payload,
                    content_hash,
                ),
            )
            connection.execute("COMMIT")
        except BaseException:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        return StoreAppendResult(
            record.record_id, content_hash, inserted=True, duplicate=False
        )

    def get(self, *, tenant_id: str, record_id: str) -> StoredStateRecord | None:
        connection = self._require_open()
        row = connection.execute(
            """
            SELECT payload, payload_sha256, committed_at, kind,
                   schema_namespace, schema_name, schema_version, observed_at,
                   source_id, source_version, source_simulated, user_id,
                   account_id, profile_config_hash
            FROM phase3_state_records
            WHERE tenant_id = ? AND record_id = ?
            """,
            (tenant_id, record_id),
        ).fetchone()
        if row is None:
            return None
        (
            payload, content_hash, committed_at, kind, schema_namespace,
            schema_name, schema_version, observed_at, source_id,
            source_version, source_simulated, user_id, account_id,
            profile_config_hash,
        ) = row
        if not isinstance(payload, bytes) or not verify_serialized_hash(
            payload, content_hash
        ):
            raise DurableStoreIntegrityError("stored record hash mismatch")
        try:
            record = deserialize_state_record(payload)
        except ValueError as exc:
            raise DurableStoreIntegrityError("stored record is invalid") from exc
        if record.tenant.tenant_id != tenant_id or record.record_id != record_id:
            raise DurableStoreIntegrityError("stored record scope mismatch")
        expected_columns = (
            record.kind.value,
            record.schema.namespace,
            record.schema.name,
            record.schema.version,
            _canonical_utc(record.observed_at, "observed_at"),
            record.source.source_id,
            record.source.source_version,
            int(record.source.simulated),
            record.user.user_id if record.user is not None else None,
            record.account.account_id if record.account is not None else None,
            record.profile.config_hash if record.profile is not None else None,
        )
        if expected_columns != (
            kind, schema_namespace, schema_name, schema_version, observed_at,
            source_id, source_version, source_simulated, user_id, account_id,
            profile_config_hash,
        ):
            raise DurableStoreIntegrityError("stored record index mismatch")
        return StoredStateRecord(
            record=record,
            content_hash=content_hash,
            committed_at=_parse_canonical_utc(committed_at, "committed_at"),
        )

    def count(self, *, tenant_id: str | None = None) -> int:
        connection = self._require_open()
        if tenant_id is None:
            row = connection.execute(
                "SELECT COUNT(*) FROM phase3_state_records"
            ).fetchone()
        else:
            row = connection.execute(
                "SELECT COUNT(*) FROM phase3_state_records WHERE tenant_id = ?",
                (tenant_id,),
            ).fetchone()
        if row is None or type(row[0]) is not int:
            raise DurableStoreIntegrityError("invalid record count")
        return row[0]
