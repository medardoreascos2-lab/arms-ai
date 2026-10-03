"""Pure, fail-closed tenant/account authorization for Phase 3 reads."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Mapping

from backend.entitlements import (
    FeatureEntitlement,
    Permission,
    UserIdentity,
    UserRole,
    UserStatus,
    permissions_for_roles,
)

from .state_contracts import AccountIdentity, TenantIdentity


class AccountScopeMode(str, Enum):
    EXPLICIT = "EXPLICIT"
    ALL_TENANT_ACCOUNTS = "ALL_TENANT_ACCOUNTS"


class ReadAction(str, Enum):
    ACCOUNT_STATE = "ACCOUNT_STATE"
    PROP_FIRM_EVALUATION = "PROP_FIRM_EVALUATION"
    PORTFOLIO_SUMMARY = "PORTFOLIO_SUMMARY"
    JOURNAL_ANALYTICS = "JOURNAL_ANALYTICS"
    NOTIFICATION_EVENT = "NOTIFICATION_EVENT"
    MEMBERSHIP_ENTITLEMENT = "MEMBERSHIP_ENTITLEMENT"


class AuthorizationCode(str, Enum):
    ALLOWED = "ALLOWED"
    MISSING_AUTH = "MISSING_AUTH"
    PRINCIPAL_INACTIVE = "PRINCIPAL_INACTIVE"
    TENANT_MISMATCH = "TENANT_MISMATCH"
    USER_SCOPE_DENIED = "USER_SCOPE_DENIED"
    PERMISSION_MISSING = "PERMISSION_MISSING"
    ENTITLEMENT_MISSING = "ENTITLEMENT_MISSING"
    ACCOUNT_UNKNOWN = "ACCOUNT_UNKNOWN"
    ACCOUNT_SCOPE_DENIED = "ACCOUNT_SCOPE_DENIED"
    NO_ACCOUNTS_AUTHORIZED = "NO_ACCOUNTS_AUTHORIZED"


@dataclass(frozen=True)
class ReadRequirement:
    permission: Permission
    entitlement: FeatureEntitlement | None
    account_scoped: bool
    user_scoped: bool = False


READ_REQUIREMENTS: Mapping[ReadAction, ReadRequirement] = MappingProxyType({
    ReadAction.ACCOUNT_STATE: ReadRequirement(
        Permission.ACCOUNT_PROFILE_READ,
        FeatureEntitlement.PROP_FIRM_POLICY,
        True,
    ),
    ReadAction.PROP_FIRM_EVALUATION: ReadRequirement(
        Permission.ANALYTICS_READ,
        FeatureEntitlement.PROP_FIRM_POLICY,
        True,
    ),
    ReadAction.PORTFOLIO_SUMMARY: ReadRequirement(
        Permission.ANALYTICS_READ,
        FeatureEntitlement.MULTI_ACCOUNT,
        True,
    ),
    ReadAction.JOURNAL_ANALYTICS: ReadRequirement(
        Permission.ANALYTICS_READ,
        FeatureEntitlement.TRADE_JOURNAL_ANALYTICS,
        True,
    ),
    ReadAction.NOTIFICATION_EVENT: ReadRequirement(
        Permission.NOTIFICATION_READ,
        FeatureEntitlement.NOTIFICATIONS,
        False,
        True,
    ),
    ReadAction.MEMBERSHIP_ENTITLEMENT: ReadRequirement(
        Permission.ENTITLEMENT_READ,
        None,
        False,
        True,
    ),
})


@dataclass(frozen=True)
class AccountReadScope:
    tenant_id: str
    mode: AccountScopeMode
    account_ids: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        TenantIdentity(self.tenant_id)
        if not isinstance(self.mode, AccountScopeMode):
            raise ValueError("mode must be an AccountScopeMode")
        if not isinstance(self.account_ids, frozenset):
            raise ValueError("account_ids must be an immutable set")
        for account_id in self.account_ids:
            AccountIdentity(self.tenant_id, account_id)
        if self.mode is AccountScopeMode.ALL_TENANT_ACCOUNTS and self.account_ids:
            raise ValueError("all-tenant scope cannot carry explicit account IDs")

    def allows(self, account_id: str) -> bool:
        AccountIdentity(self.tenant_id, account_id)
        return (
            self.mode is AccountScopeMode.ALL_TENANT_ACCOUNTS
            or account_id in self.account_ids
        )


@dataclass(frozen=True)
class AuthorizationPrincipal:
    identity: UserIdentity
    roles: frozenset[UserRole]
    entitlements: frozenset[FeatureEntitlement]
    account_scope: AccountReadScope
    permissions: frozenset[Permission] = field(init=False)
    canonical_admin_authorized: bool = field(default=False, init=False)
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.identity, UserIdentity):
            raise ValueError("identity must be a UserIdentity")
        if not isinstance(self.roles, frozenset) or not self.roles or any(
            not isinstance(role, UserRole) for role in self.roles
        ):
            raise ValueError("roles must be a nonempty immutable UserRole set")
        if not isinstance(self.entitlements, frozenset) or any(
            not isinstance(item, FeatureEntitlement) for item in self.entitlements
        ):
            raise ValueError(
                "entitlements must be an immutable FeatureEntitlement set"
            )
        if not isinstance(self.account_scope, AccountReadScope):
            raise ValueError("account_scope must be an AccountReadScope")
        if self.account_scope.tenant_id != self.identity.tenant_id:
            raise ValueError("account scope tenant must match principal tenant")
        if (
            self.account_scope.mode is AccountScopeMode.ALL_TENANT_ACCOUNTS
            and UserRole.TENANT_ADMIN not in self.roles
        ):
            raise ValueError("all-tenant account scope requires TENANT_ADMIN")
        object.__setattr__(self, "permissions", permissions_for_roles(self.roles))


@dataclass(frozen=True)
class ReadRequest:
    action: ReadAction
    tenant_id: str
    account_id: str | None = None
    user_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.action, ReadAction):
            raise ValueError("action must be a ReadAction")
        TenantIdentity(self.tenant_id)
        if self.account_id is not None:
            AccountIdentity(self.tenant_id, self.account_id)
        if self.user_id is not None:
            UserIdentity(self.user_id, self.tenant_id)
        requirement = READ_REQUIREMENTS[self.action]
        if requirement.account_scoped and self.account_id is None and (
            self.action is not ReadAction.PORTFOLIO_SUMMARY
        ):
            raise ValueError(f"{self.action.value} requires account_id")
        if not requirement.account_scoped and self.account_id is not None:
            raise ValueError(f"{self.action.value} cannot carry account_id")
        if requirement.user_scoped and self.user_id is None:
            raise ValueError(f"{self.action.value} requires user_id")
        if not requirement.user_scoped and self.user_id is not None:
            raise ValueError(f"{self.action.value} cannot carry user_id")


@dataclass(frozen=True)
class AuthorizationDecision:
    allowed: bool
    code: AuthorizationCode
    authorized_account_ids: tuple[str, ...] = ()
    tenant_admin: bool = False
    canonical_admin_authorized: bool = field(default=False, init=False)
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if type(self.allowed) is not bool:
            raise ValueError("allowed must be boolean")
        if not isinstance(self.code, AuthorizationCode):
            raise ValueError("code must be an AuthorizationCode")
        if self.allowed != (self.code is AuthorizationCode.ALLOWED):
            raise ValueError("authorization code does not match allowed state")
        if not isinstance(self.authorized_account_ids, tuple):
            raise ValueError("authorized_account_ids must be an immutable tuple")
        if tuple(sorted(set(self.authorized_account_ids))) != self.authorized_account_ids:
            raise ValueError("authorized_account_ids must be sorted and unique")
        if not self.allowed and self.authorized_account_ids:
            raise ValueError("denied decisions cannot expose authorized accounts")
        if type(self.tenant_admin) is not bool:
            raise ValueError("tenant_admin must be boolean")


def _decision(
    code: AuthorizationCode,
    *,
    account_ids: tuple[str, ...] = (),
    tenant_admin: bool = False,
) -> AuthorizationDecision:
    return AuthorizationDecision(
        allowed=code is AuthorizationCode.ALLOWED,
        code=code,
        authorized_account_ids=account_ids,
        tenant_admin=tenant_admin,
    )


@dataclass(frozen=True)
class ReadAuthorizationBoundary:
    """Known-account authorization service with no mutation capabilities."""

    known_accounts: frozenset[AccountIdentity]

    def __post_init__(self) -> None:
        if not isinstance(self.known_accounts, frozenset) or any(
            not isinstance(account, AccountIdentity) for account in self.known_accounts
        ):
            raise ValueError("known_accounts must be an immutable AccountIdentity set")

    def evaluate(
        self,
        principal: AuthorizationPrincipal | None,
        request: ReadRequest,
    ) -> AuthorizationDecision:
        if not isinstance(request, ReadRequest):
            raise ValueError("request must be a ReadRequest")
        if principal is None:
            return _decision(AuthorizationCode.MISSING_AUTH)
        if not isinstance(principal, AuthorizationPrincipal):
            return _decision(AuthorizationCode.MISSING_AUTH)
        if principal.identity.status is not UserStatus.ACTIVE:
            return _decision(AuthorizationCode.PRINCIPAL_INACTIVE)
        if principal.identity.tenant_id != request.tenant_id:
            return _decision(AuthorizationCode.TENANT_MISMATCH)

        is_tenant_admin = UserRole.TENANT_ADMIN in principal.roles
        requirement = READ_REQUIREMENTS[request.action]
        if requirement.user_scoped and (
            request.user_id != principal.identity.user_id and not is_tenant_admin
        ):
            return _decision(AuthorizationCode.USER_SCOPE_DENIED)
        if requirement.permission not in principal.permissions:
            return _decision(AuthorizationCode.PERMISSION_MISSING)
        if (
            requirement.entitlement is not None
            and requirement.entitlement not in principal.entitlements
        ):
            return _decision(AuthorizationCode.ENTITLEMENT_MISSING)

        if not requirement.account_scoped:
            return _decision(
                AuthorizationCode.ALLOWED,
                tenant_admin=is_tenant_admin,
            )

        known_for_tenant = frozenset(
            account.account_id
            for account in self.known_accounts
            if account.tenant_id == request.tenant_id
        )
        if request.account_id is not None:
            if request.account_id not in known_for_tenant:
                return _decision(AuthorizationCode.ACCOUNT_UNKNOWN)
            if not principal.account_scope.allows(request.account_id):
                return _decision(AuthorizationCode.ACCOUNT_SCOPE_DENIED)
            return _decision(
                AuthorizationCode.ALLOWED,
                account_ids=(request.account_id,),
                tenant_admin=is_tenant_admin,
            )

        visible = tuple(sorted(
            account_id
            for account_id in known_for_tenant
            if principal.account_scope.allows(account_id)
        ))
        if not visible:
            return _decision(AuthorizationCode.NO_ACCOUNTS_AUTHORIZED)
        return _decision(
            AuthorizationCode.ALLOWED,
            account_ids=visible,
            tenant_admin=is_tenant_admin,
        )
