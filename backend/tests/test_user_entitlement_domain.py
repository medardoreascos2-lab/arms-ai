"""Phase 2 user identity, role, and entitlement domain tests."""

from dataclasses import FrozenInstanceError

import pytest

from backend.entitlements import (
    ROLE_PERMISSIONS,
    AccountEntitlementLimits,
    DashboardAccess,
    EntitlementDecisionCode,
    FeatureEntitlement,
    NotificationAccess,
    Permission,
    SignalEntitlementLimits,
    UserEntitlementProfile,
    UserIdentity,
    UserRole,
    UserStatus,
    evaluate_account_capacity,
    evaluate_active_account_capacity,
    evaluate_dashboard_access,
    evaluate_notification_access,
    evaluate_permission,
    evaluate_signal_capacity,
    permissions_for_roles,
)
from backend.security.admin_authorization_v2 import AdminAuthorizationV2


ALL_FEATURES = frozenset(FeatureEntitlement)


def profile(
    *,
    role=UserRole.OPERATOR,
    status=UserStatus.ACTIVE,
    features=ALL_FEATURES,
    dashboard=DashboardAccess.READ_ONLY,
    notifications=NotificationAccess.TEST_DISPATCH,
    linked_limit=3,
    active_limit=2,
    signal_limit=5,
):
    return UserEntitlementProfile(
        identity=UserIdentity("user-1", "tenant-1", status=status),
        roles=frozenset({role}),
        features=features,
        account_limits=AccountEntitlementLimits(linked_limit, active_limit),
        signal_limits=SignalEntitlementLimits(signal_limit),
        dashboard_access=dashboard,
        notification_access=notifications,
    )


def test_identity_and_profile_are_immutable_and_use_opaque_identifiers():
    entitlements = profile()
    assert entitlements.identity.user_id == "user-1"
    with pytest.raises(FrozenInstanceError):
        entitlements.identity.status = UserStatus.DISABLED
    with pytest.raises(FrozenInstanceError):
        entitlements.dashboard_access = DashboardAccess.NONE
    with pytest.raises(ValueError, match="opaque"):
        UserIdentity("user with spaces", "tenant-1")


def test_role_permissions_are_fixed_immutable_and_derived_only_from_roles():
    expected = permissions_for_roles(frozenset({UserRole.VIEWER, UserRole.ANALYST}))
    assert Permission.DASHBOARD_READ in expected
    assert Permission.ANALYTICS_READ in expected
    assert Permission.ACCOUNT_LINK not in expected
    assert profile(role=UserRole.OPERATOR).permissions == ROLE_PERMISSIONS[UserRole.OPERATOR]
    with pytest.raises(TypeError):
        ROLE_PERMISSIONS[UserRole.VIEWER] = frozenset()
    with pytest.raises(AttributeError):
        ROLE_PERMISSIONS[UserRole.VIEWER].add(Permission.ACCOUNT_LINK)


def test_mutable_or_empty_role_and_feature_inputs_are_rejected():
    base = profile()
    with pytest.raises(ValueError, match="role"):
        UserEntitlementProfile(
            base.identity,
            set({UserRole.OPERATOR}),
            base.features,
            base.account_limits,
            base.signal_limits,
        )
    with pytest.raises(ValueError, match="at least one"):
        UserEntitlementProfile(
            base.identity,
            frozenset(),
            base.features,
            base.account_limits,
            base.signal_limits,
        )
    with pytest.raises(ValueError, match="features"):
        UserEntitlementProfile(
            base.identity,
            base.roles,
            set(ALL_FEATURES),
            base.account_limits,
            base.signal_limits,
        )


def test_profile_and_every_decision_have_no_admin_or_execution_authority():
    entitlements = profile()
    decisions = (
        evaluate_dashboard_access(entitlements),
        evaluate_notification_access(entitlements),
        evaluate_notification_access(entitlements, test_dispatch=True),
        evaluate_account_capacity(entitlements, linked_accounts=0),
        evaluate_active_account_capacity(entitlements, active_accounts=0),
        evaluate_signal_capacity(entitlements, signal_candidates_today=0),
    )
    assert entitlements.canonical_admin_authorized is False
    assert entitlements.execution_authorized is False
    assert all(item.canonical_admin_authorized is False for item in decisions)
    assert all(item.execution_authorized is False for item in decisions)


@pytest.mark.parametrize("status", [UserStatus.SUSPENDED, UserStatus.DISABLED])
def test_inactive_users_fail_closed_for_all_access(status):
    entitlements = profile(status=status)
    decisions = (
        evaluate_dashboard_access(entitlements),
        evaluate_notification_access(entitlements, test_dispatch=True),
        evaluate_account_capacity(entitlements, linked_accounts=0),
        evaluate_signal_capacity(entitlements, signal_candidates_today=0),
    )
    assert all(not item.allowed for item in decisions)
    assert all(item.code == EntitlementDecisionCode.USER_INACTIVE for item in decisions)


