"""Read-only membership policy and entitlement projection foundation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import re
from typing import Protocol

from backend.entitlements import (
    AccountEntitlementLimits,
    DashboardAccess,
    FeatureEntitlement,
    NotificationAccess,
    SignalEntitlementLimits,
    UserEntitlementProfile,
    UserIdentity,
    UserRole,
    permissions_for_roles,
)


class MembershipStatus(str, Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class MembershipLifecycleState(str, Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    GRACE = "GRACE"
    SUSPENDED = "SUSPENDED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class MembershipResolutionCode(str, Enum):
    ENTITLED = "ENTITLED"
    INACTIVE = "INACTIVE"
    NOT_FOUND = "NOT_FOUND"
    ADAPTER_UNAVAILABLE = "ADAPTER_UNAVAILABLE"
    INVALID_ADAPTER_RESULT = "INVALID_ADAPTER_RESULT"
    IDENTITY_MISMATCH = "IDENTITY_MISMATCH"


_OPAQUE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


def _opaque(value: str, name: str) -> None:
    if not isinstance(value, str) or _OPAQUE_ID.fullmatch(value) is None:
        raise ValueError(f"{name} must be a safe opaque identifier")


def _aware(value: datetime, name: str) -> None:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(f"{name} must be timezone-aware")


@dataclass(frozen=True)
class MembershipPlan:
    plan_id: str
    version: str
    features: frozenset[FeatureEntitlement]
    account_limits: AccountEntitlementLimits
    signal_limits: SignalEntitlementLimits
    dashboard_access: DashboardAccess = DashboardAccess.NONE
    notification_access: NotificationAccess = NotificationAccess.NONE

    def __post_init__(self) -> None:
        _opaque(self.plan_id, "plan_id")
        _opaque(self.version, "version")
        if not isinstance(self.features, frozenset) or any(
            not isinstance(feature, FeatureEntitlement) for feature in self.features
        ):
            raise ValueError("plan features must be an immutable FeatureEntitlement set")
        if not isinstance(self.account_limits, AccountEntitlementLimits):
            raise ValueError("plan account limits are required")
        if not isinstance(self.signal_limits, SignalEntitlementLimits):
            raise ValueError("plan signal limits are required")
        if not isinstance(self.dashboard_access, DashboardAccess):
            raise ValueError("invalid plan dashboard access")
        if not isinstance(self.notification_access, NotificationAccess):
            raise ValueError("invalid plan notification access")


@dataclass(frozen=True)
class MembershipRecord:
    membership_id: str
    tenant_id: str
    user_id: str
    plan: MembershipPlan
    status: MembershipStatus
    effective_from: datetime
    effective_until: datetime
    grace_ends_at: datetime
    record_version: str = "1"

    def __post_init__(self) -> None:
        _opaque(self.membership_id, "membership_id")
        _opaque(self.tenant_id, "tenant_id")
        _opaque(self.user_id, "user_id")
        _opaque(self.record_version, "record_version")
        if not isinstance(self.plan, MembershipPlan):
            raise ValueError("membership plan is required")
        if not isinstance(self.status, MembershipStatus):
            raise ValueError("invalid membership status")
        _aware(self.effective_from, "effective_from")
        _aware(self.effective_until, "effective_until")
        _aware(self.grace_ends_at, "grace_ends_at")
        if self.effective_until <= self.effective_from:
            raise ValueError("membership effective window must be positive")
        if self.grace_ends_at < self.effective_until:
            raise ValueError("membership grace cannot end before effective access")


@dataclass(frozen=True)
class MembershipEvaluation:
    lifecycle_state: MembershipLifecycleState
    entitled: bool
    evaluated_at: datetime
    canonical_admin_authorized: bool = field(default=False, init=False)
    execution_authorized: bool = field(default=False, init=False)
    billing_mutation_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.lifecycle_state, MembershipLifecycleState):
            raise ValueError("invalid membership lifecycle state")
        if type(self.entitled) is not bool:
            raise ValueError("entitled must be boolean")
        _aware(self.evaluated_at, "evaluated_at")
        expected = self.lifecycle_state in (
            MembershipLifecycleState.ACTIVE,
            MembershipLifecycleState.GRACE,
        )
        if self.entitled != expected:
            raise ValueError("membership entitlement does not match lifecycle state")


@dataclass(frozen=True)
class MembershipEntitlementProjection:
    code: MembershipResolutionCode
    lifecycle_state: MembershipLifecycleState | None
    profile: UserEntitlementProfile | None
    membership_id: str | None = None
    plan_id: str | None = None
    plan_version: str | None = None
    canonical_admin_authorized: bool = field(default=False, init=False)
    execution_authorized: bool = field(default=False, init=False)
    billing_mutation_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.code, MembershipResolutionCode):
            raise ValueError("invalid membership resolution code")
        if self.lifecycle_state is not None and not isinstance(
            self.lifecycle_state,
            MembershipLifecycleState,
        ):
            raise ValueError("invalid projected lifecycle state")
        for name in ("membership_id", "plan_id", "plan_version"):
            value = getattr(self, name)
            if value is not None:
                _opaque(value, name)
        identifiers = (self.membership_id, self.plan_id, self.plan_version)
        if any(value is not None for value in identifiers) and not all(
            value is not None for value in identifiers
        ):
            raise ValueError("membership projection identifiers must be all or none")
        entitled = self.code == MembershipResolutionCode.ENTITLED
        if entitled != (self.profile is not None):
            raise ValueError("only entitled membership may include an entitlement profile")
        if entitled and self.lifecycle_state not in (
            MembershipLifecycleState.ACTIVE,
            MembershipLifecycleState.GRACE,
        ):
            raise ValueError("entitled projection requires active or grace membership")
        if entitled and not all(value is not None for value in identifiers):
            raise ValueError("entitled projection requires membership identifiers")
        if self.code == MembershipResolutionCode.INACTIVE and (
            self.lifecycle_state is None
            or any(value is None for value in identifiers)
        ):
            raise ValueError("inactive projection requires lifecycle and membership identity")
        if self.code == MembershipResolutionCode.IDENTITY_MISMATCH and (
            self.lifecycle_state is not None
            or any(value is None for value in identifiers)
        ):
            raise ValueError("identity mismatch requires membership identity only")
        if self.code in (
            MembershipResolutionCode.NOT_FOUND,
            MembershipResolutionCode.ADAPTER_UNAVAILABLE,
            MembershipResolutionCode.INVALID_ADAPTER_RESULT,
        ) and (
            self.lifecycle_state is not None
            or any(value is not None for value in identifiers)
        ):
            raise ValueError("unresolved membership cannot include membership state")


class MembershipReadAdapter(Protocol):
    def get_membership(
        self,
        tenant_id: str,
        user_id: str,
    ) -> MembershipRecord | None: ...


def evaluate_membership(
    membership: MembershipRecord,
    evaluated_at: datetime,
) -> MembershipEvaluation:
    if not isinstance(membership, MembershipRecord):
        raise ValueError("membership record is required")
    _aware(evaluated_at, "evaluated_at")

    if membership.status == MembershipStatus.CANCELLED:
        state = MembershipLifecycleState.CANCELLED
    elif membership.status == MembershipStatus.SUSPENDED:
        state = MembershipLifecycleState.SUSPENDED
    elif membership.status == MembershipStatus.EXPIRED:
        state = MembershipLifecycleState.EXPIRED
    elif evaluated_at < membership.effective_from:
        state = MembershipLifecycleState.PENDING
    elif evaluated_at >= membership.grace_ends_at:
        state = MembershipLifecycleState.EXPIRED
    elif membership.status == MembershipStatus.PENDING:
        state = MembershipLifecycleState.PENDING
    elif evaluated_at < membership.effective_until:
        state = MembershipLifecycleState.ACTIVE
    else:
        state = MembershipLifecycleState.GRACE

    return MembershipEvaluation(
        lifecycle_state=state,
        entitled=state in (
            MembershipLifecycleState.ACTIVE,
            MembershipLifecycleState.GRACE,
        ),
        evaluated_at=evaluated_at,
    )


def _projection(
    code: MembershipResolutionCode,
    *,
    membership: MembershipRecord | None = None,
    state: MembershipLifecycleState | None = None,
    profile: UserEntitlementProfile | None = None,
) -> MembershipEntitlementProjection:
    return MembershipEntitlementProjection(
        code=code,
        lifecycle_state=state,
        profile=profile,
        membership_id=membership.membership_id if membership is not None else None,
        plan_id=membership.plan.plan_id if membership is not None else None,
        plan_version=membership.plan.version if membership is not None else None,
    )


def project_membership_entitlements(
    membership: MembershipRecord,
    identity: UserIdentity,
    roles: frozenset[UserRole],
    evaluated_at: datetime,
) -> MembershipEntitlementProjection:
    if not isinstance(membership, MembershipRecord):
        raise ValueError("membership record is required")
    if not isinstance(identity, UserIdentity):
        raise ValueError("user identity is required")
    permissions_for_roles(roles)
    if (
        membership.tenant_id != identity.tenant_id
        or membership.user_id != identity.user_id
    ):
        return _projection(
            MembershipResolutionCode.IDENTITY_MISMATCH,
            membership=membership,
        )
    evaluation = evaluate_membership(membership, evaluated_at)
    if not evaluation.entitled:
        return _projection(
            MembershipResolutionCode.INACTIVE,
            membership=membership,
            state=evaluation.lifecycle_state,
        )
    plan = membership.plan
    profile = UserEntitlementProfile(
        identity=identity,
        roles=roles,
        features=plan.features,
        account_limits=plan.account_limits,
        signal_limits=plan.signal_limits,
        dashboard_access=plan.dashboard_access,
        notification_access=plan.notification_access,
    )
    return _projection(
        MembershipResolutionCode.ENTITLED,
        membership=membership,
        state=evaluation.lifecycle_state,
        profile=profile,
    )


def resolve_membership_entitlements(
    adapter: MembershipReadAdapter,
    identity: UserIdentity,
    roles: frozenset[UserRole],
    evaluated_at: datetime,
) -> MembershipEntitlementProjection:
    if not isinstance(identity, UserIdentity):
        raise ValueError("user identity is required")
    permissions_for_roles(roles)
    _aware(evaluated_at, "evaluated_at")
    try:
        membership = adapter.get_membership(identity.tenant_id, identity.user_id)
    except Exception:
        return _projection(MembershipResolutionCode.ADAPTER_UNAVAILABLE)
    if membership is None:
        return _projection(MembershipResolutionCode.NOT_FOUND)
    if not isinstance(membership, MembershipRecord):
        return _projection(MembershipResolutionCode.INVALID_ADAPTER_RESULT)
    return project_membership_entitlements(
        membership,
        identity,
        roles,
        evaluated_at,
    )
