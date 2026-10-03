"""Containerless PostgreSQL adapter foundation for Phase 4 durable records."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import re
from typing import Callable, Protocol

from .database_abstraction import (
    DatabaseAccessMode,
    DatabaseAdapter,
    DatabaseAvailability,
    DatabaseBackend,
    DatabaseCapabilities,
    DatabaseConfigurationError,
    DatabaseConnection,
    DatabaseError,
    DatabaseHealth,
    DatabaseReadOnlyError,
    DatabaseTarget,
    DatabaseTenantIsolationError,
    REQUIRED_CAPABILITIES,
)
from backend.phase3.state_contracts import TenantIdentity


_HASH = re.compile(r"^[0-9a-f]{64}$")
_RECORD_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}$")
_MAX_PAYLOAD_BYTES = 16 * 1024 * 1024


class PostgresRecordKind(str, Enum):
    SNAPSHOT = "SNAPSHOT"
    EVALUATION = "EVALUATION"
    AUDIT = "AUDIT"
    OUTBOX = "OUTBOX"
    RESEARCH_METADATA = "RESEARCH_METADATA"

    @property
    def table_name(self) -> str:
        return {
            PostgresRecordKind.SNAPSHOT: "phase4_account_snapshots",
            PostgresRecordKind.EVALUATION: "phase4_evaluations",
            PostgresRecordKind.AUDIT: "phase4_audit_events",
            PostgresRecordKind.OUTBOX: "phase4_outbox",
            PostgresRecordKind.RESEARCH_METADATA: "phase4_research_metadata",
        }[self]


POSTGRES_TABLES = tuple(kind.table_name for kind in PostgresRecordKind)


@dataclass(frozen=True)
class PostgresDocument:
    tenant_id: str
    record_id: str
    kind: PostgresRecordKind
    payload: bytes
    occurred_at: datetime
    payload_sha256: str = field(init=False)
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        TenantIdentity(self.tenant_id)
        if not isinstance(self.record_id, str) or _RECORD_ID.fullmatch(self.record_id) is None:
            raise ValueError("record_id must be a valid identifier")
        if not isinstance(self.kind, PostgresRecordKind):
            raise ValueError("kind must be a PostgresRecordKind")
        if not isinstance(self.payload, bytes) or not self.payload:
            raise ValueError("payload must be nonempty immutable bytes")
        if len(self.payload) > _MAX_PAYLOAD_BYTES:
            raise ValueError("payload exceeds the durable document limit")
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() is None:
            raise ValueError("occurred_at must be timezone-aware")
        object.__setattr__(self, "payload_sha256", hashlib.sha256(self.payload).hexdigest())


@dataclass(frozen=True)
class PostgresStoredDocument:
    document: PostgresDocument
    stored_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.document, PostgresDocument):
            raise ValueError("document must be a PostgresDocument")
        if self.stored_at.tzinfo is None or self.stored_at.utcoffset() is None:
            raise ValueError("stored_at must be timezone-aware")


@dataclass(frozen=True)
class PostgresAppendResult:
    record_id: str
    payload_sha256: str
    inserted: bool
    duplicate: bool
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.record_id, str) or _RECORD_ID.fullmatch(self.record_id) is None:
            raise ValueError("record_id must be a valid identifier")
        if not isinstance(self.payload_sha256, str) or _HASH.fullmatch(self.payload_sha256) is None:
            raise ValueError("payload_sha256 must be a lowercase digest")
        if type(self.inserted) is not bool or type(self.duplicate) is not bool:
            raise ValueError("append result flags must be booleans")
        if self.inserted == self.duplicate:
            raise ValueError("append result must be inserted or duplicate")


class PostgresCursor(Protocol):
    rowcount: int

    def execute(self, query: str, parameters: tuple[object, ...] = ()) -> object: ...

    def fetchone(self) -> tuple[object, ...] | None: ...

    def close(self) -> None: ...


class PostgresDBAPIConnection(Protocol):
    def cursor(self) -> PostgresCursor: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...

    def close(self) -> None: ...


PostgresConnectionFactory = Callable[[str, DatabaseAccessMode], PostgresDBAPIConnection]


def _utc_text(value: datetime, name: str) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def _parse_utc(value: object, name: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise DatabaseError(f"stored {name} is invalid")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        raise DatabaseError(f"stored {name} is invalid") from None
    if _utc_text(parsed, name) != value:
        raise DatabaseError(f"stored {name} is not canonical")
    return parsed


def _insert_sql(kind: PostgresRecordKind) -> str:
    return (
        f"INSERT INTO {kind.table_name} "
        "(tenant_id, record_id, payload, payload_sha256, occurred_at, stored_at) "
        "VALUES (%s, %s, %s, %s, %s, %s) "
        "ON CONFLICT (tenant_id, record_id) DO NOTHING"
    )


def _hash_sql(kind: PostgresRecordKind) -> str:
    return (
        f"SELECT payload_sha256 FROM {kind.table_name} "
        "WHERE tenant_id = %s AND record_id = %s"
    )


def _read_sql(kind: PostgresRecordKind) -> str:
    return (
        f"SELECT payload, payload_sha256, occurred_at, stored_at "
        f"FROM {kind.table_name} WHERE tenant_id = %s AND record_id = %s"
    )


class PostgresTenantRepository:
    execution_authorized = False
    production_mutation_authorized = False

    def __init__(self, connection: "PostgresDatabaseConnection", tenant_id: str):
        self._connection = connection
        self.tenant_id = TenantIdentity(tenant_id).tenant_id

    def append(
        self,
        document: PostgresDocument,
        *,
        stored_at: datetime,
    ) -> PostgresAppendResult:
        if self._connection.read_only:
            raise DatabaseReadOnlyError("database connection is read-only")
        if not isinstance(document, PostgresDocument):
            raise ValueError("document must be a PostgresDocument")
        if document.tenant_id != self.tenant_id:
            raise DatabaseTenantIsolationError("document tenant does not match session tenant")
        stored_text = _utc_text(stored_at, "stored_at")
        occurred_text = _utc_text(document.occurred_at, "occurred_at")
        cursor = self._connection._raw.cursor()
        try:
            cursor.execute(
                _insert_sql(document.kind),
                (
                    self.tenant_id,
                    document.record_id,
                    document.payload,
                    document.payload_sha256,
                    occurred_text,
                    stored_text,
                ),
            )
            inserted = cursor.rowcount == 1
            cursor.execute(
                _hash_sql(document.kind),
                (self.tenant_id, document.record_id),
            )
            stored_hash = cursor.fetchone()
            if stored_hash != (document.payload_sha256,):
                raise DatabaseError("PostgreSQL immutable record conflict")
            self._connection._raw.commit()
        except DatabaseError:
            self._connection._raw.rollback()
            raise
        except Exception:
            self._connection._raw.rollback()
            raise DatabaseError("PostgreSQL transaction failed") from None
        finally:
            cursor.close()
        return PostgresAppendResult(
            record_id=document.record_id,
            payload_sha256=document.payload_sha256,
            inserted=inserted,
            duplicate=not inserted,
        )

    def get(
        self,
        *,
        kind: PostgresRecordKind,
        record_id: str,
    ) -> PostgresStoredDocument | None:
        if not isinstance(kind, PostgresRecordKind):
            raise ValueError("kind must be a PostgresRecordKind")
        if not isinstance(record_id, str) or _RECORD_ID.fullmatch(record_id) is None:
            raise ValueError("record_id must be a valid identifier")
        cursor = self._connection._raw.cursor()
        try:
            cursor.execute(_read_sql(kind), (self.tenant_id, record_id))
            row = cursor.fetchone()
            self._connection._raw.rollback()
        except Exception:
            self._connection._raw.rollback()
            raise DatabaseError("PostgreSQL read failed") from None
        finally:
            cursor.close()
        if row is None:
            return None
        payload, payload_hash, occurred_at, stored_at = row
        if (
            not isinstance(payload, bytes)
            or not isinstance(payload_hash, str)
            or _HASH.fullmatch(payload_hash) is None
            or hashlib.sha256(payload).hexdigest() != payload_hash
        ):
            raise DatabaseError("PostgreSQL stored document integrity failure")
        document = PostgresDocument(
            tenant_id=self.tenant_id,
            record_id=record_id,
            kind=kind,
            payload=payload,
            occurred_at=_parse_utc(occurred_at, "occurred_at"),
        )
        if document.payload_sha256 != payload_hash:
            raise DatabaseError("PostgreSQL stored document hash mismatch")
        return PostgresStoredDocument(
            document=document,
            stored_at=_parse_utc(stored_at, "stored_at"),
        )


class PostgresDatabaseConnection:
    backend = DatabaseBackend.POSTGRESQL
    capabilities: DatabaseCapabilities = REQUIRED_CAPABILITIES
    execution_authorized = False
    production_mutation_authorized = False

    def __init__(
        self,
        target: DatabaseTarget,
        raw: PostgresDBAPIConnection,
        *,
        required_schema_version: int,
        clock: Callable[[], datetime],
    ):
        self.target = target
        self._raw = raw
        self._required_schema_version = required_schema_version
        self._clock = clock
        self._closed = False

    @property
    def read_only(self) -> bool:
        return self.target.access_mode is DatabaseAccessMode.READ_ONLY

    def _read_schema_version(self) -> int:
        if self._closed:
            raise DatabaseError("PostgreSQL connection is closed")
        cursor = self._raw.cursor()
        try:
            cursor.execute(
                "SELECT schema_version FROM phase4_store_metadata WHERE singleton = TRUE"
            )
            row = cursor.fetchone()
            self._raw.rollback()
        except Exception:
            self._raw.rollback()
            raise DatabaseError("PostgreSQL schema check failed") from None
        finally:
            cursor.close()
        if row is None or len(row) != 1 or type(row[0]) is not int or row[0] < 1:
            raise DatabaseError("PostgreSQL schema metadata is invalid")
        return row[0]

    @property
    def schema_version(self) -> int:
        version = self._read_schema_version()
        if version != self._required_schema_version:
            raise DatabaseError("PostgreSQL schema version mismatch")
        return version

    def health(self) -> DatabaseHealth:
        checked_at = self._clock()
        try:
            version = self.schema_version
        except DatabaseError:
            return DatabaseHealth(
                backend=self.backend,
                availability=DatabaseAvailability.UNAVAILABLE,
                checked_at=checked_at,
                read_only=self.read_only,
                schema_version=None,
                detail_code="postgresql_unavailable",
            )
        return DatabaseHealth(
            backend=self.backend,
            availability=DatabaseAvailability.AVAILABLE,
            checked_at=checked_at,
            read_only=self.read_only,
            schema_version=version,
            detail_code=(
                "postgresql_read_only" if self.read_only else "postgresql_available"
            ),
        )

    def tenant(self, tenant_id: str) -> PostgresTenantRepository:
        if self._closed:
            raise DatabaseError("PostgreSQL connection is closed")
        return PostgresTenantRepository(self, tenant_id)

    def close(self) -> None:
        if not self._closed:
            self._raw.close()
            self._closed = True

    def __enter__(self) -> "PostgresDatabaseConnection":
        self.schema_version
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


class PostgresDatabaseAdapter:
    """DB-API-compatible PostgreSQL adapter with injected connection creation.

    The factory receives an opaque reference ID and access mode. Resolution to a
    real driver or secret remains outside this adapter and is not implemented by
    this milestone.
    """

    backend = DatabaseBackend.POSTGRESQL
    capabilities: DatabaseCapabilities = REQUIRED_CAPABILITIES

    def __init__(
        self,
        connection_factory: PostgresConnectionFactory,
        *,
        required_schema_version: int = 1,
        clock: Callable[[], datetime] | None = None,
    ):
        if not callable(connection_factory):
            raise DatabaseConfigurationError("connection_factory must be callable")
        if type(required_schema_version) is not int or required_schema_version < 1:
            raise DatabaseConfigurationError("required_schema_version must be positive")
        self._connection_factory = connection_factory
        self._required_schema_version = required_schema_version
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def connect(self, target: DatabaseTarget) -> DatabaseConnection:
        if not isinstance(target, DatabaseTarget) or target.backend is not self.backend:
            raise DatabaseConfigurationError(
                "PostgreSQL adapter requires a PostgreSQL target"
            )
        reference = target.connection_reference
        assert reference is not None
        try:
            raw = self._connection_factory(reference, target.access_mode)
        except Exception:
            raise DatabaseError("PostgreSQL connection unavailable") from None
        connection = PostgresDatabaseConnection(
            target,
            raw,
            required_schema_version=self._required_schema_version,
            clock=self._clock,
        )
        if connection.health().availability is not DatabaseAvailability.AVAILABLE:
            connection.close()
            raise DatabaseError("PostgreSQL connection failed health validation")
        return connection
