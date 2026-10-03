"""Read-only membership policy foundation tests."""

from dataclasses import FrozenInstanceError, fields
from datetime import datetime, timedelta, timezone

import pytest

from backend.entitlements import (
    AccountEntitlementLimits,
    DashboardAccess,
    FeatureEntitlement,
    NotificationAccess,
    SignalEntitlementLimits,
    UserIdentity,
    UserRole,
)
from backend.memberships import (
    MembershipEntitlementProjection,
    MembershipLifecycleState,
    MembershipPlan,
    MembershipRecord,
    MembershipResolutionCode,
    MembershipStatus,
    evaluate_membership,
    project_membership_entitlements,
    resolve_membership_entitlements,
)


START = datetime(2026, 10, 1, tzinfo=timezone.utc)
END = datetime(2026, 11, 1, tzinfo=timezone.utc)
GRACE_END = datetime(2026, 11, 8, tzinfo=timezone.utc)


def plan():
    return MembershipPlan(
        plan_id="professional",
        version="2026-10",
        features=frozenset({
            FeatureEntitlement.DASHBOARD,
            FeatureEntitlement.MULTI_ACCOUNT,
            FeatureEntitlement.SIGNALS,
            FeatureEntitlement.NOTIFICATIONS,
        }),
        account_limits=AccountEntitlementLimits(5, 3),
        signal_limits=SignalEntitlementLimits(20),
        dashboard_access=DashboardAccess.READ_ONLY,
        notification_access=NotificationAccess.READ_ONLY,
    )


def membership(
    *,
    status=MembershipStatus.ACTIVE,
    effective_from=START,
    effective_until=END,
    grace_ends_at=GRACE_END,
    tenant_id="tenant-1",
    user_id="user-1",
):
    return MembershipRecord(
        membership_id="membership-1",
        tenant_id=tenant_id,
        user_id=user_id,
        plan=plan(),
        status=status,
        effective_from=effective_from,
        effective_until=effective_until,
        grace_ends_at=grace_ends_at,
    )


def identity():
    return UserIdentity("user-1", "tenant-1")


def test_plan_and_membership_are_immutable_and_have_no_billing_fields():
    member = membership()
    plan_fields = {item.name for item in fields(MembershipPlan)}
    record_fields = {item.name for item in fields(MembershipRecord)}
    forbidden = {"price", "currency", "stripe_id", "payment_method", "credential"}
    assert plan_fields.isdisjoint(forbidden)
    assert record_fields.isdisjoint(forbidden)
    with pytest.raises(FrozenInstanceError):
        member.status = MembershipStatus.CANCELLED
    with pytest.raises(FrozenInstanceError):
        member.plan.features = frozenset()


def test_membership_dates_require_aware_ordered_windows():
    naive = datetime(2026, 10, 1)
    with pytest.raises(ValueError, match="timezone-aware"):
        membership(effective_from=naive)
    with pytest.raises(ValueError, match="positive"):
        membership(effective_until=START)
    with pytest.raises(ValueError, match="grace"):
        membership(grace_ends_at=END - timedelta(seconds=1))


def test_active_grace_and_expired_boundaries_are_explicit():
    member = membership()
    before = evaluate_membership(member, START - timedelta(seconds=1))
    at_start = evaluate_membership(member, START)
    before_end = evaluate_membership(member, END - timedelta(microseconds=1))
    at_end = evaluate_membership(member, END)
    before_grace_end = evaluate_membership(
        member,
        GRACE_END - timedelta(microseconds=1),
    )
    at_grace_end = evaluate_membership(member, GRACE_END)
    assert before.lifecycle_state == MembershipLifecycleState.PENDING
    assert at_start.lifecycle_state == MembershipLifecycleState.ACTIVE
    assert before_end.lifecycle_state == MembershipLifecycleState.ACTIVE
    assert at_end.lifecycle_state == MembershipLifecycleState.GRACE
    assert before_grace_end.lifecycle_state == MembershipLifecycleState.GRACE
    assert at_grace_end.lifecycle_state == MembershipLifecycleState.EXPIRED
    assert at_start.entitled and at_end.entitled
    assert not before.entitled and not at_grace_end.entitled


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (MembershipStatus.PENDING, MembershipLifecycleState.PENDING),
        (MembershipStatus.SUSPENDED, MembershipLifecycleState.SUSPENDED),
        (MembershipStatus.CANCELLED, MembershipLifecycleState.CANCELLED),
        (MembershipStatus.EXPIRED, MembershipLifecycleState.EXPIRED),
    ],
)
def test_persisted_nonactive_statuses_override_effective_access(status, expected):
    evaluation = evaluate_membership(membership(status=status), START + timedelta(days=1))
    assert evaluation.lifecycle_state == expected
    assert evaluation.entitled is False


