"""Immutable service identity and credential-reference model for Phase 4."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import re

from backend.phase3.state_contracts import TenantIdentity

from .secret_providers import SecretReference


_SERVICE_ID = re.compile(r"^[a-z][a-z0-9_.-]{0,127}$")


class ServicePermission(str, Enum):
    HEALTH_READ = "HEALTH_READ"
    METRICS_READ = "METRICS_READ"
    OPERATIONS_READ = "OPERATIONS_READ"
    LOCAL_BACKUP_CREATE = "LOCAL_BACKUP_CREATE"
    ISOLATED_RESTORE_VALIDATE = "ISOLATED_RESTORE_VALIDATE"
    WORKER_SUPERVISE = "WORKER_SUPERVISE"
    SCHEDULER_SUPERVISE = "SCHEDULER_SUPERVISE"
    RETRY_OPERATIONS = "RETRY_OPERATIONS"


def _utc(value: datetime, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class ServiceTenantScope:
    tenant_ids: frozenset[str]

    def __post_init__(self) -> None:
        if not isinstance(self.tenant_ids, frozenset) or not self.tenant_ids:
            raise ValueError("tenant_ids must be a nonempty immutable set")
        for tenant_id in self.tenant_ids:
            TenantIdentity(tenant_id)

    def allows(self, tenant_id: str) -> bool:
        TenantIdentity(tenant_id)
        return tenant_id in self.tenant_ids


@dataclass(frozen=True)
class ServiceCredentialRotation:
    sequence: int
    issued_at: datetime
    rotate_after: datetime
    previous_credential_reference: SecretReference | None = None

    def __post_init__(self) -> None:
        if type(self.sequence) is not int or self.sequence < 1:
            raise ValueError("rotation sequence must be positive")
        issued = _utc(self.issued_at, "issued_at")
        rotate = _utc(self.rotate_after, "rotate_after")
        if rotate <= issued:
            raise ValueError("rotate_after must follow issued_at")
        if self.sequence == 1 and self.previous_credential_reference is not None:
            raise ValueError("initial credential cannot reference a previous credential")
        if self.sequence > 1 and not isinstance(
            self.previous_credential_reference, SecretReference
        ):
            raise ValueError("rotated credential requires a previous credential reference")
        object.__setattr__(self, "issued_at", issued)
        object.__setattr__(self, "rotate_after", rotate)


@dataclass(frozen=True)
class ServiceIdentity:
    service_id: str
    tenant_scope: ServiceTenantScope
    permissions: frozenset[ServicePermission]
    credential_reference: SecretReference
    expires_at: datetime
    rotation: ServiceCredentialRotation
    authenticated: bool = field(default=False, init=False)
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)
    live_trading_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.service_id, str) or _SERVICE_ID.fullmatch(self.service_id) is None:
            raise ValueError("service_id must be a lowercase service identifier")
        if not isinstance(self.tenant_scope, ServiceTenantScope):
            raise ValueError("tenant_scope must be a ServiceTenantScope")
        if not isinstance(self.permissions, frozenset) or not self.permissions or any(
            not isinstance(permission, ServicePermission) for permission in self.permissions
        ):
            raise ValueError("permissions must be a nonempty immutable ServicePermission set")
        if not isinstance(self.credential_reference, SecretReference):
            raise ValueError("credential_reference must be a SecretReference")
        if not isinstance(self.rotation, ServiceCredentialRotation):
            raise ValueError("rotation must be ServiceCredentialRotation")
        expires = _utc(self.expires_at, "expires_at")
        if expires <= self.rotation.rotate_after:
            raise ValueError("expires_at must follow rotate_after")
        if (
            self.rotation.previous_credential_reference is not None
            and self.rotation.previous_credential_reference == self.credential_reference
        ):
            raise ValueError("current and previous credential references must differ")
        object.__setattr__(self, "expires_at", expires)

    def active_at(self, moment: datetime) -> bool:
        now = _utc(moment, "moment")
        return self.rotation.issued_at <= now < self.expires_at

    def rotation_due_at(self, moment: datetime) -> bool:
        now = _utc(moment, "moment")
        return self.rotation.rotate_after <= now < self.expires_at

    def covers(self, permission: ServicePermission, tenant_id: str) -> bool:
        if not isinstance(permission, ServicePermission):
            raise ValueError("permission must be a ServicePermission")
        return permission in self.permissions and self.tenant_scope.allows(tenant_id)
