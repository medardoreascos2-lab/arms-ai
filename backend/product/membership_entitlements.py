"""Backend-authoritative Product plan entitlement mappings."""

from __future__ import annotations

from types import MappingProxyType
from typing import Mapping

from backend.entitlements import FeatureEntitlement
from backend.product.membership_catalog import ProductPlanId


CURRENT_PRODUCT_ENTITLEMENTS = frozenset({
    FeatureEntitlement.MEDAR_CONVERSATION,
    FeatureEntitlement.MEDAR_MEMORY,
    FeatureEntitlement.DAILY_INTELLIGENCE,
    FeatureEntitlement.TRADING_WORKSPACE,
    FeatureEntitlement.TRADING_COACH,
    FeatureEntitlement.SHADOW_MEDAR,
    FeatureEntitlement.PORTFOLIO_GUARDIAN,
    FeatureEntitlement.RESEARCH,
    FeatureEntitlement.NOTIFICATIONS,
})
FUTURE_PRODUCT_ENTITLEMENTS = frozenset({
    FeatureEntitlement.VOICE,
    FeatureEntitlement.VIDEO,
})

PRODUCT_PLAN_ENTITLEMENTS: Mapping[
    ProductPlanId, frozenset[FeatureEntitlement]
] = MappingProxyType({
    ProductPlanId.FREE: frozenset({
        FeatureEntitlement.DAILY_INTELLIGENCE,
        FeatureEntitlement.NOTIFICATIONS,
    }),
    ProductPlanId.PRO: frozenset({
        FeatureEntitlement.MEDAR_CONVERSATION,
        FeatureEntitlement.MEDAR_MEMORY,
        FeatureEntitlement.DAILY_INTELLIGENCE,
        FeatureEntitlement.RESEARCH,
        FeatureEntitlement.NOTIFICATIONS,
    }),
    ProductPlanId.PREMIUM: CURRENT_PRODUCT_ENTITLEMENTS,
    ProductPlanId.ELITE: CURRENT_PRODUCT_ENTITLEMENTS,
})


def entitlements_for_plan(
    plan_id: ProductPlanId,
) -> frozenset[FeatureEntitlement]:
    if not isinstance(plan_id, ProductPlanId):
        raise ValueError("canonical Product plan required")
    return PRODUCT_PLAN_ENTITLEMENTS[plan_id]
