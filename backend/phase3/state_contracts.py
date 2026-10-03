"""Immutable Phase 3 contracts for durable, read-only state.

These contracts define the information that a future persistence layer may
store. They deliberately perform no I/O and carry no broker or execution
authority. Canonical serialization and content hashing are introduced in
R32B; this milestone keeps exact values and provenance in memory without
inventing a database format.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
import re
from typing import TypeAlias


_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}$")
_SCHEMA_NAME = re.compile(r"^[a-z][a-z0-9_.-]{0,127}$")
_HASH = re.compile(r"^[0-9a-f]{64}$")
_FIELD_NAME = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_SENSITIVE_FIELD_PARTS = (
    "api_key",
    "authorization",
    "cookie",
    "credential",
    "password",
    "private_key",
    "secret",
    "token",
)
_MAX_TEXT_LENGTH = 4096
_MAX_PAYLOAD_FIELDS = 256
_MAX_SEQUENCE_ITEMS = 256


def _identifier(value: object, name: str) -> None:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise ValueError(f"{name} must be a valid nonempty identifier")


def _aware(value: object, name: str) -> None:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(f"{name} must be timezone-aware")


class DecimalUnit(str, Enum):
    CURRENCY = "currency"
    POINTS = "points"
    PERCENT = "percent"
    RATIO = "ratio"


@dataclass(frozen=True)
class DurableDecimal:
    """An exact finite decimal with an explicit semantic unit."""

    value: Decimal
    unit: DecimalUnit
    currency: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.value, Decimal) or not self.value.is_finite():
            raise ValueError("value must be a finite Decimal")
        if not isinstance(self.unit, DecimalUnit):
            raise ValueError("unit must be a DecimalUnit")
        if self.unit is DecimalUnit.CURRENCY:
            if (
                not isinstance(self.currency, str)
                or re.fullmatch(r"[A-Z]{3}", self.currency) is None
            ):
                raise ValueError("currency values require a three-letter currency")
        elif self.currency is not None:
            raise ValueError("currency is only valid for currency values")


@dataclass(frozen=True)
class SchemaIdentity:
    namespace: str
    name: str
    version: int

    def __post_init__(self) -> None:
        if not isinstance(self.namespace, str) or _SCHEMA_NAME.fullmatch(self.namespace) is None:
            raise ValueError("namespace must be a lowercase schema name")
        if not isinstance(self.name, str) or _SCHEMA_NAME.fullmatch(self.name) is None:
            raise ValueError("name must be a lowercase schema name")
        if type(self.version) is not int or self.version < 1:
            raise ValueError("version must be a positive integer")

    @property
    def qualified_name(self) -> str:
        return f"{self.namespace}.{self.name}.v{self.version}"


@dataclass(frozen=True)
class TenantIdentity:
    tenant_id: str

    def __post_init__(self) -> None:
        _identifier(self.tenant_id, "tenant_id")


@dataclass(frozen=True)
class UserIdentity:
    tenant_id: str
    user_id: str

    def __post_init__(self) -> None:
        _identifier(self.tenant_id, "tenant_id")
        _identifier(self.user_id, "user_id")


@dataclass(frozen=True)
class AccountIdentity:
    tenant_id: str
    account_id: str

    def __post_init__(self) -> None:
        _identifier(self.tenant_id, "tenant_id")
        _identifier(self.account_id, "account_id")


@dataclass(frozen=True)
class PropFirmProfileIdentity:
    firm_id: str
    program_id: str
    stage: str
    account_size: DurableDecimal
    profile_version: str
    config_hash: str

    def __post_init__(self) -> None:
        for field_name in ("firm_id", "program_id", "stage", "profile_version"):
            _identifier(getattr(self, field_name), field_name)
        if not isinstance(self.account_size, DurableDecimal):
            raise ValueError("account_size must be a DurableDecimal")
        if self.account_size.unit is not DecimalUnit.CURRENCY:
            raise ValueError("account_size must use the currency unit")
        if self.account_size.value <= 0:
            raise ValueError("account_size must be positive")
        if not isinstance(self.config_hash, str) or _HASH.fullmatch(self.config_hash) is None:
            raise ValueError("config_hash must be a lowercase sha256 digest")


@dataclass(frozen=True)
class SourceIdentity:
    source_id: str
    source_version: str
    simulated: bool

    def __post_init__(self) -> None:
        _identifier(self.source_id, "source_id")
        _identifier(self.source_version, "source_version")
        if type(self.simulated) is not bool:
            raise ValueError("simulated must be a boolean")


DurableScalar: TypeAlias = str | int | bool | datetime | DurableDecimal | None
DurableValue: TypeAlias = DurableScalar | tuple[DurableScalar, ...]


def _validate_scalar(value: object, field_name: str) -> None:
    if value is None or type(value) in (bool, int):
        return
    if isinstance(value, DurableDecimal):
        return
    if isinstance(value, datetime):
        _aware(value, f"payload field {field_name}")
        return
    if isinstance(value, str):
        if len(value) > _MAX_TEXT_LENGTH:
            raise ValueError(f"payload field {field_name} exceeds text limit")
        if any(ord(character) < 32 and character not in "\t\n\r" for character in value):
            raise ValueError(f"payload field {field_name} contains control characters")
        return
    raise ValueError(
        f"payload field {field_name} must use an exact durable scalar; "
        "floats, mutable containers, and untyped objects are forbidden"
    )


@dataclass(frozen=True)
class DurableStatePayload:
    """Sorted, immutable state fields with no implicit numeric conversion."""

    entries: tuple[tuple[str, DurableValue], ...]

    def __post_init__(self) -> None:
        if not isinstance(self.entries, tuple):
            raise ValueError("entries must be an immutable tuple")
        if len(self.entries) > _MAX_PAYLOAD_FIELDS:
            raise ValueError("payload contains too many fields")

        names: list[str] = []
        for entry in self.entries:
            if not isinstance(entry, tuple) or len(entry) != 2:
                raise ValueError("each payload entry must be a (name, value) tuple")
            field_name, value = entry
            if not isinstance(field_name, str) or _FIELD_NAME.fullmatch(field_name) is None:
                raise ValueError("payload field names must be lowercase identifiers")
            if any(part in field_name for part in _SENSITIVE_FIELD_PARTS):
                raise ValueError(f"sensitive payload field is forbidden: {field_name}")
            names.append(field_name)
            if isinstance(value, tuple):
                if len(value) > _MAX_SEQUENCE_ITEMS:
                    raise ValueError(f"payload field {field_name} contains too many items")
                for item in value:
                    _validate_scalar(item, field_name)
            else:
                _validate_scalar(value, field_name)

        if names != sorted(names):
            raise ValueError("payload fields must be sorted by name")
        if len(names) != len(set(names)):
            raise ValueError("payload fields must be unique")

    def get(self, field_name: str, default: DurableValue = None) -> DurableValue:
        for name, value in self.entries:
            if name == field_name:
                return value
        return default


class DurableStateKind(str, Enum):
    TENANT = "tenant"
    USER = "user"
    ACCOUNT = "account"
    PROP_FIRM_PROFILE = "prop_firm_profile"
    ACCOUNT_SNAPSHOT = "account_snapshot"
    EVALUATION_RESULT = "evaluation_result"
    PORTFOLIO_SUMMARY = "portfolio_summary"
    JOURNAL_ANALYTICS_SNAPSHOT = "journal_analytics_snapshot"
    NOTIFICATION_EVENT = "notification_event"
    MEMBERSHIP_ENTITLEMENT_STATE = "membership_entitlement_state"


_USER_REQUIRED = frozenset({
    DurableStateKind.USER,
    DurableStateKind.MEMBERSHIP_ENTITLEMENT_STATE,
})
_ACCOUNT_REQUIRED = frozenset({
    DurableStateKind.ACCOUNT,
    DurableStateKind.ACCOUNT_SNAPSHOT,
    DurableStateKind.EVALUATION_RESULT,
})
_PROFILE_REQUIRED = frozenset({
    DurableStateKind.PROP_FIRM_PROFILE,
    DurableStateKind.ACCOUNT_SNAPSHOT,
    DurableStateKind.EVALUATION_RESULT,
})


@dataclass(frozen=True)
class DurableStateRecord:
    """Versioned state observation with explicit scope and provenance.

    Authorization flags are constants exposed as read-only properties. A
    durable state record cannot authorize execution, production mutation, or
    canonical administrative changes.
    """

    record_id: str
    schema: SchemaIdentity
    kind: DurableStateKind
    observed_at: datetime
    tenant: TenantIdentity
    source: SourceIdentity
    payload: DurableStatePayload
    user: UserIdentity | None = None
    account: AccountIdentity | None = None
    profile: PropFirmProfileIdentity | None = None

    def __post_init__(self) -> None:
        _identifier(self.record_id, "record_id")
        if not isinstance(self.schema, SchemaIdentity):
            raise ValueError("schema must be a SchemaIdentity")
        if not isinstance(self.kind, DurableStateKind):
            raise ValueError("kind must be a DurableStateKind")
        if self.schema.name != self.kind.value:
            raise ValueError("schema name must match durable state kind")
        _aware(self.observed_at, "observed_at")
        if not isinstance(self.tenant, TenantIdentity):
            raise ValueError("tenant must be a TenantIdentity")
        if not isinstance(self.source, SourceIdentity):
            raise ValueError("source must be a SourceIdentity")
        if not isinstance(self.payload, DurableStatePayload):
            raise ValueError("payload must be a DurableStatePayload")

        if self.user is not None:
            if not isinstance(self.user, UserIdentity):
                raise ValueError("user must be a UserIdentity")
            if self.user.tenant_id != self.tenant.tenant_id:
                raise ValueError("user tenant does not match record tenant")
        if self.account is not None:
            if not isinstance(self.account, AccountIdentity):
                raise ValueError("account must be an AccountIdentity")
            if self.account.tenant_id != self.tenant.tenant_id:
                raise ValueError("account tenant does not match record tenant")
        if self.profile is not None and not isinstance(self.profile, PropFirmProfileIdentity):
            raise ValueError("profile must be a PropFirmProfileIdentity")

        if self.kind in _USER_REQUIRED and self.user is None:
            raise ValueError(f"{self.kind.value} records require user identity")
        if self.kind in _ACCOUNT_REQUIRED and self.account is None:
            raise ValueError(f"{self.kind.value} records require account identity")
        if self.kind in _PROFILE_REQUIRED and self.profile is None:
            raise ValueError(f"{self.kind.value} records require profile identity")
        if self.kind is DurableStateKind.TENANT and any(
            value is not None for value in (self.user, self.account, self.profile)
        ):
            raise ValueError("tenant records cannot carry narrower identities")

    @property
    def execution_authorized(self) -> bool:
        return False

    @property
    def production_mutation_authorized(self) -> bool:
        return False

    @property
    def canonical_admin_authorized(self) -> bool:
        return False
