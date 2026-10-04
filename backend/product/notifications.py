"""Canonical Product notification records with no external delivery authority."""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum


from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator


_IDENTIFIER = r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$"


class NotificationCategory(str, Enum):
    FINANCIAL = "FINANCIAL"
    TRADING_COACH = "TRADING_COACH"
    PORTFOLIO = "PORTFOLIO"
    MEDAR = "MEDAR"
    SYSTEM = "SYSTEM"
    SECURITY = "SECURITY"
    MEMORY = "MEMORY"
    PRODUCT = "PRODUCT"


class NotificationPriority(str, Enum):
    INFO = "INFO"
    WATCH = "WATCH"
    IMPORTANT = "IMPORTANT"
    CRITICAL = "CRITICAL"


class NotificationStatus(str, Enum):
    UNREAD = "UNREAD"
    READ = "READ"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    SNOOZED = "SNOOZED"
    DISMISSED = "DISMISSED"
    EXPIRED = "EXPIRED"


class NotificationChannel(str, Enum):
    IN_APP = "IN_APP"
    VOICE = "VOICE"
    PUSH = "PUSH"
    TELEGRAM = "TELEGRAM"
    WHATSAPP = "WHATSAPP"
    EMAIL = "EMAIL"


class ProductNotification(BaseModel):
    """A tenant/user-scoped inbox record; requested channels are descriptive only."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    notification_id: str = Field(pattern=_IDENTIFIER)
    user_id: str = Field(pattern=_IDENTIFIER)
    tenant_id: str = Field(pattern=_IDENTIFIER)
    category: NotificationCategory
    priority: NotificationPriority
    title: str = Field(min_length=1, max_length=256)
    summary: str = Field(min_length=1, max_length=1024)
    source_type: str = Field(min_length=1, max_length=64, pattern=_IDENTIFIER)
    source_reference: str = Field(min_length=1, max_length=128, pattern=_IDENTIFIER)
    created_at: datetime
    expires_at: datetime | None = None
    status: NotificationStatus = NotificationStatus.UNREAD
    channels_requested: tuple[NotificationChannel, ...] = (NotificationChannel.IN_APP,)
    requires_acknowledgement: bool = False
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("created_at", "expires_at")
    @classmethod
    def timestamps_are_utc(cls, value: datetime | None) -> datetime | None:
        if value is not None and (
            value.tzinfo is None or value.utcoffset() != timedelta(0)
        ):
            raise ValueError("notification timestamps must be UTC")
        return value

    @field_validator("channels_requested")
    @classmethod
    def channels_are_unique(
        cls, value: tuple[NotificationChannel, ...]
    ) -> tuple[NotificationChannel, ...]:
        if len(value) != len(set(value)):
            raise ValueError("requested channels must be unique")
        return value

    @model_validator(mode="after")
    def temporal_and_status_rules(self) -> ProductNotification:
        if self.expires_at is not None and self.expires_at <= self.created_at:
            raise ValueError("notification expiry must follow creation")
        if self.requires_acknowledgement and self.status == NotificationStatus.DISMISSED:
            raise ValueError("required acknowledgement cannot start dismissed")
        return self
