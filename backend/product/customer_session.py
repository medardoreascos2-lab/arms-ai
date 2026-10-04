"""Provider-neutral customer session and local synthetic test authority.

A session identifier is resolved only through its issuing provider. The local provider
uses deterministic synthetic records and must never be mounted as production auth.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from enum import Enum
import re
from types import MappingProxyType
from typing import Mapping, Protocol

from backend.entitlements import FeatureEntitlement, UserIdentity, UserRole


_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
LOCAL_TEST_ONLY = "LOCAL_TEST_ONLY"


def _utc(value: datetime, name: str) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{name} must be UTC")


def _identifier(value: str, name: str) -> None:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise ValueError(f"{name} must be a safe opaque identifier")


class CustomerSessionStatus(str, Enum):
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
    INVALID = "INVALID"


class CustomerAssuranceLevel(str, Enum):
    LOCAL_TEST_ONLY = LOCAL_TEST_ONLY


@dataclass(frozen=True)
class TrustedCustomerSession:
    session_id: str
    user_id: str
    tenant_id: str
    issued_at: datetime
    expires_at: datetime
    auth_source: str
    authentication_method: str
    assurance_level: CustomerAssuranceLevel
    roles: frozenset[UserRole]
    entitlements: frozenset[FeatureEntitlement]
    status: CustomerSessionStatus
    device_metadata: Mapping[str, str] = field(default_factory=dict)
    session_metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("session_id", "user_id", "tenant_id"):
            _identifier(getattr(self, name), name)
        _identifier(self.auth_source, "auth_source")
        _identifier(self.authentication_method, "authentication_method")
        _utc(self.issued_at, "issued_at")
        _utc(self.expires_at, "expires_at")
        if self.expires_at <= self.issued_at:
            raise ValueError("session expiry must follow issuance")
        if not isinstance(self.assurance_level, CustomerAssuranceLevel):
            raise ValueError("invalid assurance level")
        if not isinstance(self.status, CustomerSessionStatus):
            raise ValueError("invalid session status")
        if not isinstance(self.roles, frozenset) or not self.roles or any(
            not isinstance(role, UserRole) for role in self.roles
        ):
            raise ValueError("session roles must be a nonempty immutable role set")
        if not isinstance(self.entitlements, frozenset) or any(
            not isinstance(item, FeatureEntitlement) for item in self.entitlements
        ):
            raise ValueError("session entitlements must be an immutable feature set")
        for name in ("device_metadata", "session_metadata"):
            value = getattr(self, name)
            if not isinstance(value, Mapping) or any(
                not isinstance(key, str) or not isinstance(item, str)
                for key, item in value.items()
            ):
                raise ValueError(f"{name} must contain text pairs")
            object.__setattr__(self, name, MappingProxyType(dict(value)))


class CustomerSessionProvider(Protocol):
    def validate_session(self, session_id: str, at: datetime) -> TrustedCustomerSession | None: ...
    def resolve_identity(self, session: TrustedCustomerSession, at: datetime) -> UserIdentity: ...
    def resolve_tenant(self, session: TrustedCustomerSession, at: datetime) -> str: ...
    def resolve_roles(self, session: TrustedCustomerSession, at: datetime) -> frozenset[UserRole]: ...
    def resolve_entitlements(
        self, session: TrustedCustomerSession, at: datetime
    ) -> frozenset[FeatureEntitlement]: ...


class LocalSyntheticSessionProvider:
    """In-memory deterministic fixtures. No credentials, cookies, network, or persistence."""

    auth_source = LOCAL_TEST_ONLY

    def __init__(self, sessions: tuple[TrustedCustomerSession, ...]) -> None:
        self._sessions: dict[str, TrustedCustomerSession] = {}
        for session in sessions:
            if not isinstance(session, TrustedCustomerSession):
                raise ValueError("trusted session fixture required")
            if (
                session.auth_source != LOCAL_TEST_ONLY
                or session.authentication_method != "SYNTHETIC_FIXTURE"
                or session.assurance_level != CustomerAssuranceLevel.LOCAL_TEST_ONLY
            ):
                raise ValueError("local provider accepts LOCAL_TEST_ONLY sessions only")
            for name in ("session_id", "user_id", "tenant_id"):
                if not getattr(session, name).startswith("synthetic-"):
                    raise ValueError("local provider accepts synthetic identifiers only")
            if session.session_id in self._sessions:
                raise ValueError("duplicate synthetic session identifier")
            self._sessions[session.session_id] = session

    def validate_session(self, session_id: str, at: datetime) -> TrustedCustomerSession | None:
        _utc(at, "at")
        if not isinstance(session_id, str):
            return None
        session = self._sessions.get(session_id)
        if session is None or session.status != CustomerSessionStatus.ACTIVE:
            return None
        if not session.issued_at <= at < session.expires_at:
            return None
        return session

    def _require(self, session: TrustedCustomerSession, at: datetime) -> None:
        if not isinstance(session, TrustedCustomerSession):
            raise PermissionError("trusted customer session required")
        if self.validate_session(session.session_id, at) is not session:
            raise PermissionError("session is not current or was not issued by this provider")

    def resolve_identity(self, session: TrustedCustomerSession, at: datetime) -> UserIdentity:
        self._require(session, at)
        return UserIdentity(session.user_id, session.tenant_id)

    def resolve_tenant(self, session: TrustedCustomerSession, at: datetime) -> str:
        self._require(session, at)
        return session.tenant_id

    def resolve_roles(self, session: TrustedCustomerSession, at: datetime) -> frozenset[UserRole]:
        self._require(session, at)
        return session.roles

    def resolve_entitlements(
        self, session: TrustedCustomerSession, at: datetime
    ) -> frozenset[FeatureEntitlement]:
        self._require(session, at)
        return session.entitlements

    def revoke(self, session_id: str) -> None:
        session = self._sessions.get(session_id)
        if session is not None:
            self._sessions[session_id] = replace(session, status=CustomerSessionStatus.REVOKED)


def synthetic_customer_session(
    *, issued_at: datetime, expires_at: datetime,
    session_id: str = "synthetic-session-1",
    user_id: str = "synthetic-user-1",
    tenant_id: str = "synthetic-tenant-1",
    entitlements: frozenset[FeatureEntitlement] = frozenset({FeatureEntitlement.MEDAR_CONVERSATION}),
    roles: frozenset[UserRole] = frozenset({UserRole.VIEWER}),
) -> TrustedCustomerSession:
    """Explicit deterministic fixture for local tests, never a customer account."""
    return TrustedCustomerSession(
        session_id=session_id, user_id=user_id, tenant_id=tenant_id,
        issued_at=issued_at, expires_at=expires_at,
        auth_source=LOCAL_TEST_ONLY, authentication_method="SYNTHETIC_FIXTURE",
        assurance_level=CustomerAssuranceLevel.LOCAL_TEST_ONLY,
        roles=roles, entitlements=entitlements, status=CustomerSessionStatus.ACTIVE,
        device_metadata={"kind": "synthetic-test-device"},
        session_metadata={"environment": LOCAL_TEST_ONLY},
    )
