"""Notification routing intent only; no external transport is wired."""

from dataclasses import dataclass
from enum import Enum

from backend.financial.alert import FinancialAlert


class NotificationChannel(str, Enum):
    TEXT = "TEXT"
    VOICE = "VOICE"
    PUSH = "PUSH"
    TELEGRAM = "TELEGRAM"
    WHATSAPP = "WHATSAPP"
    EMAIL = "EMAIL"


@dataclass(frozen=True)
class NotificationPlan:
    alert_id: str
    channels: tuple[NotificationChannel, ...]
    status: str = "PREVIEW_ONLY"
    send_authority: bool = False

    def __post_init__(self) -> None:
        if not self.alert_id.strip() or not self.channels:
            raise ValueError("notification plan requires alert and channels")
        if any(not isinstance(channel, NotificationChannel) for channel in self.channels):
            raise TypeError("notification channels must be explicit")
        if len(set(self.channels)) != len(self.channels):
            raise ValueError("notification channels must be unique")
        if self.status != "PREVIEW_ONLY" or self.send_authority:
            raise ValueError("notification plan cannot send externally")
        object.__setattr__(self, "channels", tuple(self.channels))


def plan_notification(
    alert: FinancialAlert, channels: tuple[NotificationChannel, ...],
) -> NotificationPlan:
    return NotificationPlan(alert.alert_id, channels)
