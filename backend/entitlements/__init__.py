"""Phase 2 user identity and entitlement domain."""

from .domain import (
    ROLE_PERMISSIONS,
    AccountEntitlementLimits,
    DashboardAccess,
    EntitlementDecision,
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
