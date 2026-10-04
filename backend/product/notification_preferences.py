"""Tenant-scoped Product notification preferences; no delivery transport."""

from __future__ import annotations

from datetime import time
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.product.notification_store import NotificationScope
from backend.product.notifications import (
    NotificationCategory,
    NotificationChannel,
    NotificationPriority,
)


_PRIORITY_RANK = {
    NotificationPriority.INFO: 0,
    NotificationPriority.WATCH: 1,
    NotificationPriority.IMPORTANT: 2,
    NotificationPriority.CRITICAL: 3,
}


class QuietHours(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    start: time
    end: time

    @model_validator(mode="after")
    def nonzero_window(self) -> QuietHours:
        if self.start == self.end:
            raise ValueError("quiet hours cannot cover an ambiguous full day")
        return self

    def contains(self, value: time) -> bool:
        if self.start < self.end:
            return self.start <= value < self.end
        return value >= self.start or value < self.end


class CategoryNotificationPreference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    category: NotificationCategory
    enabled: bool = True
    priority_threshold: NotificationPriority = NotificationPriority.INFO
    quiet_hours: QuietHours | None = None
    critical_override: bool = True
    channels: tuple[NotificationChannel, ...] = (NotificationChannel.IN_APP,)

    @field_validator("channels")
    @classmethod
    def require_unique_channels(
        cls, value: tuple[NotificationChannel, ...],
    ) -> tuple[NotificationChannel, ...]:
        if not value or len(value) != len(set(value)):
            raise ValueError("at least one unique supported channel is required")
        return value


class NotificationPreferenceProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    tenant_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
    user_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
    preferences: tuple[CategoryNotificationPreference, ...]

    @field_validator("preferences")
    @classmethod
    def categories_are_unique(
        cls, value: tuple[CategoryNotificationPreference, ...],
    ) -> tuple[CategoryNotificationPreference, ...]:
        categories = [item.category for item in value]
        if len(categories) != len(set(categories)):
            raise ValueError("notification category preferences must be unique")
        return value

    def allows(
        self, category: NotificationCategory, priority: NotificationPriority,
        channel: NotificationChannel, local_time: time,
    ) -> bool:
        preference = next(
            (item for item in self.preferences if item.category == category),
            None,
        )
        if preference is None or not preference.enabled or channel not in preference.channels:
            return False
        if _PRIORITY_RANK[priority] < _PRIORITY_RANK[preference.priority_threshold]:
            return False
        quiet = preference.quiet_hours
        if quiet is not None and quiet.contains(local_time):
            return priority == NotificationPriority.CRITICAL and preference.critical_override
        return True


class ProductNotificationPreferenceStore(Protocol):
    def put(
        self, scope: NotificationScope, profile: NotificationPreferenceProfile,
    ) -> NotificationPreferenceProfile: ...
    def get(
        self, scope: NotificationScope,
    ) -> NotificationPreferenceProfile | None: ...


class LocalSqliteNotificationPreferenceStore:
    """Local test/development preference persistence with no delivery capability."""

    def __init__(self, connection, *, environment: str) -> None:
        if environment not in {"LOCAL_TEST_ONLY", "DEVELOPMENT"}:
            raise ValueError("local preference store requires test/development environment")
        self._connection = connection
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS product_notification_preferences (
                tenant_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                profile_json TEXT NOT NULL,
                PRIMARY KEY (tenant_id, user_id)
            )
            """
        )
        self._connection.commit()

    @staticmethod
    def _require_scope(
        scope: NotificationScope, profile: NotificationPreferenceProfile,
    ) -> None:
        if profile.tenant_id != scope.tenant_id or profile.user_id != scope.user_id:
            raise PermissionError("preference profile is outside tenant/user scope")

    def put(
        self, scope: NotificationScope, profile: NotificationPreferenceProfile,
    ) -> NotificationPreferenceProfile:
        self._require_scope(scope, profile)
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO product_notification_preferences
                    (tenant_id, user_id, profile_json)
                VALUES (?, ?, ?)
                ON CONFLICT (tenant_id, user_id)
                DO UPDATE SET profile_json = excluded.profile_json
                """,
                (scope.tenant_id, scope.user_id, profile.model_dump_json()),
            )
        return profile

    def get(
        self, scope: NotificationScope,
    ) -> NotificationPreferenceProfile | None:
        row = self._connection.execute(
            """
            SELECT profile_json FROM product_notification_preferences
            WHERE tenant_id = ? AND user_id = ?
            """,
            (scope.tenant_id, scope.user_id),
        ).fetchone()
        return (
            None if row is None
            else NotificationPreferenceProfile.model_validate_json(row[0])
        )
