"""P110B aggregate Product metrics tests."""

from datetime import datetime, timedelta, timezone

from backend.product.analytics_events import ProductAnalyticsEvent
from backend.product.analytics_metrics import calculate_product_metrics


NOW = datetime(2026, 10, 31, 12, tzinfo=timezone.utc)


def event(event_id, subject, name, target, days_ago, state=None):
    return ProductAnalyticsEvent(
        event_id=event_id,
        pseudonymous_subject_id=subject,
        name=name,
        target=target,
        state=state,
        occurred_at=NOW - timedelta(days=days_ago),
    )


def test_metrics_cover_activity_retention_adoption_value_conversion_and_churn():
    events = (
        event("1", "a", "screen_view", "HOME", 30),
        event("2", "a", "feature_used", "MEDAR", 29),
        event("3", "a", "feature_used", "MEDAR", 0),
        event("4", "a", "subscription_state", "SUBSCRIPTION", 8, "ACTIVE"),
        event("5", "b", "screen_view", "HOME", 7),
        event("6", "b", "daily_opened", "DAILY_INTELLIGENCE", 0),
        event("7", "b", "subscription_state", "SUBSCRIPTION", 6, "ACTIVE"),
        event("8", "b", "subscription_state", "SUBSCRIPTION", 1, "CANCELLED"),
        event("9", "c", "screen_view", "HOME", 0),
    )
    result = calculate_product_metrics(events, as_of=NOW)
    assert (result.dau, result.wau, result.mau) == (3, 3, 3)
    assert result.d1_retention == 1.0
    assert result.d7_retention == 0.5
    assert result.d30_retention == 1.0
    assert result.feature_adoption["MEDAR"] == 1 / 3
    assert result.feature_adoption["DAILY_INTELLIGENCE"] == 1 / 3
    assert result.median_time_to_value_seconds is not None
    assert result.conversion == 1 / 3
    assert result.churn == 0.5


def test_empty_metrics_are_zero_and_content_free():
    result = calculate_product_metrics((), as_of=NOW)
    assert result.dau == result.wau == result.mau == 0
    assert result.d1_retention == result.d7_retention == result.d30_retention == 0
    assert result.median_time_to_value_seconds is None
    assert result.conversion == result.churn == 0