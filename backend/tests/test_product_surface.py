"""Product roles consume canonical membership decisions and remain read-only."""

from datetime import datetime, timezone

from backend.entitlements import (
    AccountEntitlementLimits,
    DashboardAccess,
    FeatureEntitlement,
    SignalEntitlementLimits,
    UserIdentity,
    UserRole,
)
from backend.memberships import (
    MembershipPlan,
    MembershipRecord,
    MembershipStatus,
    project_membership_entitlements,
)
from backend.product import (
    ProductDecisionCode,
    ProductSurface,
    ProductTier,
    resolve_product_access,
)


NOW = datetime(2026, 10, 4, tzinfo=timezone.utc)
START = datetime(2026, 10, 1, tzinfo=timezone.utc)
END = datetime(2026, 11, 1, tzinfo=timezone.utc)


def projection(plan_id="FREE", *, features=True, active=True, roles=None):
    plan = MembershipPlan(
        plan_id=plan_id,
        version="1",
        features=frozenset({FeatureEntitlement.DASHBOARD}) if features else frozenset(),
        account_limits=AccountEntitlementLimits(0, 0),
        signal_limits=SignalEntitlementLimits(0),
        dashboard_access=DashboardAccess.READ_ONLY,
    )
    record = MembershipRecord(
        membership_id="product-member",
        tenant_id="tenant-1",
        user_id="user-1",
        plan=plan,
        status=MembershipStatus.ACTIVE if active else MembershipStatus.SUSPENDED,
        effective_from=START,
        effective_until=END,
        grace_ends_at=END,
    )
    return project_membership_entitlements(
        record,
        UserIdentity("user-1", "tenant-1"),
        roles or frozenset({UserRole.VIEWER}),
        NOW,
    )


def test_all_product_tiers_use_canonical_read_only_dashboard_entitlement():
    for tier in ProductTier:
        roles = frozenset({UserRole.TENANT_ADMIN}) if tier == ProductTier.ADMIN else None
        snapshot = resolve_product_access(projection(tier.value, roles=roles))
        assert snapshot.tier == tier
        for surface in ProductSurface:
            decision = snapshot.decisions[surface]
            if surface in {ProductSurface.HOME, ProductSurface.MARKETS}:
                assert decision.code == ProductDecisionCode.ALLOWED
            elif surface == ProductSurface.MEDAR:
                assert decision.code == ProductDecisionCode.SESSION_INVALID
            else:
                assert decision.code == ProductDecisionCode.SURFACE_NOT_READY
        assert snapshot.canonical_admin_authorized is False
        assert snapshot.paper_authorized is False
        assert snapshot.live_authorized is False


def test_unknown_inactive_and_unentitled_memberships_fail_closed():
    for source in (None, projection("other"), projection(active=False), projection(features=False)):
        snapshot = resolve_product_access(source)
        assert all(not decision.allowed for decision in snapshot.decisions.values())


def test_admin_tier_requires_server_role_and_does_not_grant_admin_authority():
    snapshot = resolve_product_access(projection("ADMIN"))
    assert all(decision.code == ProductDecisionCode.ADMIN_ROLE_MISSING
               for surface, decision in snapshot.decisions.items() if surface != ProductSurface.MEDAR)
    assert snapshot.decisions[ProductSurface.MEDAR].code == ProductDecisionCode.ENTITLEMENT_REQUIRED
    assert snapshot.canonical_admin_authorized is False
