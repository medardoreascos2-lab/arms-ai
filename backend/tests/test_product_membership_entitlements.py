"""P108B backend-authoritative Product entitlement tests."""

import pytest

from backend.entitlements import FeatureEntitlement
from backend.product.membership_catalog import ProductPlanId
from backend.product.membership_entitlements import (
    CURRENT_PRODUCT_ENTITLEMENTS,
    FUTURE_PRODUCT_ENTITLEMENTS,
    PRODUCT_PLAN_ENTITLEMENTS,
    entitlements_for_plan,
)


def test_canonical_product_entitlements_match_contract():
    expected = {
        "MEDAR_CONVERSATION", "MEDAR_MEMORY", "DAILY_INTELLIGENCE",
        "TRADING_WORKSPACE", "TRADING_COACH", "SHADOW_MEDAR",
        "PORTFOLIO_GUARDIAN", "RESEARCH", "NOTIFICATIONS",
    }
    assert {item.value for item in CURRENT_PRODUCT_ENTITLEMENTS} == expected
    assert {item.value for item in FUTURE_PRODUCT_ENTITLEMENTS} == {
        "VOICE", "VIDEO",
    }
    assert expected.issubset({item.value for item in FeatureEntitlement})


def test_every_plan_has_backend_mapping_and_future_features_remain_disabled():
    assert set(PRODUCT_PLAN_ENTITLEMENTS) == set(ProductPlanId)
    assert all(
        features.isdisjoint(FUTURE_PRODUCT_ENTITLEMENTS)
        for features in PRODUCT_PLAN_ENTITLEMENTS.values()
    )
    assert entitlements_for_plan(ProductPlanId.PREMIUM) == CURRENT_PRODUCT_ENTITLEMENTS
    assert FeatureEntitlement.TRADING_WORKSPACE not in entitlements_for_plan(
        ProductPlanId.FREE,
    )


def test_noncanonical_plan_cannot_request_entitlements():
    with pytest.raises(ValueError):
        entitlements_for_plan("PREMIUM")
