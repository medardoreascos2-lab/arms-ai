"""F114A: telemetry records feature counts without private trade content."""

from datetime import date

import pytest

from backend.financial.feature_usage import (
    FeatureUsageEvent, FinancialFeature, aggregate_feature_usage,
)


def test_feature_usage_contains_only_feature_and_day():
    event = FeatureUsageEvent(FinancialFeature.TRADING_COACH, date(2026, 10, 4))
    assert event.local_only
    assert not event.contains_financial_content
    assert not hasattr(event, "asset_id")
    assert not hasattr(event, "portfolio_id")
    with pytest.raises(TypeError):
        FeatureUsageEvent(FinancialFeature.TRADING_COACH, date(2026, 10, 4),
                          trade_result="private")
    summary = aggregate_feature_usage((event,), date(2026, 10, 4))
    assert summary.counts[FinancialFeature.TRADING_COACH] == 1


def test_telemetry_cannot_claim_content_or_external_send():
    with pytest.raises(ValueError, match="cannot contain"):
        FeatureUsageEvent(FinancialFeature.SHADOW_MEDAR, date(2026, 10, 4),
                          contains_financial_content=True)
    with pytest.raises(ValueError, match="cannot contain"):
        FeatureUsageEvent(FinancialFeature.ARBITRAGE_RADAR, date(2026, 10, 4),
                          local_only=False)
