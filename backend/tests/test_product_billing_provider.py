"""P109B provider-neutral billing contract tests."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from backend.product.billing_provider import (
    BillingLifecycleAction,
    BillingLifecycleCommand,
    BillingProvider,
    BillingProviderKind,
    BillingProviderStatus,
    BillingScope,
)


def test_provider_contract_declares_future_kinds_but_stays_disconnected():
    assert {item.value for item in BillingProviderKind} == {"NONE", "STRIPE", "OTHER"}
    for provider in BillingProviderKind:
        status = BillingProviderStatus(provider=provider)
        assert status.connected is False
        assert status.supports_charges is False
        assert status.external_webhooks_enabled is False


def test_lifecycle_command_cannot_authorize_a_charge():
    command = BillingLifecycleCommand(
        action=BillingLifecycleAction.SUBSCRIBE,
        scope=BillingScope(tenant_id="tenant-1", user_id="user-1"),
        target_plan_id="PREMIUM",
        idempotency_key="subscribe-1",
        requested_at=datetime(2026, 10, 4, tzinfo=timezone.utc),
    )
    assert command.charge_authorized is False
    with pytest.raises(ValidationError):
        BillingLifecycleCommand.model_validate({
            **command.model_dump(), "charge_authorized": True,
        })


def test_provider_protocol_has_no_payment_or_checkout_operations():
    methods = set(BillingProvider.__protocol_attrs__)
    assert {"status", "get_customer", "get_subscription", "apply_lifecycle"} <= methods
    assert methods.isdisjoint({"charge", "pay", "checkout", "attach_payment_method"})