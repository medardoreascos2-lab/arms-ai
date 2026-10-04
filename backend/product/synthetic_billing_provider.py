"""Deterministic local billing lifecycle for tests; it never charges or pays."""

from __future__ import annotations

from datetime import timedelta
from hashlib import sha256

from backend.product.billing import BillingCustomer, BillingStatus, Plan, Subscription, Trial
from backend.product.billing_provider import (
    BillingLifecycleAction,
    BillingLifecycleCommand,
    BillingProviderStatus,
    BillingScope,
)
from backend.product.membership_catalog import ProductPlanId


_PLAN_RANK = {
    ProductPlanId.FREE: 0,
    ProductPlanId.PRO: 1,
    ProductPlanId.PREMIUM: 2,
    ProductPlanId.ELITE: 3,
}


class SyntheticBillingLifecycleError(ValueError):
    pass


class LocalSyntheticBillingLifecycle:
    """In-memory, metadata-only lifecycle used by tests and local development."""

    def __init__(self, *, trial_days: int = 14, catalog_version: str = "1") -> None:
        if trial_days < 1:
            raise ValueError("trial_days must be positive")
        self._trial_days = trial_days
        self._catalog_version = catalog_version
        self._customers: dict[tuple[str, str], BillingCustomer] = {}
        self._subscriptions: dict[tuple[str, str], Subscription] = {}
        self._idempotency: dict[tuple[str, str, str], tuple[str, Subscription]] = {}

    def status(self) -> BillingProviderStatus:
        return BillingProviderStatus()

    def get_customer(self, scope: BillingScope) -> BillingCustomer | None:
        return self._customers.get(self._key(scope))

    def get_subscription(self, scope: BillingScope) -> Subscription | None:
        return self._subscriptions.get(self._key(scope))

    def apply_lifecycle(self, command: BillingLifecycleCommand) -> Subscription:
        key = self._key(command.scope)
        idempotency_key = (*key, command.idempotency_key)
        fingerprint = command.model_dump_json()
        previous = self._idempotency.get(idempotency_key)
        if previous is not None:
            if previous[0] != fingerprint:
                raise SyntheticBillingLifecycleError("idempotency key reused for another command")
            return previous[1]

        customer = self._customers.get(key) or self._new_customer(command.scope)
        current = self._subscriptions.get(key)
        result = self._transition(customer, current, command)
        self._customers[key] = customer
        self._subscriptions[key] = result
        self._idempotency[idempotency_key] = (fingerprint, result)
        return result

    def _transition(
        self,
        customer: BillingCustomer,
        current: Subscription | None,
        command: BillingLifecycleCommand,
    ) -> Subscription:
        action = command.action
        target = command.target_plan_id
        if action in {
            BillingLifecycleAction.START_TRIAL,
            BillingLifecycleAction.SUBSCRIBE,
            BillingLifecycleAction.UPGRADE,
            BillingLifecycleAction.DOWNGRADE,
        } and target is None:
            raise SyntheticBillingLifecycleError("target plan is required")

        if action == BillingLifecycleAction.START_TRIAL:
            if current is not None:
                raise SyntheticBillingLifecycleError("trial requires no existing subscription")
            return self._new_subscription(
                customer, command.scope, target, BillingStatus.TRIAL,
                Trial(
                    starts_at=command.requested_at,
                    ends_at=command.requested_at + timedelta(days=self._trial_days),
                ),
            )

        if action == BillingLifecycleAction.SUBSCRIBE:
            if current is not None and current.status not in {
                BillingStatus.CANCELLED, BillingStatus.EXPIRED, BillingStatus.INCOMPLETE,
            }:
                raise SyntheticBillingLifecycleError("subscribe requires no active lifecycle")
            return self._new_subscription(customer, command.scope, target, BillingStatus.ACTIVE)

        if current is None:
            raise SyntheticBillingLifecycleError("lifecycle transition requires a subscription")

        if action in {BillingLifecycleAction.UPGRADE, BillingLifecycleAction.DOWNGRADE}:
            if current.status not in {BillingStatus.TRIAL, BillingStatus.ACTIVE}:
                raise SyntheticBillingLifecycleError("plan change requires trial or active status")
            current_rank = _PLAN_RANK[current.plan.plan_id]
            target_rank = _PLAN_RANK[target]
            if action == BillingLifecycleAction.UPGRADE and target_rank <= current_rank:
                raise SyntheticBillingLifecycleError("upgrade target must be higher")
            if action == BillingLifecycleAction.DOWNGRADE and target_rank >= current_rank:
                raise SyntheticBillingLifecycleError("downgrade target must be lower")
            return current.model_copy(update={
                "plan": Plan(plan_id=target, catalog_version=self._catalog_version),
                "version": current.version + 1,
            })

        if action == BillingLifecycleAction.CANCEL:
            if current.status not in {BillingStatus.TRIAL, BillingStatus.ACTIVE, BillingStatus.PAST_DUE}:
                raise SyntheticBillingLifecycleError("subscription cannot be cancelled")
            return current.model_copy(update={
                "status": BillingStatus.CANCELLED,
                "version": current.version + 1,
            })

        if action == BillingLifecycleAction.EXPIRE:
            if current.status not in {BillingStatus.TRIAL, BillingStatus.CANCELLED}:
                raise SyntheticBillingLifecycleError("subscription cannot expire")
            return current.model_copy(update={
                "status": BillingStatus.EXPIRED,
                "version": current.version + 1,
            })

        raise SyntheticBillingLifecycleError("unsupported lifecycle action")

    def _new_customer(self, scope: BillingScope) -> BillingCustomer:
        token = self._scope_token(scope)
        return BillingCustomer(
            billing_customer_id=f"synthetic-customer-{token}",
            tenant_id=scope.tenant_id,
            user_id=scope.user_id,
            provider="LOCAL_SYNTHETIC",
        )

    def _new_subscription(
        self,
        customer: BillingCustomer,
        scope: BillingScope,
        plan_id: ProductPlanId,
        status: BillingStatus,
        trial: Trial | None = None,
    ) -> Subscription:
        return Subscription(
            subscription_id=f"synthetic-subscription-{self._scope_token(scope)}",
            billing_customer_id=customer.billing_customer_id,
            tenant_id=scope.tenant_id,
            user_id=scope.user_id,
            plan=Plan(plan_id=plan_id, catalog_version=self._catalog_version),
            status=status,
            trial=trial,
            version=1,
        )

    @staticmethod
    def _key(scope: BillingScope) -> tuple[str, str]:
        return scope.tenant_id, scope.user_id

    @staticmethod
    def _scope_token(scope: BillingScope) -> str:
        raw = f"{scope.tenant_id}\0{scope.user_id}".encode("utf-8")
        return sha256(raw).hexdigest()[:24]