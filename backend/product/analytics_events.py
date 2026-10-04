"""Content-free Product analytics events with fixed categorical dimensions."""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


_SAFE_ID = r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$"


class ProductAnalyticsEventName(str, Enum):
    SCREEN_VIEW = "screen_view"
    FEATURE_USED = "feature_used"
    ONBOARDING_STEP = "onboarding_step"
    ALERT_ACK = "alert_ack"
    COACH_OPENED = "coach_opened"
    DAILY_OPENED = "daily_opened"
    SUBSCRIPTION_STATE = "subscription_state"


class ProductAnalyticsTarget(str, Enum):
    HOME = "HOME"
    MEDAR = "MEDAR"
    DAILY_INTELLIGENCE = "DAILY_INTELLIGENCE"
    TRADING_WORKSPACE = "TRADING_WORKSPACE"
    TRADING_COACH = "TRADING_COACH"
    PORTFOLIO_GUARDIAN = "PORTFOLIO_GUARDIAN"
    RESEARCH = "RESEARCH"
    ONBOARDING = "ONBOARDING"
    NOTIFICATIONS = "NOTIFICATIONS"
    SUBSCRIPTION = "SUBSCRIPTION"


class ProductAnalyticsState(str, Enum):
    STARTED = "STARTED"
    COMPLETED = "COMPLETED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    TRIAL = "TRIAL"
    ACTIVE = "ACTIVE"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class ProductAnalyticsEvent(BaseModel):
    """No arbitrary properties are accepted, preventing private content capture."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: str = Field(pattern=_SAFE_ID)
    pseudonymous_subject_id: str = Field(pattern=_SAFE_ID)
    name: ProductAnalyticsEventName
    target: ProductAnalyticsTarget
    state: ProductAnalyticsState | None = None
    occurred_at: datetime
    content_included: bool = Field(default=False, frozen=True)

    @field_validator("occurred_at")
    @classmethod
    def occurred_at_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise ValueError("occurred_at must be UTC")
        return value

    @model_validator(mode="after")
    def dimensions_match_event(self) -> ProductAnalyticsEvent:
        if self.content_included:
            raise ValueError("analytics events cannot contain content")
        if self.name == ProductAnalyticsEventName.SUBSCRIPTION_STATE:
            if self.target != ProductAnalyticsTarget.SUBSCRIPTION or self.state not in {
                ProductAnalyticsState.TRIAL,
                ProductAnalyticsState.ACTIVE,
                ProductAnalyticsState.CANCELLED,
                ProductAnalyticsState.EXPIRED,
            }:
                raise ValueError("subscription events require a subscription state")
        return self