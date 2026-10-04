"""P110A content-free Product analytics tests."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from backend.product.analytics_events import (
    ProductAnalyticsEvent,
    ProductAnalyticsEventName,
)


NOW = datetime(2026, 10, 4, tzinfo=timezone.utc)


def test_allowed_event_names_match_contract():
    assert {item.value for item in ProductAnalyticsEventName} == {
        "screen_view", "feature_used", "onboarding_step", "alert_ack",
        "coach_opened", "daily_opened", "subscription_state",
    }


def test_event_accepts_only_fixed_content_free_dimensions():
    event = ProductAnalyticsEvent(
        event_id="event-1",
        pseudonymous_subject_id="anon-5f18",
        name="feature_used",
        target="MEDAR",
        occurred_at=NOW,
    )
    assert event.content_included is False
    forbidden = {
        "conversation_text": "private",
        "memory_content": "private",
        "financial_positions": ["NQ"],
        "health_data": "private",
        "private_messages": "private",
    }
    for field, value in forbidden.items():
        with pytest.raises(ValidationError):
            ProductAnalyticsEvent.model_validate({**event.model_dump(), field: value})
    with pytest.raises(ValidationError):
        ProductAnalyticsEvent.model_validate({**event.model_dump(), "content_included": True})


def test_subscription_state_requires_fixed_subscription_dimensions():
    with pytest.raises(ValidationError):
        ProductAnalyticsEvent(
            event_id="event-2",
            pseudonymous_subject_id="anon-5f18",
            name="subscription_state",
            target="MEDAR",
            state="ACTIVE",
            occurred_at=NOW,
        )