def test_zero_length_grace_expires_at_effective_end():
    member = membership(grace_ends_at=END)
    evaluation = evaluate_membership(member, END)
    assert evaluation.lifecycle_state == MembershipLifecycleState.EXPIRED
    assert evaluation.entitled is False


@pytest.mark.parametrize(
    ("evaluated_at", "expected_state"),
    [
        (START, MembershipLifecycleState.ACTIVE),
        (END, MembershipLifecycleState.GRACE),
    ],
)
def test_active_and_grace_memberships_project_exact_plan_entitlements(
    evaluated_at,
    expected_state,
):
    member = membership()
    projection = project_membership_entitlements(
        member,
        identity(),
        frozenset({UserRole.OPERATOR}),
        evaluated_at,
    )
    assert projection.code == MembershipResolutionCode.ENTITLED
    assert projection.lifecycle_state == expected_state
    assert projection.profile.features == member.plan.features
    assert projection.profile.account_limits == member.plan.account_limits
    assert projection.profile.signal_limits == member.plan.signal_limits
    assert projection.profile.dashboard_access == member.plan.dashboard_access
    assert projection.profile.notification_access == member.plan.notification_access
    assert projection.canonical_admin_authorized is False
    assert projection.execution_authorized is False
    assert projection.billing_mutation_authorized is False


def test_expired_membership_projects_no_entitlement_profile():
    projection = project_membership_entitlements(
        membership(),
        identity(),
        frozenset({UserRole.OPERATOR}),
        GRACE_END,
    )
    assert projection.code == MembershipResolutionCode.INACTIVE
    assert projection.lifecycle_state == MembershipLifecycleState.EXPIRED
    assert projection.profile is None


def test_cross_user_membership_fails_closed_without_profile():
    projection = project_membership_entitlements(
        membership(user_id="different-user"),
        identity(),
        frozenset({UserRole.OPERATOR}),
        START,
    )
    assert projection.code == MembershipResolutionCode.IDENTITY_MISMATCH
    assert projection.lifecycle_state is None
    assert projection.profile is None


def test_cross_tenant_membership_fails_closed_without_profile():
    projection = project_membership_entitlements(
        membership(tenant_id="different-tenant"),
        identity(),
        frozenset({UserRole.OPERATOR}),
        START,
    )
    assert projection.code == MembershipResolutionCode.IDENTITY_MISMATCH
    assert projection.lifecycle_state is None
    assert projection.profile is None


class FakeReadAdapter:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def get_membership(self, tenant_id, user_id):
        self.calls.append((tenant_id, user_id))
        return self.result


def test_read_adapter_resolves_membership_without_mutation_methods():
    adapter = FakeReadAdapter(membership())
    projection = resolve_membership_entitlements(
        adapter,
        identity(),
        frozenset({UserRole.OPERATOR}),
        START,
    )
    assert projection.code == MembershipResolutionCode.ENTITLED
    assert adapter.calls == [("tenant-1", "user-1")]
    assert not hasattr(adapter, "create_subscription")
    assert not hasattr(adapter, "charge")
    assert not hasattr(adapter, "cancel")


@pytest.mark.parametrize(
    ("adapter", "expected"),
    [
        (FakeReadAdapter(None), MembershipResolutionCode.NOT_FOUND),
        (
            FakeReadAdapter({"membership": "invalid"}),
            MembershipResolutionCode.INVALID_ADAPTER_RESULT,
        ),
    ],
)
def test_missing_or_invalid_adapter_result_fails_closed(adapter, expected):
    projection = resolve_membership_entitlements(
        adapter,
        identity(),
        frozenset({UserRole.OPERATOR}),
        START,
    )
    assert projection.code == expected
    assert projection.profile is None
    assert projection.billing_mutation_authorized is False


def test_adapter_exception_fails_closed_without_exposing_error():
    class FailingAdapter:
        def get_membership(self, tenant_id, user_id):
            raise RuntimeError("secret provider detail")

    projection = resolve_membership_entitlements(
        FailingAdapter(),
        identity(),
        frozenset({UserRole.OPERATOR}),
        START,
    )
    assert projection.code == MembershipResolutionCode.ADAPTER_UNAVAILABLE
    assert projection.profile is None
    assert "secret" not in repr(projection)


def test_membership_evaluation_has_no_admin_execution_or_billing_authority():
    evaluation = evaluate_membership(membership(), START)
    assert evaluation.canonical_admin_authorized is False
    assert evaluation.execution_authorized is False
    assert evaluation.billing_mutation_authorized is False


def test_direct_projection_rejects_inconsistent_membership_state():
    with pytest.raises(ValueError, match="identifiers"):
        MembershipEntitlementProjection(
            code=MembershipResolutionCode.ENTITLED,
            lifecycle_state=MembershipLifecycleState.ACTIVE,
            profile=project_membership_entitlements(
                membership(),
                identity(),
                frozenset({UserRole.OPERATOR}),
                START,
            ).profile,
        )
