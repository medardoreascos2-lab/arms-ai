"""Immutable Phase 2 user entitlement domain without authentication authority."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import re
from types import MappingProxyType
from typing import Mapping


class UserStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    DISABLED = "DISABLED"


class UserRole(str, Enum):
    VIEWER = "VIEWER"
    ANALYST = "ANALYST"
    OPERATOR = "OPERATOR"
    TENANT_ADMIN = "TENANT_ADMIN"


class Permission(str, Enum):
    DASHBOARD_READ = "DASHBOARD_READ"
    ANALYTICS_READ = "ANALYTICS_READ"
    SIGNAL_READ = "SIGNAL_READ"
    SIGNAL_CREATE = "SIGNAL_CREATE"
    ACCOUNT_PROFILE_READ = "ACCOUNT_PROFILE_READ"
    ACCOUNT_LINK = "ACCOUNT_LINK"
    NOTIFICATION_READ = "NOTIFICATION_READ"
    NOTIFICATION_TEST_DISPATCH = "NOTIFICATION_TEST_DISPATCH"
    ENTITLEMENT_READ = "ENTITLEMENT_READ"
    ENTITLEMENT_MANAGE = "ENTITLEMENT_MANAGE"


class FeatureEntitlement(str, Enum):
    DASHBOARD = "DASHBOARD"
    PROP_FIRM_POLICY = "PROP_FIRM_POLICY"
    MULTI_ACCOUNT = "MULTI_ACCOUNT"
    TRADE_JOURNAL_ANALYTICS = "TRADE_JOURNAL_ANALYTICS"
    SIGNALS = "SIGNALS"
    NOTIFICATIONS = "NOTIFICATIONS"
    TELEGRAM_TEST = "TELEGRAM_TEST"


class DashboardAccess(str, Enum):
    NONE = "NONE"
    READ_ONLY = "READ_ONLY"


class NotificationAccess(str, Enum):
    NONE = "NONE"
    READ_ONLY = "READ_ONLY"
    TEST_DISPATCH = "TEST_DISPATCH"


class EntitlementDecisionCode(str, Enum):
    ALLOWED = "ALLOWED"
    USER_INACTIVE = "USER_INACTIVE"
    PERMISSION_MISSING = "PERMISSION_MISSING"
    FEATURE_DISABLED = "FEATURE_DISABLED"
    ACCESS_DISABLED = "ACCESS_DISABLED"
    ACCOUNT_LIMIT_REACHED = "ACCOUNT_LIMIT_REACHED"
    ACTIVE_ACCOUNT_LIMIT_REACHED = "ACTIVE_ACCOUNT_LIMIT_REACHED"
    SIGNAL_LIMIT_REACHED = "SIGNAL_LIMIT_REACHED"


ROLE_PERMISSIONS: Mapping[UserRole, frozenset[Permission]] = MappingProxyType({
    UserRole.VIEWER: frozenset({
        Permission.DASHBOARD_READ,
        Permission.ENTITLEMENT_READ,
    }),
    UserRole.ANALYST: frozenset({
        Permission.DASHBOARD_READ,
        Permission.ANALYTICS_READ,
        Permission.SIGNAL_READ,
        Permission.ENTITLEMENT_READ,
    }),
    UserRole.OPERATOR: frozenset({
        Permission.DASHBOARD_READ,
        Permission.ANALYTICS_READ,
        Permission.SIGNAL_READ,
        Permission.SIGNAL_CREATE,
        Permission.ACCOUNT_PROFILE_READ,
        Permission.ACCOUNT_LINK,
        Permission.NOTIFICATION_READ,
        Permission.NOTIFICATION_TEST_DISPATCH,
        Permission.ENTITLEMENT_READ,
    }),
    UserRole.TENANT_ADMIN: frozenset(Permission),
})


_OPAQUE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


def _validate_opaque_id(value: str, name: str) -> None:
    if not isinstance(value, str) or _OPAQUE_ID.fullmatch(value) is None:
        raise ValueError(f"{name} must be a safe opaque identifier")


def _validate_nonnegative_integer(value: int, name: str) -> None:
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer")


@dataclass(frozen=True)
class UserIdentity:
    user_id: str
    tenant_id: str
    identity_version: str = "1"
    status: UserStatus = UserStatus.ACTIVE

    def __post_init__(self) -> None:
        _validate_opaque_id(self.user_id, "user_id")
        _validate_opaque_id(self.tenant_id, "tenant_id")
        _validate_opaque_id(self.identity_version, "identity_version")
        if not isinstance(self.status, UserStatus):
            raise ValueError("invalid user status")


@dataclass(frozen=True)
class AccountEntitlementLimits:
    maximum_linked_accounts: int
    maximum_active_accounts: int

    def __post_init__(self) -> None:
        _validate_nonnegative_integer(
            self.maximum_linked_accounts,
            "maximum_linked_accounts",
        )
        _validate_nonnegative_integer(
            self.maximum_active_accounts,
            "maximum_active_accounts",
        )
        if self.maximum_active_accounts > self.maximum_linked_accounts:
            raise ValueError("active account limit cannot exceed linked account limit")


@dataclass(frozen=True)
class SignalEntitlementLimits:
    maximum_daily_signal_candidates: int

    def __post_init__(self) -> None:
        _validate_nonnegative_integer(
            self.maximum_daily_signal_candidates,
            "maximum_daily_signal_candidates",
        )


def permissions_for_roles(roles: frozenset[UserRole]) -> frozenset[Permission]:
    if not isinstance(roles, frozenset) or any(
        not isinstance(role, UserRole) for role in roles
    ):
        raise ValueError("roles must be an immutable UserRole set")
    return frozenset(
        permission
        for role in roles
        for permission in ROLE_PERMISSIONS[role]
    )


@dataclass(frozen=True)
class UserEntitlementProfile:
    identity: UserIdentity
    roles: frozenset[UserRole]
    features: frozenset[FeatureEntitlement]
    account_limits: AccountEntitlementLimits
    signal_limits: SignalEntitlementLimits
    dashboard_access: DashboardAccess = DashboardAccess.NONE
    notification_access: NotificationAccess = NotificationAccess.NONE
    permissions: frozenset[Permission] = field(init=False)
    canonical_admin_authorized: bool = field(default=False, init=False)
    execution_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.identity, UserIdentity):
            raise ValueError("user identity is required")
        if not self.roles:
            raise ValueError("at least one role is required")
        computed_permissions = permissions_for_roles(self.roles)
        if not isinstance(self.features, frozenset) or any(
            not isinstance(feature, FeatureEntitlement) for feature in self.features
        ):
            raise ValueError("features must be an immutable FeatureEntitlement set")
        if not isinstance(self.account_limits, AccountEntitlementLimits):
            raise ValueError("account limits are required")
        if not isinstance(self.signal_limits, SignalEntitlementLimits):
            raise ValueError("signal limits are required")
        if not isinstance(self.dashboard_access, DashboardAccess):
            raise ValueError("invalid dashboard access")
        if not isinstance(self.notification_access, NotificationAccess):
            raise ValueError("invalid notification access")
        object.__setattr__(self, "permissions", computed_permissions)


@dataclass(frozen=True)
class EntitlementDecision:
    allowed: bool
    code: EntitlementDecisionCode
    remaining_capacity: int | None = None
    canonical_admin_authorized: bool = field(default=False, init=False)
    execution_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if type(self.allowed) is not bool:
            raise ValueError("allowed must be boolean")
        if not isinstance(self.code, EntitlementDecisionCode):
            raise ValueError("invalid entitlement decision code")
        if self.remaining_capacity is not None:
            _validate_nonnegative_integer(self.remaining_capacity, "remaining_capacity")
        if self.allowed != (self.code == EntitlementDecisionCode.ALLOWED):
            raise ValueError("entitlement decision code does not match allowed state")


def _decision(
    code: EntitlementDecisionCode,
    remaining_capacity: int | None = None,
) -> EntitlementDecision:
    return EntitlementDecision(
        allowed=code == EntitlementDecisionCode.ALLOWED,
        code=code,
        remaining_capacity=remaining_capacity,
    )


def evaluate_permission(
    profile: UserEntitlementProfile,
    permission: Permission,
    *,
    feature: FeatureEntitlement | None = None,
) -> EntitlementDecision:
    if not isinstance(profile, UserEntitlementProfile):
        raise ValueError("user entitlement profile is required")
    if not isinstance(permission, Permission):
        raise ValueError("permission is required")
    if feature is not None and not isinstance(feature, FeatureEntitlement):
        raise ValueError("feature entitlement is invalid")
    if profile.identity.status != UserStatus.ACTIVE:
        return _decision(EntitlementDecisionCode.USER_INACTIVE)
    if permission not in profile.permissions:
        return _decision(EntitlementDecisionCode.PERMISSION_MISSING)
    if feature is not None and feature not in profile.features:
        return _decision(EntitlementDecisionCode.FEATURE_DISABLED)
    return _decision(EntitlementDecisionCode.ALLOWED)


def evaluate_dashboard_access(
    profile: UserEntitlementProfile,
) -> EntitlementDecision:
    base = evaluate_permission(
        profile,
        Permission.DASHBOARD_READ,
        feature=FeatureEntitlement.DASHBOARD,
    )
    if not base.allowed:
        return base
    if profile.dashboard_access != DashboardAccess.READ_ONLY:
        return _decision(EntitlementDecisionCode.ACCESS_DISABLED)
    return _decision(EntitlementDecisionCode.ALLOWED)


def evaluate_notification_access(
    profile: UserEntitlementProfile,
    *,
    test_dispatch: bool = False,
) -> EntitlementDecision:
    if type(test_dispatch) is not bool:
        raise ValueError("test_dispatch must be boolean")
    permission = (
        Permission.NOTIFICATION_TEST_DISPATCH
        if test_dispatch
        else Permission.NOTIFICATION_READ
    )
    base = evaluate_permission(
        profile,
        permission,
        feature=FeatureEntitlement.NOTIFICATIONS,
    )
    if not base.allowed:
        return base
    if test_dispatch and FeatureEntitlement.TELEGRAM_TEST not in profile.features:
        return _decision(EntitlementDecisionCode.FEATURE_DISABLED)
    required_access = (
        NotificationAccess.TEST_DISPATCH
        if test_dispatch
        else (NotificationAccess.READ_ONLY, NotificationAccess.TEST_DISPATCH)
    )
    if test_dispatch:
        has_access = profile.notification_access == required_access
    else:
        has_access = profile.notification_access in required_access
    if not has_access:
        return _decision(EntitlementDecisionCode.ACCESS_DISABLED)
    return _decision(EntitlementDecisionCode.ALLOWED)


def evaluate_account_capacity(
    profile: UserEntitlementProfile,
    *,
    linked_accounts: int,
    additional_accounts: int = 1,
) -> EntitlementDecision:
    _validate_nonnegative_integer(linked_accounts, "linked_accounts")
    if type(additional_accounts) is not int or additional_accounts < 1:
        raise ValueError("additional_accounts must be a positive integer")
    base = evaluate_permission(
        profile,
        Permission.ACCOUNT_LINK,
        feature=FeatureEntitlement.MULTI_ACCOUNT,
    )
    if not base.allowed:
        return base
    limit = profile.account_limits.maximum_linked_accounts
    if linked_accounts + additional_accounts > limit:
        return _decision(
            EntitlementDecisionCode.ACCOUNT_LIMIT_REACHED,
            max(0, limit - linked_accounts),
        )
    return _decision(
        EntitlementDecisionCode.ALLOWED,
        limit - linked_accounts - additional_accounts,
    )


def evaluate_active_account_capacity(
    profile: UserEntitlementProfile,
    *,
    active_accounts: int,
    additional_accounts: int = 1,
) -> EntitlementDecision:
    _validate_nonnegative_integer(active_accounts, "active_accounts")
    if type(additional_accounts) is not int or additional_accounts < 1:
        raise ValueError("additional_accounts must be a positive integer")
    base = evaluate_permission(
        profile,
        Permission.ACCOUNT_LINK,
        feature=FeatureEntitlement.MULTI_ACCOUNT,
    )
    if not base.allowed:
        return base
    limit = profile.account_limits.maximum_active_accounts
    if active_accounts + additional_accounts > limit:
        return _decision(
            EntitlementDecisionCode.ACTIVE_ACCOUNT_LIMIT_REACHED,
            max(0, limit - active_accounts),
        )
    return _decision(
        EntitlementDecisionCode.ALLOWED,
        limit - active_accounts - additional_accounts,
    )


def evaluate_signal_capacity(
    profile: UserEntitlementProfile,
    *,
    signal_candidates_today: int,
    additional_candidates: int = 1,
) -> EntitlementDecision:
    _validate_nonnegative_integer(signal_candidates_today, "signal_candidates_today")
    if type(additional_candidates) is not int or additional_candidates < 1:
        raise ValueError("additional_candidates must be a positive integer")
    base = evaluate_permission(
        profile,
        Permission.SIGNAL_CREATE,
        feature=FeatureEntitlement.SIGNALS,
    )
    if not base.allowed:
        return base
    limit = profile.signal_limits.maximum_daily_signal_candidates
    if signal_candidates_today + additional_candidates > limit:
        return _decision(
            EntitlementDecisionCode.SIGNAL_LIMIT_REACHED,
            max(0, limit - signal_candidates_today),
        )
    return _decision(
        EntitlementDecisionCode.ALLOWED,
        limit - signal_candidates_today - additional_candidates,
    )
