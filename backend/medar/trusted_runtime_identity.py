"""Local authenticated MEDAR identity authority; no request-owned scope fields.

Only an authority installed by trusted runtime bootstrap can bind these identities
for memory access. This module does not provide per-user authentication.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from secrets import token_hex
from typing import Callable

from backend.medar.memory_access import MemoryPurpose
from backend.security.admin_authorization_v2 import AdminAuthorizationV2


class IdentityClassification(str, Enum):
    ANONYMOUS = "ANONYMOUS"
    SESSION_AUTHENTICATED = "SESSION_AUTHENTICATED"
    USER_AUTHENTICATED = "USER_AUTHENTICATED"
    SERVICE_AUTHENTICATED = "SERVICE_AUTHENTICATED"
    PRIVILEGED_LOCAL = "PRIVILEGED_LOCAL"


class IdentityAssurance(str, Enum):
    NONE = "NONE"
    SESSION = "SESSION"
    USER = "USER"
    SERVICE = "SERVICE"
    LOCAL_ADMIN = "LOCAL_ADMIN"


class RuntimeMemoryPermission(str, Enum):
    READ = "READ"
    WRITE = "WRITE"


@dataclass(frozen=True)
class TrustedRuntimeIdentity:
    runtime_identity_id: str
    owner_id: str
    tenant_id: str
    session_id: str
    service_id: str | None
    authentication_source: str
    classification: IdentityClassification
    assurance_level: IdentityAssurance
    issued_at: datetime
    expires_at: datetime
    permissions: frozenset[RuntimeMemoryPermission]
    purpose: MemoryPurpose
    _binding: object = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        for name in ("runtime_identity_id", "owner_id", "tenant_id", "session_id", "authentication_source"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} is required")
        if self.service_id is not None and (not isinstance(self.service_id, str) or not self.service_id.strip()):
            raise ValueError("service_id must be non-empty when provided")
        if not isinstance(self.classification, IdentityClassification) or not isinstance(self.assurance_level, IdentityAssurance):
            raise TypeError("identity classification and assurance must be typed")
        if self.classification is IdentityClassification.ANONYMOUS or self.assurance_level is IdentityAssurance.NONE:
            raise PermissionError("anonymous identity is not authenticated")
        if not isinstance(self.purpose, MemoryPurpose) or not isinstance(self.permissions, frozenset) or not self.permissions or any(
            not isinstance(permission, RuntimeMemoryPermission) for permission in self.permissions
        ):
            raise ValueError("identity purpose and permissions must be explicit")
        for value in (self.issued_at, self.expires_at):
            if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("identity times must be timezone-aware")
        if self.expires_at <= self.issued_at:
            raise ValueError("identity expiration must follow issuance")


@dataclass(frozen=True)
class LocalIdentityAssignment:
    owner_id: str
    tenant_id: str
    session_id: str
    service_id: str
    purpose: MemoryPurpose
    permissions: frozenset[RuntimeMemoryPermission]

    def __post_init__(self) -> None:
        for name in ("owner_id", "tenant_id", "session_id", "service_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"trusted {name} is required")
        if not isinstance(self.purpose, MemoryPurpose) or not isinstance(self.permissions, frozenset) or not self.permissions or any(
            not isinstance(permission, RuntimeMemoryPermission) for permission in self.permissions
        ):
            raise ValueError("trusted assignment requires purpose and permissions")


class LocalAdminIdentityAuthority:
    """Bootstrap-owned identity issuer using the existing local admin verifier."""

    def __init__(
        self,
        authentication: AdminAuthorizationV2,
        assignment: LocalIdentityAssignment,
        *,
        lifetime: timedelta = timedelta(minutes=15),
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not isinstance(authentication, AdminAuthorizationV2) or not isinstance(assignment, LocalIdentityAssignment):
            raise TypeError("admin authentication and trusted assignment are required")
        if not isinstance(lifetime, timedelta) or not timedelta(0) < lifetime <= timedelta(hours=1):
            raise ValueError("identity lifetime must be positive and at most one hour")
        self._authentication = authentication
        self._assignment = assignment
        self._lifetime = lifetime
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._binding = object()
        self._issued: dict[str, TrustedRuntimeIdentity] = {}

    def issue(self, credential: str | None) -> TrustedRuntimeIdentity:
        self._authentication.require_authorized(credential)
        now = self._clock()
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("identity clock must be timezone-aware")
        assignment = self._assignment
        identity = TrustedRuntimeIdentity(
            token_hex(16), assignment.owner_id, assignment.tenant_id,
            assignment.session_id, assignment.service_id, "LOCAL_ADMIN_CREDENTIAL",
            IdentityClassification.PRIVILEGED_LOCAL, IdentityAssurance.LOCAL_ADMIN,
            now, now + self._lifetime, assignment.permissions, assignment.purpose,
            self._binding,
        )
        self._issued[identity.runtime_identity_id] = identity
        return identity

    def require_valid(self, identity: TrustedRuntimeIdentity) -> None:
        if not isinstance(identity, TrustedRuntimeIdentity):
            raise PermissionError("trusted runtime identity is required")
        if identity._binding is not self._binding or self._issued.get(identity.runtime_identity_id) is not identity:
            raise PermissionError("identity was not issued by this authority")
        now = self._clock()
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("identity clock must be timezone-aware")
        if identity.issued_at > now or identity.expires_at <= now:
            raise PermissionError("identity is expired or not yet valid")