def test_dashboard_requires_role_permission_feature_and_read_only_access():
    assert evaluate_dashboard_access(profile()).allowed
    missing_feature = profile(features=ALL_FEATURES - {FeatureEntitlement.DASHBOARD})
    assert evaluate_dashboard_access(missing_feature).code == (
        EntitlementDecisionCode.FEATURE_DISABLED
    )
    no_access = profile(dashboard=DashboardAccess.NONE)
    assert evaluate_dashboard_access(no_access).code == EntitlementDecisionCode.ACCESS_DISABLED


def test_notification_read_and_test_dispatch_have_independent_access_gates():
    read_only = profile(notifications=NotificationAccess.READ_ONLY)
    assert evaluate_notification_access(read_only).allowed
    assert evaluate_notification_access(read_only, test_dispatch=True).code == (
        EntitlementDecisionCode.ACCESS_DISABLED
    )
    no_telegram = profile(features=ALL_FEATURES - {FeatureEntitlement.TELEGRAM_TEST})
    assert evaluate_notification_access(no_telegram, test_dispatch=True).code == (
        EntitlementDecisionCode.FEATURE_DISABLED
    )
    no_notifications = profile(features=ALL_FEATURES - {FeatureEntitlement.NOTIFICATIONS})
    assert evaluate_notification_access(no_notifications, test_dispatch=True).code == (
        EntitlementDecisionCode.FEATURE_DISABLED
    )


def test_viewer_role_cannot_create_signals_link_accounts_or_test_dispatch():
    viewer = profile(role=UserRole.VIEWER)
    decisions = (
        evaluate_signal_capacity(viewer, signal_candidates_today=0),
        evaluate_account_capacity(viewer, linked_accounts=0),
        evaluate_notification_access(viewer, test_dispatch=True),
    )
    assert all(item.code == EntitlementDecisionCode.PERMISSION_MISSING for item in decisions)


def test_linked_and_active_account_limits_enforce_exact_boundaries():
    entitlements = profile(linked_limit=3, active_limit=2)
    linked = evaluate_account_capacity(entitlements, linked_accounts=1, additional_accounts=2)
    assert linked.allowed
    assert linked.remaining_capacity == 0
    linked_block = evaluate_account_capacity(entitlements, linked_accounts=3)
    assert linked_block.code == EntitlementDecisionCode.ACCOUNT_LIMIT_REACHED
    assert linked_block.remaining_capacity == 0
    active = evaluate_active_account_capacity(entitlements, active_accounts=1)
    assert active.allowed
    assert active.remaining_capacity == 0
    active_block = evaluate_active_account_capacity(entitlements, active_accounts=2)
    assert active_block.code == EntitlementDecisionCode.ACTIVE_ACCOUNT_LIMIT_REACHED


def test_daily_signal_limit_enforces_exact_boundary():
    entitlements = profile(signal_limit=5)
    allowed = evaluate_signal_capacity(
        entitlements,
        signal_candidates_today=3,
        additional_candidates=2,
    )
    assert allowed.allowed
    assert allowed.remaining_capacity == 0
    blocked = evaluate_signal_capacity(entitlements, signal_candidates_today=5)
    assert blocked.code == EntitlementDecisionCode.SIGNAL_LIMIT_REACHED
    assert blocked.remaining_capacity == 0


def test_zero_limits_disable_capacity_without_unlimited_sentinel_values():
    entitlements = profile(linked_limit=0, active_limit=0, signal_limit=0)
    assert evaluate_account_capacity(entitlements, linked_accounts=0).code == (
        EntitlementDecisionCode.ACCOUNT_LIMIT_REACHED
    )
    assert evaluate_active_account_capacity(entitlements, active_accounts=0).code == (
        EntitlementDecisionCode.ACTIVE_ACCOUNT_LIMIT_REACHED
    )
    assert evaluate_signal_capacity(entitlements, signal_candidates_today=0).code == (
        EntitlementDecisionCode.SIGNAL_LIMIT_REACHED
    )


@pytest.mark.parametrize("invalid", [-1, True, 1.5, "1"])
def test_capacity_inputs_reject_negative_bool_and_lossy_types(invalid):
    entitlements = profile()
    with pytest.raises(ValueError):
        evaluate_account_capacity(entitlements, linked_accounts=invalid)
    with pytest.raises(ValueError):
        evaluate_active_account_capacity(entitlements, active_accounts=invalid)
    with pytest.raises(ValueError):
        evaluate_signal_capacity(entitlements, signal_candidates_today=invalid)


def test_feature_and_permission_gates_are_independent():
    operator = profile(features=ALL_FEATURES - {FeatureEntitlement.SIGNALS})
    assert Permission.SIGNAL_CREATE in operator.permissions
    assert evaluate_permission(
        operator,
        Permission.SIGNAL_CREATE,
        feature=FeatureEntitlement.SIGNALS,
    ).code == EntitlementDecisionCode.FEATURE_DISABLED


def test_tenant_admin_profile_does_not_replace_canonical_admin_credential():
    tenant_admin = profile(role=UserRole.TENANT_ADMIN)
    canonical = AdminAuthorizationV2(token="canonical-admin-secret")
    assert Permission.ENTITLEMENT_MANAGE in tenant_admin.permissions
    assert tenant_admin.canonical_admin_authorized is False
    assert canonical.is_authorized(tenant_admin.identity.user_id) is False
