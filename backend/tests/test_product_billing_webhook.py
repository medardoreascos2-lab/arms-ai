"""P109D billing webhook contract tests."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from backend.product.billing_provider import BillingScope
from backend.product.billing_webhook import (
    BillingWebhookEvent,
    BillingWebhookReplayError,
    BillingWebhookReplayProtector,
)


NOW = datetime(2026, 10, 4, tzinfo=timezone.utc)


def event(sequence=1, event_id="evt-1", key="key-1", stream="sub-1"):
    return BillingWebhookEvent(
        event_id=event_id,
        idempotency_key=key,
        stream_id=stream,
        sequence=sequence,
        provider="STRIPE",
        scope=BillingScope(tenant_id="tenant-1", user_id="user-1"),
        billing_status="ACTIVE",
        plan_id="PREMIUM",
        occurred_at=NOW,
        signature_verified=True,
    )


def test_signature_and_non_payment_contract_fail_closed():
    value = event()
    assert value.signature_required is True
    assert value.signature_verified is True
    assert value.applies_payment is False
    assert value.applies_charge is False
    for update in (
        {"signature_verified": False},
        {"signature_required": False},
        {"applies_charge": True},
        {"provider": "NONE"},
    ):
        with pytest.raises(ValidationError):
            BillingWebhookEvent.model_validate({**value.model_dump(), **update})


def test_replay_protector_rejects_duplicate_ids_keys_and_ordering():
    guard = BillingWebhookReplayProtector()
    guard.accept(event())
    with pytest.raises(BillingWebhookReplayError):
        guard.accept(event(sequence=2))
    with pytest.raises(BillingWebhookReplayError):
        guard.accept(event(sequence=2, event_id="evt-2"))
    with pytest.raises(BillingWebhookReplayError):
        guard.accept(event(sequence=1, event_id="evt-3", key="key-3"))
    guard.accept(event(sequence=2, event_id="evt-4", key="key-4"))


def test_ordering_is_isolated_per_stream():
    guard = BillingWebhookReplayProtector()
    guard.accept(event(sequence=10))
    guard.accept(event(sequence=1, event_id="evt-2", key="key-2", stream="sub-2"))