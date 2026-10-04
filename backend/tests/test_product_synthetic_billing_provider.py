"""P109C synthetic billing lifecycle tests."""

from datetime import datetime, timedelta, timezone

import pytest

from backend.product.billing import BillingStatus
from backend.product.billing_provider import (
    BillingLifecycleAction,
    BillingLifecycleCommand,
    BillingScope,
)
from backend.product.synthetic_billing_provider import (
    LocalSyntheticBillingLifecycle,
    SyntheticBillingLifecycleError,
)


NOW = datetime(2026, 10, 4, 12, tzinfo=timezone.utc)
SCOPE = BillingScope(tenant_id="tenant-1", user_id="user-1")


def command(action, key, plan=None, when=NOW):
    return BillingLifecycleCommand(
        action=action,
        scope=SCOPE,
        target_plan_id=plan,
        idempotency_key=key,
        requested_at=when,
    )


def assert_no_payment_authority(provider, subscription):
    assert provider.status().connected is False
    assert provider.status().supports_charges is False
    assert subscription.payment_provider_connected is False
    assert subscription.charge_authorized is False
    assert subscription.plan.purchasable is False
    assert subscription.invoice_references == ()


def test_trial_upgrade_downgrade_cancel_expire_without_charge():
    provider = LocalSyntheticBillingLifecycle(trial_days=7)
    trial = provider.apply_lifecycle(command(BillingLifecycleAction.START_TRIAL, "1", "PRO"))
    assert trial.status == BillingStatus.TRIAL
    assert trial.trial.ends_at == NOW + timedelta(days=7)

    upgraded = provider.apply_lifecycle(command(BillingLifecycleAction.UPGRADE, "2", "PREMIUM"))
    assert upgraded.plan.plan_id == "PREMIUM"
    downgraded = provider.apply_lifecycle(command(BillingLifecycleAction.DOWNGRADE, "3", "PRO"))
    assert downgraded.plan.plan_id == "PRO"
    cancelled = provider.apply_lifecycle(command(BillingLifecycleAction.CANCEL, "4"))
    assert cancelled.status == BillingStatus.CANCELLED
    expired = provider.apply_lifecycle(command(BillingLifecycleAction.EXPIRE, "5"))
    assert expired.status == BillingStatus.EXPIRED
    assert_no_payment_authority(provider, expired)


def test_subscribe_is_synthetic_idempotent_and_scoped():
    provider = LocalSyntheticBillingLifecycle()
    request = command(BillingLifecycleAction.SUBSCRIBE, "subscribe-1", "PREMIUM")
    first = provider.apply_lifecycle(request)
    second = provider.apply_lifecycle(request)
    assert first == second
    assert first.status == BillingStatus.ACTIVE
    assert provider.get_customer(SCOPE).tenant_id == SCOPE.tenant_id
    assert_no_payment_authority(provider, first)


def test_invalid_plan_directions_and_idempotency_reuse_fail_closed():
    provider = LocalSyntheticBillingLifecycle()
    first = command(BillingLifecycleAction.SUBSCRIBE, "same-key", "PREMIUM")
    provider.apply_lifecycle(first)
    with pytest.raises(SyntheticBillingLifecycleError):
        provider.apply_lifecycle(command(BillingLifecycleAction.SUBSCRIBE, "same-key", "ELITE"))
    with pytest.raises(SyntheticBillingLifecycleError):
        provider.apply_lifecycle(command(BillingLifecycleAction.UPGRADE, "up", "PRO"))
    with pytest.raises(SyntheticBillingLifecycleError):
        provider.apply_lifecycle(command(BillingLifecycleAction.DOWNGRADE, "down", "ELITE"))