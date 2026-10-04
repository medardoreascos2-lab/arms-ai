"""Validated billing webhook contract with ordering and replay protection."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.product.billing import BillingStatus
from backend.product.billing_provider import BillingProviderKind, BillingScope
from backend.product.membership_catalog import ProductPlanId


_SAFE_ID = r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$"


class BillingWebhookEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: str = Field(pattern=_SAFE_ID)
    idempotency_key: str = Field(pattern=_SAFE_ID)
    stream_id: str = Field(pattern=_SAFE_ID)
    sequence: int = Field(ge=1)
    provider: Literal[BillingProviderKind.STRIPE, BillingProviderKind.OTHER]
    scope: BillingScope
    billing_status: BillingStatus
    plan_id: ProductPlanId | None = None
    occurred_at: datetime
    signature_required: Literal[True] = True
    signature_verified: Literal[True]
    applies_payment: Literal[False] = False
    applies_charge: Literal[False] = False

    @field_validator("occurred_at")
    @classmethod
    def occurred_at_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise ValueError("occurred_at must be UTC")
        return value


class BillingWebhookReplayError(ValueError):
    pass


class BillingWebhookReplayProtector:
    """In-memory validation seam. It does not expose or handle an HTTP endpoint."""

    def __init__(self) -> None:
        self._event_ids: set[str] = set()
        self._idempotency_keys: set[str] = set()
        self._last_sequence_by_stream: dict[str, int] = {}

    def accept(self, event: BillingWebhookEvent) -> None:
        if event.event_id in self._event_ids:
            raise BillingWebhookReplayError("duplicate event_id")
        if event.idempotency_key in self._idempotency_keys:
            raise BillingWebhookReplayError("duplicate idempotency_key")
        last_sequence = self._last_sequence_by_stream.get(event.stream_id, 0)
        if event.sequence <= last_sequence:
            raise BillingWebhookReplayError("event is duplicate or out of order")

        self._event_ids.add(event.event_id)
        self._idempotency_keys.add(event.idempotency_key)
        self._last_sequence_by_stream[event.stream_id] = event.sequence