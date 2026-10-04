"""Scoped Product profile and presentation preferences."""

from __future__ import annotations

from enum import Enum
import sqlite3
from typing import Protocol
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.product.notification_store import NotificationScope
from backend.product.notifications import NotificationChannel


_SAFE_ID = r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$"


class ProductTheme(str, Enum):
    SYSTEM = "SYSTEM"
    LIGHT = "LIGHT"
    DARK = "DARK"
    HIGH_CONTRAST = "HIGH_CONTRAST"


class ProductResponseProfile(str, Enum):
    CONCISE = "CONCISE"
    BALANCED = "BALANCED"
    DETAILED = "DETAILED"


class AccessibilityPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    reduced_motion: bool = False
    high_contrast: bool = False
    text_scale: float = Field(default=1.0, ge=0.8, le=2.0)
    screen_reader_optimized: bool = False


class ProductProfilePreferences(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    tenant_id: str = Field(pattern=_SAFE_ID)
    user_id: str = Field(pattern=_SAFE_ID)
    display_name: str = Field(min_length=1, max_length=80)
    language: str = Field(pattern=r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$")
    timezone: str = Field(min_length=1, max_length=64)
    theme: ProductTheme = ProductTheme.SYSTEM
    accessibility: AccessibilityPreferences = AccessibilityPreferences()
    response_profile: ProductResponseProfile = ProductResponseProfile.BALANCED
    notification_defaults: tuple[NotificationChannel, ...] = (
        NotificationChannel.IN_APP,
    )
    version: int = Field(ge=1)

    @field_validator("timezone")
    @classmethod
    def timezone_must_be_known(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise ValueError("timezone must be an IANA timezone") from error
        return value

    @field_validator("notification_defaults")
    @classmethod
    def channels_must_be_unique(
        cls, value: tuple[NotificationChannel, ...],
    ) -> tuple[NotificationChannel, ...]:
        if len(value) != len(set(value)):
            raise ValueError("notification defaults must be unique")
        return value


class ProductProfileStore(Protocol):
    def get(
        self, scope: NotificationScope,
    ) -> ProductProfilePreferences | None: ...
    def save(
        self, scope: NotificationScope, profile: ProductProfilePreferences,
        expected_version: int | None,
    ) -> ProductProfilePreferences: ...


class LocalSqliteProductProfileStore:
    def __init__(self, database_path: str, *, environment: str) -> None:
        if environment not in {"LOCAL_TEST_ONLY", "DEVELOPMENT"}:
            raise ValueError("local profile store requires test/development environment")
        self._connection = sqlite3.connect(database_path)
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS product_profile_preferences (
                tenant_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                version INTEGER NOT NULL,
                profile_json TEXT NOT NULL,
                PRIMARY KEY (tenant_id, user_id)
            )
            """
        )
        self._connection.commit()

    def close(self) -> None:
        self._connection.close()

    @staticmethod
    def _require_scope(
        scope: NotificationScope, profile: ProductProfilePreferences,
    ) -> None:
        if profile.tenant_id != scope.tenant_id or profile.user_id != scope.user_id:
            raise PermissionError("profile is outside tenant/user scope")

    def get(
        self, scope: NotificationScope,
    ) -> ProductProfilePreferences | None:
        row = self._connection.execute(
            """
            SELECT profile_json FROM product_profile_preferences
            WHERE tenant_id = ? AND user_id = ?
            """,
            (scope.tenant_id, scope.user_id),
        ).fetchone()
        return (
            None if row is None
            else ProductProfilePreferences.model_validate_json(row[0])
        )

    def save(
        self, scope: NotificationScope, profile: ProductProfilePreferences,
        expected_version: int | None,
    ) -> ProductProfilePreferences:
        self._require_scope(scope, profile)
        current = self.get(scope)
        if current is None:
            if expected_version is not None or profile.version != 1:
                raise RuntimeError("new profile must start at version 1")
        elif expected_version != current.version or profile.version != current.version + 1:
            raise RuntimeError("stale or invalid profile version")
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO product_profile_preferences
                    (tenant_id, user_id, version, profile_json)
                VALUES (?, ?, ?, ?)
                ON CONFLICT (tenant_id, user_id)
                DO UPDATE SET version = excluded.version, profile_json = excluded.profile_json
                """,
                (
                    scope.tenant_id, scope.user_id,
                    profile.version, profile.model_dump_json(),
                ),
            )
        return profile
