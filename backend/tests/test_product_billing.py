"""P109A provider-neutral billing domain tests."""

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from backend.product.billing import (
    BillingCustomer,
    BillingStatus,
    InvoiceReference,
    Plan,
    Subscription,
    Trial,
)


NOW = datetime(2026, 10, 4, 12, tzinfo=timezone.utc)


def customer():
    return BillingCustomer(
        billing_customer_id="synthetic-billing-customer-1",
        tenant_id="synthetic-tenant-1",
        user_id="synthetic-user-1",
        provider="LOCAL_SYNTHETIC",
    )


def subscription(**overrides):
    body = {
        "subscription_id": "synthetic-subscription-1",
        "billing_customer_id": customer().billing_customer_id,
        "tenant_id": customer().tenant_id,
        "user_id": customer().user_id,
        "plan": Plan(plan_id="PREMIUM", catalog_version="1"),
        "status": BillingStatus.TRIAL,
        "trial": Trial(starts_at=NOW, ends_at=NOW + timedelta(days=14)),
        "invoice_references": (
            InvoiceReference(
                invoice_reference="synthetic-invoice-1",
                provider="LOCAL_SYNTHETIC",
                amount="0.00",
                currency="USD",
            ),
        ),
        "version": 1,
    }
    body.update(overrides)
    return Subscription(**body)


def test_billing_statuses_match_contract_and_authority_is_false():
    assert {item.value for item in BillingStatus} == {
        "TRIAL", "ACTIVE", "PAST_DUE", "CANCELLED", "EXPIRED", "INCOMPLETE",
    }
    value = subscription()
    assert customer().payment_method_attached is False
    assert customer().charge_authorized is False
    assert value.payment_provider_connected is False
    assert value.charge_authorized is False
    assert value.plan.price_final is False
    assert value.plan.purchasable is False
    assert value.invoice_references[0].charged is False


def test_billing_models_cannot_enable_payment_or_charge_authority():
    with pytest.raises(ValidationError):
        BillingCustomer.model_validate({
            **customer().model_dump(), "charge_authorized": True,
        })
    with pytest.raises(ValidationError):
        Subscription.model_validate({
            **subscription().model_dump(), "payment_provider_connected": True,
        })
    with pytest.raises(ValidationError):
        InvoiceReference(
            invoice_reference="synthetic-invoice-2",
            provider="LOCAL_SYNTHETIC",
            amount="25.00",
            currency="USD",
            charged=True,
        )


def test_trial_status_requires_valid_utc_trial_window():
    with pytest.raises(ValidationError):
        subscription(trial=None)
    with pytest.raises(ValidationError):
        Trial(starts_at=NOW, ends_at=NOW)
    with pytest.raises(ValidationError):
        Trial(
            starts_at=datetime(2026, 10, 4, 12),
            ends_at=NOW + timedelta(days=1),
        )
