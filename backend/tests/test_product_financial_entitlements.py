"""P104-PRE6 canonical Product financial entitlement taxonomy."""

from backend.entitlements import FeatureEntitlement


def test_current_product_financial_entitlements_are_canonical():
    expected = {
        "FINANCIAL_OVERVIEW",
        "TRADING_WORKSPACE",
        "PORTFOLIO_GUARDIAN",
        "TRADING_COACH",
        "SHADOW_MEDAR",
    }
    assert expected.issubset({item.value for item in FeatureEntitlement})


def test_future_unfinished_financial_features_are_not_exposed():
    unfinished = {
        "CRYPTO_RADAR",
        "ARBITRAGE_RADAR",
        "COMPANY_INTELLIGENCE",
    }
    assert unfinished.isdisjoint({item.value for item in FeatureEntitlement})
