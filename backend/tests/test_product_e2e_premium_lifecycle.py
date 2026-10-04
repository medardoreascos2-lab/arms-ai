"""P118B synthetic premium-user membership lifecycle rehearsal."""

from datetime import datetime, timedelta, timezone

from backend.entitlements import FeatureEntitlement
from backend.product.billing import BillingStatus
from backend.product.billing_provider import BillingLifecycleAction, BillingLifecycleCommand, BillingScope
from backend.product.membership_entitlements import entitlements_for_plan
from backend.product.membership_usage import ProductUsageResource, evaluate_product_usage
from backend.product.synthetic_billing_provider import LocalSyntheticBillingLifecycle


NOW = datetime(2026, 10, 4, 12, tzinfo=timezone.utc)
SCOPE = BillingScope(tenant_id="synthetic-tenant-e2e", user_id="synthetic-premium-user")


def command(action, key, plan=None, offset=0):
    return BillingLifecycleCommand(
        action=action,
        scope=SCOPE,
        target_plan_id=plan,
        idempotency_key=key,
        requested_at=NOW + timedelta(minutes=offset),
    )


def test_synthetic_premium_lifecycle_updates_product_access_without_charge():
    provider = LocalSyntheticBillingLifecycle()
    trial = provider.apply_lifecycle(command(BillingLifecycleAction.START_TRIAL, "trial", "PRO"))
    assert trial.status == BillingStatus.TRIAL
    assert FeatureEntitlement.MEDAR_CONVERSATION in entitlements_for_plan(trial.plan.plan_id)

    premium = provider.apply_lifecycle(command(BillingLifecycleAction.UPGRADE, "upgrade", "PREMIUM", 1))
    assert FeatureEntitlement.TRADING_WORKSPACE in entitlements_for_plan(premium.plan.plan_id)
    usage = evaluate_product_usage(
        premium.plan.plan_id, ProductUsageResource.MEDAR_REQUESTS, used=499,
    )
    assert usage.allowed is True and usage.remaining == 0

    pro = provider.apply_lifecycle(command(BillingLifecycleAction.DOWNGRADE, "downgrade", "PRO", 2))
    assert FeatureEntitlement.TRADING_WORKSPACE not in entitlements_for_plan(pro.plan.plan_id)
    cancelled = provider.apply_lifecycle(command(BillingLifecycleAction.CANCEL, "cancel", offset=3))
    expired = provider.apply_lifecycle(command(BillingLifecycleAction.EXPIRE, "expire", offset=4))
    renewed = provider.apply_lifecycle(command(BillingLifecycleAction.SUBSCRIBE, "renew", "PREMIUM", 5))

    assert cancelled.status == BillingStatus.CANCELLED
    assert expired.status == BillingStatus.EXPIRED
    assert renewed.status == BillingStatus.ACTIVE
    for subscription in (trial, premium, pro, cancelled, expired, renewed):
        assert subscription.payment_provider_connected is False
        assert subscription.charge_authorized is False
        assert subscription.invoice_references == ()
    assert provider.status().connected is False
    assert provider.status().supports_charges is False