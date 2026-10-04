"""Closed-beta feedback metadata with private content disabled by default."""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
import sqlite3
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.product.analytics_events import ProductAnalyticsTarget


_SAFE_ID = r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$"


class BetaFeedbackType(str, Enum):
    BUG = "BUG"
    FEATURE_REQUEST = "FEATURE_REQUEST"
    CONFUSING_UX = "CONFUSING_UX"
    WRONG_ANSWER = "WRONG_ANSWER"
    USEFUL_ANSWER = "USEFUL_ANSWER"
    BILLING_FEEDBACK = "BILLING_FEEDBACK"


class BetaFeedback(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    feedback_id: str = Field(pattern=_SAFE_ID)
    tenant_id: str = Field(pattern=_SAFE_ID)
    user_id: str = Field(pattern=_SAFE_ID)
    feedback_type: BetaFeedbackType
    surface: ProductAnalyticsTarget
    error_reference: str | None = Field(default=None, pattern=_SAFE_ID)
    occurred_at: datetime
    private_content_included: Literal[False] = False
    comment: None = None

    @field_validator("occurred_at")
    @classmethod
    def occurred_at_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise ValueError("feedback timestamp must be UTC")
        return value


class LocalSqliteBetaFeedbackStore:
    def __init__(self, path: str = ":memory:") -> None:
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS beta_feedback (
                feedback_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                payload TEXT NOT NULL
            )
        """)

    def append(self, feedback: BetaFeedback) -> None:
        self._db.execute(
            "INSERT INTO beta_feedback VALUES (?, ?, ?, ?)",
            (feedback.feedback_id, feedback.tenant_id, feedback.user_id, feedback.model_dump_json()),
        )
        self._db.commit()

    def list_for_user(self, tenant_id: str, user_id: str) -> tuple[BetaFeedback, ...]:
        rows = self._db.execute(
            "SELECT payload FROM beta_feedback WHERE tenant_id = ? AND user_id = ? ORDER BY feedback_id",
            (tenant_id, user_id),
        ).fetchall()
        return tuple(BetaFeedback.model_validate_json(row[0]) for row in rows)