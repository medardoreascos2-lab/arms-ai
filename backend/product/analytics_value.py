"""Repeated-use value metrics for the five premium Product surfaces."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from backend.product.analytics_events import (
    ProductAnalyticsEvent,
    ProductAnalyticsEventName,
    ProductAnalyticsTarget,
)


VALUE_FEATURES = (
    ProductAnalyticsTarget.MEDAR,
    ProductAnalyticsTarget.DAILY_INTELLIGENCE,
    ProductAnalyticsTarget.TRADING_COACH,
    ProductAnalyticsTarget.PORTFOLIO_GUARDIAN,
    ProductAnalyticsTarget.RESEARCH,
)


class FeatureRepeatMetric(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    feature: ProductAnalyticsTarget
    unique_users: int = Field(ge=0)
    repeat_users: int = Field(ge=0)
    repeated_use_rate: float = Field(ge=0, le=1)


def calculate_repeated_use(
    events: tuple[ProductAnalyticsEvent, ...],
) -> tuple[FeatureRepeatMetric, ...]:
    metrics: list[FeatureRepeatMetric] = []
    for feature in VALUE_FEATURES:
        counts: dict[str, int] = {}
        for event in events:
            if event.target != feature:
                continue
            if event.name not in {
                ProductAnalyticsEventName.FEATURE_USED,
                ProductAnalyticsEventName.COACH_OPENED,
                ProductAnalyticsEventName.DAILY_OPENED,
            }:
                continue
            subject = event.pseudonymous_subject_id
            counts[subject] = counts.get(subject, 0) + 1
        repeat_users = sum(count >= 2 for count in counts.values())
        unique_users = len(counts)
        metrics.append(FeatureRepeatMetric(
            feature=feature,
            unique_users=unique_users,
            repeat_users=repeat_users,
            repeated_use_rate=repeat_users / unique_users if unique_users else 0.0,
        ))
    return tuple(metrics)