"""Durable, scoped Product onboarding state for local test/development."""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
import sqlite3
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.product.notification_store import NotificationScope


_SAFE_ID = r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$"


class OnboardingStatus(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    SKIPPED_OPTIONAL = "SKIPPED_OPTIONAL"
    BLOCKED = "BLOCKED"


class OnboardingStep(str, Enum):
    WELCOME = "WELCOME"
    GOALS = "GOALS"
    FINANCIAL_EXPECTATIONS = "FINANCIAL_EXPECTATIONS"
    MEMORY_CONSENT = "MEMORY_CONSENT"
    NOTIFICATION_PREFS = "NOTIFICATION_PREFS"
    PRIVACY = "PRIVACY"
    DONE = "DONE"


class OnboardingGoal(str, Enum):
    TRADING = "TRADING"
    INVESTING = "INVESTING"
    PORTFOLIO = "PORTFOLIO"
    BUSINESS = "BUSINESS"
    LEARNING = "LEARNING"
    PERSONAL_ASSISTANT = "PERSONAL_ASSISTANT"


class OnboardingMemoryConsent(str, Enum):
    SESSION_ONLY = "SESSION_ONLY"
    ALLOW_LOW_SENSITIVITY = "ALLOW_LOW_SENSITIVITY"
    REVIEW_BEFORE_SAVE = "REVIEW_BEFORE_SAVE"
    DO_NOT_SAVE = "DO_NOT_SAVE"


class ProductOnboardingState(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    onboarding_id: str = Field(pattern=_SAFE_ID)
    tenant_id: str = Field(pattern=_SAFE_ID)
    user_id: str = Field(pattern=_SAFE_ID)
    status: OnboardingStatus
    current_step: OnboardingStep
    completed_steps: tuple[OnboardingStep, ...] = ()
    selected_goals: tuple[OnboardingGoal, ...] = ()
    goals_confirmed: bool = False
    memory_consent: OnboardingMemoryConsent | None = None
    memory_consent_confirmed: bool = False
    version: int = Field(ge=1)
    created_at: datetime
    updated_at: datetime
    blocked_reason: str | None = Field(default=None, max_length=512)

    @field_validator("created_at", "updated_at")
    @classmethod
    def timestamps_are_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise ValueError("onboarding timestamps must be UTC")
        return value

    @field_validator("completed_steps")
    @classmethod
    def completed_steps_are_unique(
        cls, value: tuple[OnboardingStep, ...],
    ) -> tuple[OnboardingStep, ...]:
        if len(value) != len(set(value)):
            raise ValueError("completed onboarding steps must be unique")
        return value

    @field_validator("selected_goals")
    @classmethod
    def selected_goals_are_unique(
        cls, value: tuple[OnboardingGoal, ...],
    ) -> tuple[OnboardingGoal, ...]:
        if len(value) != len(set(value)):
            raise ValueError("selected onboarding goals must be unique")
        return value

    @model_validator(mode="after")
    def state_is_consistent(self) -> ProductOnboardingState:
        if self.memory_consent_confirmed != (self.memory_consent is not None):
            raise ValueError("memory consent confirmation must match an explicit choice")
        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot precede created_at")
        if self.status == OnboardingStatus.NOT_STARTED and self.completed_steps:
            raise ValueError("not-started onboarding cannot have completed steps")
        if self.status == OnboardingStatus.COMPLETED and (
            self.current_step != OnboardingStep.DONE
            or OnboardingStep.DONE not in self.completed_steps
        ):
            raise ValueError("completed onboarding must finish DONE")
        if self.status == OnboardingStatus.BLOCKED and not self.blocked_reason:
            raise ValueError("blocked onboarding requires a reason")
        if self.status != OnboardingStatus.BLOCKED and self.blocked_reason is not None:
            raise ValueError("blocked reason is only valid for blocked onboarding")
        return self


class ProductOnboardingStore(Protocol):
    def get(
        self, scope: NotificationScope,
    ) -> ProductOnboardingState | None: ...
    def save(
        self, scope: NotificationScope, state: ProductOnboardingState,
        expected_version: int | None,
    ) -> ProductOnboardingState: ...


class LocalSqliteOnboardingStore:
    """Local persistence only; no production auth or external service dependency."""

    def __init__(self, database_path: str, *, environment: str) -> None:
        if environment not in {"LOCAL_TEST_ONLY", "DEVELOPMENT"}:
            raise ValueError("local onboarding store requires test/development environment")
        if not database_path:
            raise ValueError("database_path is required")
        self._connection = sqlite3.connect(database_path)
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS product_onboarding (
                tenant_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                version INTEGER NOT NULL,
                state_json TEXT NOT NULL,
                PRIMARY KEY (tenant_id, user_id)
            )
            """
        )
        self._connection.commit()

    def close(self) -> None:
        self._connection.close()

    @staticmethod
    def _require_scope(
        scope: NotificationScope, state: ProductOnboardingState,
    ) -> None:
        if scope.tenant_id != state.tenant_id or scope.user_id != state.user_id:
            raise PermissionError("onboarding state is outside tenant/user scope")

    def get(
        self, scope: NotificationScope,
    ) -> ProductOnboardingState | None:
        row = self._connection.execute(
            """
            SELECT state_json FROM product_onboarding
            WHERE tenant_id = ? AND user_id = ?
            """,
            (scope.tenant_id, scope.user_id),
        ).fetchone()
        return (
            None if row is None
            else ProductOnboardingState.model_validate_json(row[0])
        )

    def save(
        self, scope: NotificationScope, state: ProductOnboardingState,
        expected_version: int | None,
    ) -> ProductOnboardingState:
        self._require_scope(scope, state)
        current = self.get(scope)
        if current is None:
            if expected_version is not None or state.version != 1:
                raise RuntimeError("new onboarding state must start at version 1")
        else:
            if expected_version != current.version:
                raise RuntimeError("stale onboarding state")
            if state.onboarding_id != current.onboarding_id:
                raise ValueError("onboarding identity cannot change")
            if state.created_at != current.created_at:
                raise ValueError("onboarding creation time cannot change")
            if state.version != current.version + 1:
                raise ValueError("onboarding version must increment by one")
            if state.updated_at < current.updated_at:
                raise ValueError("onboarding update time cannot move backward")
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO product_onboarding
                    (tenant_id, user_id, version, state_json)
                VALUES (?, ?, ?, ?)
                ON CONFLICT (tenant_id, user_id)
                DO UPDATE SET
                    version = excluded.version,
                    state_json = excluded.state_json
                """,
                (
                    scope.tenant_id, scope.user_id,
                    state.version, state.model_dump_json(),
                ),
            )
        return state
