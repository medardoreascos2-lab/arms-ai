"""Product visibility never grants authentication, account, PAPER, or LIVE authority."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from types import MappingProxyType
from typing import Mapping

from backend.entitlements import FeatureEntitlement, UserRole, evaluate_dashboard_access
from backend.memberships import (
    MembershipEntitlementProjection,
    MembershipLifecycleState,
    MembershipResolutionCode,
)
from backend.product.customer_session import (
    LOCAL_TEST_ONLY,
    CustomerSessionProvider,
    TrustedCustomerSession,
)


class ProductTier(str, Enum):
    FREE = "FREE"
    PRO = "PRO"
    PREMIUM = "PREMIUM"
    ELITE = "ELITE"
    ADMIN = "ADMIN"


class ProductSurface(str, Enum):
    HOME = "HOME"
    MEDAR = "MEDAR"
    MARKETS = "MARKETS"
    TRADING = "TRADING"
    PORTFOLIO = "PORTFOLIO"
    COACH = "COACH"
    RESEARCH = "RESEARCH"
    ALERTS = "ALERTS"
    MEMORY = "MEMORY"
    SETTINGS = "SETTINGS"


class ProductDecisionCode(str, Enum):
    ALLOWED = "ALLOWED"
    MEMBERSHIP_UNAVAILABLE = "MEMBERSHIP_UNAVAILABLE"
    UNKNOWN_PLAN = "UNKNOWN_PLAN"
    ADMIN_ROLE_MISSING = "ADMIN_ROLE_MISSING"
    DASHBOARD_ENTITLEMENT_MISSING = "DASHBOARD_ENTITLEMENT_MISSING"
    AVAILABLE_LOCAL_TEST = "AVAILABLE_LOCAL_TEST"
    SURFACE_NOT_READY = "SURFACE_NOT_READY"
    ENTITLEMENT_REQUIRED = "ENTITLEMENT_REQUIRED"
    SESSION_INVALID = "SESSION_INVALID"
    MEDAR_UNAVAILABLE = "MEDAR_UNAVAILABLE"


@dataclass(frozen=True)
class ProductDecision:
    allowed: bool
    code: ProductDecisionCode

    def __post_init__(self) -> None:
        if self.allowed != (self.code in (
            ProductDecisionCode.ALLOWED, ProductDecisionCode.AVAILABLE_LOCAL_TEST
        )):
            raise ValueError("product decision code must match allowed state")


@dataclass(frozen=True)
class ProductAccessSnapshot:
    tier: ProductTier | None
    decisions: Mapping[ProductSurface, ProductDecision]
    canonical_admin_authorized: bool = field(default=False, init=False)
    paper_authorized: bool = field(default=False, init=False)
    live_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if set(self.decisions) != set(ProductSurface):
            raise ValueError("every product surface requires a decision")
        object.__setattr__(self, "decisions", MappingProxyType(dict(self.decisions)))


_READ_ONLY_SURFACES = frozenset({ProductSurface.HOME, ProductSurface.MARKETS})


def _decision(code: ProductDecisionCode) -> ProductDecision:
    return ProductDecision(
        code in (ProductDecisionCode.ALLOWED, ProductDecisionCode.AVAILABLE_LOCAL_TEST),
        code,
    )


def _denied(code: ProductDecisionCode, tier: ProductTier | None = None) -> ProductAccessSnapshot:
    decisions = {surface: _decision(code) for surface in ProductSurface}
    decisions[ProductSurface.MEDAR] = _decision(ProductDecisionCode.ENTITLEMENT_REQUIRED)
    return ProductAccessSnapshot(tier=tier, decisions=decisions)


def _medar_decision(
    projection: MembershipEntitlementProjection,
    session: TrustedCustomerSession | None,
    provider: CustomerSessionProvider | None,
    at: datetime | None,
    runtime_available: bool,
) -> ProductDecision:
    if (
        not isinstance(session, TrustedCustomerSession)
        or provider is None
        or not isinstance(at, datetime)
        or at.tzinfo is None
        or at.utcoffset() != timedelta(0)
    ):
        return _decision(ProductDecisionCode.SESSION_INVALID)
    try:
        if provider.validate_session(session.session_id, at) is not session:
            return _decision(ProductDecisionCode.SESSION_INVALID)
        identity = provider.resolve_identity(session, at)
        tenant_id = provider.resolve_tenant(session, at)
        roles = provider.resolve_roles(session, at)
        entitlements = provider.resolve_entitlements(session, at)
    except Exception:
        return _decision(ProductDecisionCode.SESSION_INVALID)
    if (
        session.auth_source != LOCAL_TEST_ONLY
        or identity.user_id != session.user_id
        or identity.tenant_id != session.tenant_id
        or tenant_id != session.tenant_id
        or roles != session.roles
        or entitlements != session.entitlements
        or projection.profile is None
        or projection.profile.identity != identity
        or projection.profile.roles != roles
    ):
        return _decision(ProductDecisionCode.SESSION_INVALID)
    if (
        projection.code != MembershipResolutionCode.ENTITLED
        or projection.lifecycle_state != MembershipLifecycleState.ACTIVE
        or FeatureEntitlement.MEDAR_CONVERSATION not in entitlements
        or FeatureEntitlement.MEDAR_CONVERSATION not in projection.profile.features
    ):
        return _decision(ProductDecisionCode.ENTITLEMENT_REQUIRED)
    if not runtime_available:
        return _decision(ProductDecisionCode.MEDAR_UNAVAILABLE)
    return _decision(ProductDecisionCode.AVAILABLE_LOCAL_TEST)


def resolve_product_access(
    projection: MembershipEntitlementProjection | None,
    *,
    customer_session: TrustedCustomerSession | None = None,
    session_provider: CustomerSessionProvider | None = None,
    evaluated_at: datetime | None = None,
    medar_runtime_available: bool = False,
) -> ProductAccessSnapshot:
    """Project server-resolved visibility. MEDAR remains local test only."""
    if (
        not isinstance(projection, MembershipEntitlementProjection)
        or projection.code != MembershipResolutionCode.ENTITLED
        or projection.profile is None
    ):
        snapshot = _denied(ProductDecisionCode.MEMBERSHIP_UNAVAILABLE)
        decisions = dict(snapshot.decisions)
        decisions[ProductSurface.MEDAR] = _decision(
            ProductDecisionCode.SESSION_INVALID if customer_session is None
            else ProductDecisionCode.ENTITLEMENT_REQUIRED
        )
        return ProductAccessSnapshot(None, decisions)
    try:
        tier = ProductTier(projection.plan_id)
    except (ValueError, TypeError):
        return _denied(ProductDecisionCode.UNKNOWN_PLAN)
    if tier == ProductTier.ADMIN and UserRole.TENANT_ADMIN not in projection.profile.roles:
        return _denied(ProductDecisionCode.ADMIN_ROLE_MISSING, tier)

    dashboard = evaluate_dashboard_access(projection.profile)
    decisions = {}
    for surface in ProductSurface:
        if surface == ProductSurface.MEDAR:
            decisions[surface] = _medar_decision(
                projection, customer_session, session_provider,
                evaluated_at, medar_runtime_available,
            )
        elif surface not in _READ_ONLY_SURFACES:
            decisions[surface] = _decision(ProductDecisionCode.SURFACE_NOT_READY)
        elif not dashboard.allowed:
            decisions[surface] = _decision(ProductDecisionCode.DASHBOARD_ENTITLEMENT_MISSING)
        else:
            decisions[surface] = _decision(ProductDecisionCode.ALLOWED)
    return ProductAccessSnapshot(tier=tier, decisions=decisions)
