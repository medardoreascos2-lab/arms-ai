"""Product visibility never grants authentication, account, PAPER, or LIVE authority."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Mapping

from backend.entitlements import UserRole, evaluate_dashboard_access
from backend.memberships import MembershipEntitlementProjection, MembershipResolutionCode


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
    SURFACE_NOT_READY = "SURFACE_NOT_READY"


@dataclass(frozen=True)
class ProductDecision:
    allowed: bool
    code: ProductDecisionCode

    def __post_init__(self) -> None:
        if self.allowed != (self.code == ProductDecisionCode.ALLOWED):
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


# Routes limited to the product preview and analysis-only market page. Others await
# product endpoints and must remain unavailable regardless of tier.
_READ_ONLY_SURFACES = frozenset({
    ProductSurface.HOME,
    ProductSurface.MARKETS,
})


def _denied(code: ProductDecisionCode, tier: ProductTier | None = None) -> ProductAccessSnapshot:
    return ProductAccessSnapshot(
        tier=tier,
        decisions={surface: ProductDecision(False, code) for surface in ProductSurface},
    )


def resolve_product_access(
    projection: MembershipEntitlementProjection | None,
) -> ProductAccessSnapshot:
    """Project visibility from server-resolved membership; never accept a client tier."""
    if (
        not isinstance(projection, MembershipEntitlementProjection)
        or projection.code != MembershipResolutionCode.ENTITLED
        or projection.profile is None
    ):
        return _denied(ProductDecisionCode.MEMBERSHIP_UNAVAILABLE)
    try:
        tier = ProductTier(projection.plan_id)
    except (ValueError, TypeError):
        return _denied(ProductDecisionCode.UNKNOWN_PLAN)
    if tier == ProductTier.ADMIN and UserRole.TENANT_ADMIN not in projection.profile.roles:
        return _denied(ProductDecisionCode.ADMIN_ROLE_MISSING, tier)

    dashboard = evaluate_dashboard_access(projection.profile)
    decisions = {}
    for surface in ProductSurface:
        if surface not in _READ_ONLY_SURFACES:
            code = ProductDecisionCode.SURFACE_NOT_READY
        elif not dashboard.allowed:
            code = ProductDecisionCode.DASHBOARD_ENTITLEMENT_MISSING
        else:
            code = ProductDecisionCode.ALLOWED
        decisions[surface] = ProductDecision(code == ProductDecisionCode.ALLOWED, code)
    return ProductAccessSnapshot(tier=tier, decisions=decisions)
