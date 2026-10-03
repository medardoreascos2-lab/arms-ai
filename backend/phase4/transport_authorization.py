"""Deny-by-default transport authorization contracts for Phase 4 read APIs."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Mapping, TypeAlias

from backend.entitlements import Permission, UserStatus
from backend.phase3.read_authorization import AccountReadScope, AuthorizationPrincipal
from backend.phase3.state_contracts import AccountIdentity, TenantIdentity

from .service_identity import ServiceIdentity, ServicePermission


class Phase4TransportAction(str, Enum):
    HEALTH_READ = "HEALTH_READ"
    METRICS_READ = "METRICS_READ"
    OPERATIONS_READ = "OPERATIONS_READ"
    ACCOUNT_OPERATIONS_READ = "ACCOUNT_OPERATIONS_READ"


@dataclass(frozen=True)
class TransportAuthorizationRequirement:
    user_permission: Permission
    service_permission: ServicePermission
    account_scoped: bool


TRANSPORT_REQUIREMENTS: Mapping[
    Phase4TransportAction, TransportAuthorizationRequirement
] = MappingProxyType({
    Phase4TransportAction.HEALTH_READ: TransportAuthorizationRequirement(
        Permission.DASHBOARD_READ,
        ServicePermission.HEALTH_READ,
        False,
    ),
    Phase4TransportAction.METRICS_READ: TransportAuthorizationRequirement(
        Permission.ANALYTICS_READ,
        ServicePermission.METRICS_READ,
        False,
    ),
    Phase4TransportAction.OPERATIONS_READ: TransportAuthorizationRequirement(
        Permission.ANALYTICS_READ,
        ServicePermission.OPERATIONS_READ,
        False,
    ),
    Phase4TransportAction.ACCOUNT_OPERATIONS_READ: TransportAuthorizationRequirement(
        Permission.ACCOUNT_PROFILE_READ,
        ServicePermission.OPERATIONS_READ,
        True,
    ),
})


def _utc(value: datetime, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class AuthenticatedUserTransportPrincipal:
    principal: AuthorizationPrincipal
    tenant_claim: str
    authenticated_at: datetime
    authenticated: bool = field(default=True, init=False)
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.principal, AuthorizationPrincipal):
            raise ValueError("principal must be an AuthorizationPrincipal")
        TenantIdentity(self.tenant_claim)
        if self.tenant_claim != self.principal.identity.tenant_id:
            raise ValueError("tenant claim must match user principal")
        object.__setattr__(self, "authenticated_at", _utc(self.authenticated_at, "authenticated_at"))

    @property
    def account_scope(self) -> AccountReadScope:
        return self.principal.account_scope


@dataclass(frozen=True)
class AuthenticatedServiceTransportPrincipal:
    identity: ServiceIdentity
    tenant_claim: str
    account_scope: AccountReadScope
    authenticated_at: datetime
    authenticated: bool = field(default=True, init=False)
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.identity, ServiceIdentity):
            raise ValueError("identity must be a ServiceIdentity")
        TenantIdentity(self.tenant_claim)
        if not self.identity.tenant_scope.allows(self.tenant_claim):
            raise ValueError("tenant claim is outside service identity scope")
        if not isinstance(self.account_scope, AccountReadScope):
            raise ValueError("account_scope must be an AccountReadScope")
        if self.account_scope.tenant_id != self.tenant_claim:
            raise ValueError("account scope tenant must match tenant claim")
        authenticated = _utc(self.authenticated_at, "authenticated_at")
        if not self.identity.active_at(authenticated):
            raise ValueError("service identity was not active when authenticated")
        object.__setattr__(self, "authenticated_at", authenticated)


AuthenticatedTransportPrincipal: TypeAlias = (
    AuthenticatedUserTransportPrincipal | AuthenticatedServiceTransportPrincipal
)


@dataclass(frozen=True)
class Phase4TransportRequest:
    action: Phase4TransportAction
    tenant_id: str
    account_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.action, Phase4TransportAction):
            raise ValueError("action must be a Phase4TransportAction")
        TenantIdentity(self.tenant_id)
        requirement = TRANSPORT_REQUIREMENTS[self.action]
        if requirement.account_scoped:
            if self.account_id is None:
                raise ValueError("account-scoped transport action requires account_id")
            AccountIdentity(self.tenant_id, self.account_id)
        elif self.account_id is not None:
            raise ValueError("tenant-scoped transport action cannot carry account_id")


class TransportAuthorizationCode(str, Enum):
    ALLOWED = "ALLOWED"
    MISSING_AUTH = "MISSING_AUTH"
    AUTH_TIME_INVALID = "AUTH_TIME_INVALID"
    PRINCIPAL_INACTIVE = "PRINCIPAL_INACTIVE"
    CREDENTIAL_EXPIRED = "CREDENTIAL_EXPIRED"
    TENANT_MISMATCH = "TENANT_MISMATCH"
    PERMISSION_MISSING = "PERMISSION_MISSING"
    ACCOUNT_UNKNOWN = "ACCOUNT_UNKNOWN"
    ACCOUNT_SCOPE_DENIED = "ACCOUNT_SCOPE_DENIED"


@dataclass(frozen=True)
class TransportAuthorizationDecision:
    allowed: bool
    code: TransportAuthorizationCode
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if type(self.allowed) is not bool or not isinstance(self.code, TransportAuthorizationCode):
            raise ValueError("transport decision is invalid")
        if self.allowed != (self.code is TransportAuthorizationCode.ALLOWED):
            raise ValueError("transport decision code does not match allowed state")


def _decision(code: TransportAuthorizationCode) -> TransportAuthorizationDecision:
    return TransportAuthorizationDecision(code is TransportAuthorizationCode.ALLOWED, code)


@dataclass(frozen=True)
class Phase4TransportAuthorizationBoundary:
    known_accounts: frozenset[AccountIdentity]
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.known_accounts, frozenset) or any(
            not isinstance(item, AccountIdentity) for item in self.known_accounts
        ):
            raise ValueError("known_accounts must be an immutable AccountIdentity set")

    def evaluate(
        self,
        principal: AuthenticatedTransportPrincipal | None,
        request: Phase4TransportRequest,
        *,
        evaluated_at: datetime,
    ) -> TransportAuthorizationDecision:
        if not isinstance(request, Phase4TransportRequest):
            raise ValueError("request must be a Phase4TransportRequest")
        now = _utc(evaluated_at, "evaluated_at")
        if not isinstance(
            principal,
            (AuthenticatedUserTransportPrincipal, AuthenticatedServiceTransportPrincipal),
        ):
            return _decision(TransportAuthorizationCode.MISSING_AUTH)
        if principal.authenticated_at > now:
            return _decision(TransportAuthorizationCode.AUTH_TIME_INVALID)
        if principal.tenant_claim != request.tenant_id:
            return _decision(TransportAuthorizationCode.TENANT_MISMATCH)

        requirement = TRANSPORT_REQUIREMENTS[request.action]
        if isinstance(principal, AuthenticatedUserTransportPrincipal):
            if principal.principal.identity.status is not UserStatus.ACTIVE:
                return _decision(TransportAuthorizationCode.PRINCIPAL_INACTIVE)
            if requirement.user_permission not in principal.principal.permissions:
                return _decision(TransportAuthorizationCode.PERMISSION_MISSING)
        else:
            if not principal.identity.active_at(now):
                return _decision(TransportAuthorizationCode.CREDENTIAL_EXPIRED)
            if not principal.identity.covers(
                requirement.service_permission,
                request.tenant_id,
            ):
                return _decision(TransportAuthorizationCode.PERMISSION_MISSING)

        if requirement.account_scoped:
            account = AccountIdentity(request.tenant_id, request.account_id)
            if account not in self.known_accounts:
                return _decision(TransportAuthorizationCode.ACCOUNT_UNKNOWN)
            if not principal.account_scope.allows(request.account_id):
                return _decision(TransportAuthorizationCode.ACCOUNT_SCOPE_DENIED)
        return _decision(TransportAuthorizationCode.ALLOWED)
