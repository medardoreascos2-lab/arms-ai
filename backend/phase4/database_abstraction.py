"""Fail-closed database abstraction for the isolated Phase 4 runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
from pathlib import Path
import re
import sqlite3
from typing import Callable, Protocol, runtime_checkable

from backend.phase3.durable_store import (
    DurableStoreError,
    Phase3DurableStateStore,
    STORE_SCHEMA_VERSION,
    StoreAppendResult,
    StoredStateRecord,
)
from backend.phase3.financial_serialization import canonical_decimal_text
from backend.phase3.state_contracts import DurableStateRecord, TenantIdentity


_NAME = re.compile(r"^[a-z][a-z0-9_]{0,62}$")
_REFERENCE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\-/]{0,255}$")


class DatabaseError(RuntimeError):
    """Base error for Phase 4 database selection and access."""


class DatabaseConfigurationError(DatabaseError):
    pass


class DatabaseAdapterUnavailableError(DatabaseError):
    pass


class DatabaseReadOnlyError(DatabaseError):
    pass


class DatabaseTenantIsolationError(DatabaseError):
    pass


class DatabaseBackend(str, Enum):
    SQLITE = "SQLITE"
    POSTGRESQL = "POSTGRESQL"


class DatabaseAccessMode(str, Enum):
    READ_WRITE = "READ_WRITE"
    READ_ONLY = "READ_ONLY"


class DatabaseAvailability(str, Enum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class DatabaseTarget:
    """Secret-free database selection.

    PostgreSQL uses an opaque connection reference that a later secret provider
    may resolve. Raw DSNs and credentials are deliberately rejected here.
    """

    backend: DatabaseBackend
    database_name: str
    access_mode: DatabaseAccessMode
    sqlite_path: Path | None = None
    connection_reference: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.backend, DatabaseBackend):
            raise DatabaseConfigurationError("backend must be a DatabaseBackend")
        if not isinstance(self.access_mode, DatabaseAccessMode):
            raise DatabaseConfigurationError("access_mode must be a DatabaseAccessMode")
        if not isinstance(self.database_name, str) or _NAME.fullmatch(self.database_name) is None:
            raise DatabaseConfigurationError("database_name must be a lowercase identifier")
        if self.backend is DatabaseBackend.SQLITE:
            if not isinstance(self.sqlite_path, Path):
                raise DatabaseConfigurationError("SQLite requires sqlite_path")
            if self.connection_reference is not None:
                raise DatabaseConfigurationError("SQLite cannot carry a connection reference")
            if str(self.sqlite_path).strip() in ("", ":memory:"):
                raise DatabaseConfigurationError("SQLite requires a durable file path")
        else:
            if self.sqlite_path is not None:
                raise DatabaseConfigurationError("PostgreSQL cannot carry sqlite_path")
            reference = self.connection_reference
            if isinstance(reference, str) and any(
                marker in reference for marker in ("://", "@", "=")
            ):
                raise DatabaseConfigurationError("raw PostgreSQL connection values are forbidden")
            if not isinstance(reference, str) or _REFERENCE.fullmatch(reference) is None:
                raise DatabaseConfigurationError(
                    "PostgreSQL requires an opaque connection reference"
                )


@dataclass(frozen=True)
class DatabaseCapabilities:
    exact_decimal: bool
    tenant_scoped_access: bool
    transactional_writes: bool
    schema_versioning: bool
    read_only_mode: bool
    health_checks: bool

    def __post_init__(self) -> None:
        if any(type(value) is not bool for value in self.__dict__.values()):
            raise ValueError("database capabilities must be booleans")


REQUIRED_CAPABILITIES = DatabaseCapabilities(
    exact_decimal=True,
    tenant_scoped_access=True,
    transactional_writes=True,
    schema_versioning=True,
    read_only_mode=True,
    health_checks=True,
)


@dataclass(frozen=True)
class DatabaseHealth:
    backend: DatabaseBackend
    availability: DatabaseAvailability
    checked_at: datetime
    read_only: bool
    schema_version: int | None
    detail_code: str
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.backend, DatabaseBackend):
            raise ValueError("backend must be a DatabaseBackend")
        if not isinstance(self.availability, DatabaseAvailability):
            raise ValueError("availability must be a DatabaseAvailability")
        if self.checked_at.tzinfo is None or self.checked_at.utcoffset() is None:
            raise ValueError("checked_at must be timezone-aware")
        if type(self.read_only) is not bool:
            raise ValueError("read_only must be boolean")
        if self.schema_version is not None and (
            type(self.schema_version) is not int or self.schema_version < 1
        ):
            raise ValueError("schema_version must be positive when present")
        if not isinstance(self.detail_code, str) or _NAME.fullmatch(self.detail_code) is None:
            raise ValueError("detail_code must be a safe lowercase identifier")
        if self.availability is DatabaseAvailability.AVAILABLE and self.schema_version is None:
            raise ValueError("available database health requires schema_version")
        if self.availability is DatabaseAvailability.UNAVAILABLE and self.schema_version is not None:
            raise ValueError("unavailable database health cannot claim schema_version")


@runtime_checkable
class TenantStateRepository(Protocol):
    tenant_id: str
    execution_authorized: bool
    production_mutation_authorized: bool

    def append(
        self, record: DurableStateRecord, *, committed_at: datetime
    ) -> StoreAppendResult: ...

    def get(self, *, record_id: str) -> StoredStateRecord | None: ...

    def count(self) -> int: ...


@runtime_checkable
class DatabaseConnection(Protocol):
    backend: DatabaseBackend
    target: DatabaseTarget
    capabilities: DatabaseCapabilities
    execution_authorized: bool
    production_mutation_authorized: bool

    @property
    def read_only(self) -> bool: ...

    @property
    def schema_version(self) -> int: ...

    def health(self) -> DatabaseHealth: ...

    def tenant(self, tenant_id: str) -> TenantStateRepository: ...

    def close(self) -> None: ...


@runtime_checkable
class DatabaseAdapter(Protocol):
    backend: DatabaseBackend
    capabilities: DatabaseCapabilities

    def connect(self, target: DatabaseTarget) -> DatabaseConnection: ...


def encode_exact_decimal(value: Decimal) -> str:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise ValueError("value must be a finite Decimal")
    return canonical_decimal_text(value)


def decode_exact_decimal(value: str) -> Decimal:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError("stored decimal must be canonical text")
    try:
        decoded = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("stored decimal is invalid") from exc
    if not decoded.is_finite() or canonical_decimal_text(decoded) != value:
        raise ValueError("stored decimal must use canonical finite text")
    return decoded


class _SQLiteTenantStateRepository:
    execution_authorized = False
    production_mutation_authorized = False

    def __init__(self, connection: "SQLiteDatabaseConnection", tenant_id: str):
        self._connection = connection
        self.tenant_id = TenantIdentity(tenant_id).tenant_id

    def append(
        self, record: DurableStateRecord, *, committed_at: datetime
    ) -> StoreAppendResult:
        if self._connection.read_only:
            raise DatabaseReadOnlyError("database connection is read-only")
        if not isinstance(record, DurableStateRecord):
            raise ValueError("record must be a DurableStateRecord")
        if record.tenant.tenant_id != self.tenant_id:
            raise DatabaseTenantIsolationError("record tenant does not match session tenant")
        return self._connection._store.append(record, committed_at=committed_at)

    def get(self, *, record_id: str) -> StoredStateRecord | None:
        return self._connection._store.get(
            tenant_id=self.tenant_id,
            record_id=record_id,
        )

    def count(self) -> int:
        return self._connection._store.count(tenant_id=self.tenant_id)


class SQLiteDatabaseConnection:
    backend = DatabaseBackend.SQLITE
    capabilities = REQUIRED_CAPABILITIES
    execution_authorized = False
    production_mutation_authorized = False

    def __init__(
        self,
        target: DatabaseTarget,
        store: Phase3DurableStateStore,
        *,
        clock: Callable[[], datetime],
    ):
        self.target = target
        self._store = store
        self._clock = clock

    @property
    def read_only(self) -> bool:
        return self._store.read_only

    @property
    def schema_version(self) -> int:
        return self._store.schema_version

    def health(self) -> DatabaseHealth:
        checked_at = self._clock()
        try:
            schema_version = self._store.schema_version
        except (DurableStoreError, sqlite3.DatabaseError):
            return DatabaseHealth(
                backend=self.backend,
                availability=DatabaseAvailability.UNAVAILABLE,
                checked_at=checked_at,
                read_only=self.read_only,
                schema_version=None,
                detail_code="sqlite_unavailable",
            )
        return DatabaseHealth(
            backend=self.backend,
            availability=DatabaseAvailability.AVAILABLE,
            checked_at=checked_at,
            read_only=self.read_only,
            schema_version=schema_version,
            detail_code="sqlite_read_only" if self.read_only else "sqlite_available",
        )

    def tenant(self, tenant_id: str) -> TenantStateRepository:
        return _SQLiteTenantStateRepository(self, tenant_id)

    def close(self) -> None:
        self._store.close()

    def __enter__(self) -> "SQLiteDatabaseConnection":
        self.schema_version
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


class SQLiteDatabaseAdapter:
    backend = DatabaseBackend.SQLITE
    capabilities = REQUIRED_CAPABILITIES

    def __init__(self, *, clock: Callable[[], datetime] | None = None):
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def connect(self, target: DatabaseTarget) -> DatabaseConnection:
        if not isinstance(target, DatabaseTarget) or target.backend is not self.backend:
            raise DatabaseConfigurationError("SQLite adapter requires a SQLite target")
        path = target.sqlite_path
        assert path is not None
        read_only = target.access_mode is DatabaseAccessMode.READ_ONLY
        if path.expanduser().resolve().exists():
            store = Phase3DurableStateStore.open(path, read_only=read_only)
        else:
            if read_only:
                raise DatabaseReadOnlyError("read-only SQLite target does not exist")
            store = Phase3DurableStateStore.create(path)
        return SQLiteDatabaseConnection(target, store, clock=self._clock)


class DatabaseAdapterRegistry:
    execution_authorized = False
    production_mutation_authorized = False

    def __init__(self, adapters: tuple[DatabaseAdapter, ...] = ()):
        self._adapters: dict[DatabaseBackend, DatabaseAdapter] = {}
        for adapter in adapters:
            self.register(adapter)

    @property
    def backends(self) -> tuple[DatabaseBackend, ...]:
        return tuple(sorted(self._adapters, key=lambda item: item.value))

    def register(self, adapter: DatabaseAdapter) -> None:
        if not isinstance(adapter, DatabaseAdapter):
            raise DatabaseConfigurationError("adapter does not satisfy DatabaseAdapter")
        if adapter.capabilities != REQUIRED_CAPABILITIES:
            raise DatabaseConfigurationError("adapter lacks required safety capabilities")
        if adapter.backend in self._adapters:
            raise DatabaseConfigurationError("database backend is already registered")
        self._adapters[adapter.backend] = adapter

    def connect(self, target: DatabaseTarget) -> DatabaseConnection:
        if not isinstance(target, DatabaseTarget):
            raise DatabaseConfigurationError("target must be a DatabaseTarget")
        adapter = self._adapters.get(target.backend)
        if adapter is None:
            raise DatabaseAdapterUnavailableError(
                f"{target.backend.value.lower()} adapter is not registered"
            )
        return adapter.connect(target)
