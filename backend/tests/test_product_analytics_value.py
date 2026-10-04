"""P110C repeated-use value metric tests."""

from datetime import datetime, timedelta, timezone

from backend.product.analytics_events import ProductAnalyticsEvent
from backend.product.analytics_value import VALUE_FEATURES, calculate_repeated_use


NOW = datetime(2026, 10, 4, tzinfo=timezone.utc)


def used(event_id, subject, target, minutes):
    return ProductAnalyticsEvent(
        event_id=event_id,
        pseudonymous_subject_id=subject,
        name="feature_used",
        target=target,
        occurred_at=NOW + timedelta(minutes=minutes),
    )


def test_value_features_match_contract_and_track_repeated_use():
    assert {item.value for item in VALUE_FEATURES} == {
        "MEDAR", "DAILY_INTELLIGENCE", "TRADING_COACH",
        "PORTFOLIO_GUARDIAN", "RESEARCH",
    }
    events = (
        used("1", "a", "MEDAR", 0),
        used("2", "a", "MEDAR", 1),
        used("3", "b", "MEDAR", 2),
        used("4", "c", "RESEARCH", 3),
        ProductAnalyticsEvent(
            event_id="5", pseudonymous_subject_id="a", name="screen_view",
            target="MEDAR", occurred_at=NOW + timedelta(minutes=4),
        ),
    )
    metrics = {item.feature: item for item in calculate_repeated_use(events)}
    assert metrics["MEDAR"].unique_users == 2
    assert metrics["MEDAR"].repeat_users == 1
    assert metrics["MEDAR"].repeated_use_rate == 0.5
    assert metrics["RESEARCH"].repeated_use_rate == 0
    assert metrics["TRADING_COACH"].unique_users == 0