"""Deterministic aggregate metrics computed only from content-free events."""

from __future__ import annotations

from datetime import datetime, timedelta
from statistics import median

from pydantic import BaseModel, ConfigDict, Field

from backend.product.analytics_events import (
    ProductAnalyticsEvent,
    ProductAnalyticsEventName,
    ProductAnalyticsState,
    ProductAnalyticsTarget,
)


_FEATURE_TARGETS = {
    ProductAnalyticsTarget.MEDAR,
    ProductAnalyticsTarget.DAILY_INTELLIGENCE,
    ProductAnalyticsTarget.TRADING_COACH,
    ProductAnalyticsTarget.PORTFOLIO_GUARDIAN,
    ProductAnalyticsTarget.RESEARCH,
}
_VALUE_EVENTS = {
    ProductAnalyticsEventName.FEATURE_USED,
    ProductAnalyticsEventName.COACH_OPENED,
    ProductAnalyticsEventName.DAILY_OPENED,
    ProductAnalyticsEventName.ALERT_ACK,
}


class ProductMetricSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    dau: int = Field(ge=0)
    wau: int = Field(ge=0)
    mau: int = Field(ge=0)
    d1_retention: float = Field(ge=0, le=1)
    d7_retention: float = Field(ge=0, le=1)
    d30_retention: float = Field(ge=0, le=1)
    feature_adoption: dict[ProductAnalyticsTarget, float]
    median_time_to_value_seconds: float | None = Field(default=None, ge=0)
    conversion: float = Field(ge=0, le=1)
    churn: float = Field(ge=0, le=1)


def calculate_product_metrics(
    events: tuple[ProductAnalyticsEvent, ...],
    *,
    as_of: datetime,
) -> ProductMetricSnapshot:
    if as_of.tzinfo is None or as_of.utcoffset() != timedelta(0):
        raise ValueError("as_of must be UTC")
    eligible = tuple(event for event in events if event.occurred_at <= as_of)
    today = as_of.date()

    def active(day_count: int) -> set[str]:
        return {
            event.pseudonymous_subject_id
            for event in eligible
            if 0 <= (today - event.occurred_at.date()).days < day_count
        }

    mau_subjects = active(30)
    adoption = {
        target: _ratio(
            len({
                event.pseudonymous_subject_id
                for event in eligible
                if event.pseudonymous_subject_id in mau_subjects
                and event.target == target
                and event.name in _VALUE_EVENTS
            }),
            len(mau_subjects),
        )
        for target in sorted(_FEATURE_TARGETS, key=lambda item: item.value)
    }

    first_seen: dict[str, datetime] = {}
    first_value: dict[str, datetime] = {}
    for event in sorted(eligible, key=lambda item: item.occurred_at):
        subject = event.pseudonymous_subject_id
        first_seen.setdefault(subject, event.occurred_at)
        if event.name in _VALUE_EVENTS:
            first_value.setdefault(subject, event.occurred_at)
    value_times = [
        (first_value[subject] - timestamp).total_seconds()
        for subject, timestamp in first_seen.items()
        if subject in first_value
    ]

    latest_subscription: dict[str, ProductAnalyticsState] = {}
    ever_active: set[str] = set()
    for event in sorted(eligible, key=lambda item: item.occurred_at):
        if event.name == ProductAnalyticsEventName.SUBSCRIPTION_STATE and event.state is not None:
            latest_subscription[event.pseudonymous_subject_id] = event.state
            if event.state == ProductAnalyticsState.ACTIVE:
                ever_active.add(event.pseudonymous_subject_id)
    converted = {
        subject for subject, state in latest_subscription.items()
        if state == ProductAnalyticsState.ACTIVE
    }
    churned = {
        subject for subject, state in latest_subscription.items()
        if subject in ever_active and state in {
            ProductAnalyticsState.CANCELLED, ProductAnalyticsState.EXPIRED,
        }
    }

    all_subjects = set(first_seen)
    return ProductMetricSnapshot(
        dau=len(active(1)),
        wau=len(active(7)),
        mau=len(mau_subjects),
        d1_retention=_retention(eligible, first_seen, 1, today),
        d7_retention=_retention(eligible, first_seen, 7, today),
        d30_retention=_retention(eligible, first_seen, 30, today),
        feature_adoption=adoption,
        median_time_to_value_seconds=median(value_times) if value_times else None,
        conversion=_ratio(len(converted), len(all_subjects)),
        churn=_ratio(len(churned), len(ever_active)),
    )


def _retention(
    events: tuple[ProductAnalyticsEvent, ...],
    first_seen: dict[str, datetime],
    days: int,
    today,
) -> float:
    cohort = {
        subject for subject, timestamp in first_seen.items()
        if (today - timestamp.date()).days >= days
    }
    returned = {
        event.pseudonymous_subject_id
        for event in events
        if event.pseudonymous_subject_id in cohort
        and (event.occurred_at.date() - first_seen[event.pseudonymous_subject_id].date()).days == days
    }
    return _ratio(len(returned), len(cohort))


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0