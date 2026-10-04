"""Provider-neutral Product MEDAR usage limits; values are local test fixtures only."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from threading import Lock
from typing import Mapping

from backend.entitlements import FeatureEntitlement
from backend.product.surface import ProductTier


@dataclass(frozen=True)
class ProductMedarLimits:
    requests_per_period: int
    period_seconds: int
    concurrent_requests: int
    max_input_chars: int
    max_output_chars: int
    plan_entitlement: FeatureEntitlement = FeatureEntitlement.MEDAR_CONVERSATION
    future_token_budget: int | None = None

    def __post_init__(self) -> None:
        for name in (
            "requests_per_period", "period_seconds", "concurrent_requests",
            "max_input_chars", "max_output_chars",
        ):
            if type(getattr(self, name)) is not int or getattr(self, name) < 1:
                raise ValueError(f"{name} must be a positive integer")
        if not isinstance(self.plan_entitlement, FeatureEntitlement):
            raise ValueError("canonical plan entitlement required")
        if self.future_token_budget is not None and (
            type(self.future_token_budget) is not int or self.future_token_budget < 1
        ):
            raise ValueError("future token budget must be positive when configured")


class UsageDecisionCode(str, Enum):
    ALLOWED = "ALLOWED"
    PLAN_NOT_CONFIGURED = "PLAN_NOT_CONFIGURED"
    ENTITLEMENT_REQUIRED = "ENTITLEMENT_REQUIRED"
    INPUT_TOO_LARGE = "INPUT_TOO_LARGE"
    RATE_LIMITED = "RATE_LIMITED"
    CONCURRENT_LIMIT = "CONCURRENT_LIMIT"


@dataclass(frozen=True)
class UsageDecision:
    code: UsageDecisionCode
    limits: ProductMedarLimits | None

    @property
    def allowed(self) -> bool:
        return self.code == UsageDecisionCode.ALLOWED


class ProductMedarUsageGate:
    """Atomic per-session in-memory accounting; no billing or durable writes."""

    def __init__(self, limits_by_tier: Mapping[ProductTier, ProductMedarLimits]) -> None:
        if any(not isinstance(tier, ProductTier) or not isinstance(limits, ProductMedarLimits)
               for tier, limits in limits_by_tier.items()):
            raise ValueError("typed Product tier limits required")
        self._limits = dict(limits_by_tier)
        self._lock = Lock()
        self._windows: dict[str, tuple[datetime, int]] = {}
        self._active: dict[str, int] = {}

    def acquire(
        self, *, session_id: str, tier: ProductTier,
        entitlements: frozenset[FeatureEntitlement],
        input_chars: int, at: datetime,
    ) -> UsageDecision:
        limits = self._limits.get(tier)
        if limits is None:
            return UsageDecision(UsageDecisionCode.PLAN_NOT_CONFIGURED, None)
        if limits.plan_entitlement not in entitlements:
            return UsageDecision(UsageDecisionCode.ENTITLEMENT_REQUIRED, limits)
        if type(input_chars) is not int or input_chars < 1 or input_chars > limits.max_input_chars:
            return UsageDecision(UsageDecisionCode.INPUT_TOO_LARGE, limits)
        if not isinstance(session_id, str) or not session_id:
            raise ValueError("session identifier required")
        if not isinstance(at, datetime) or at.tzinfo is None or at.utcoffset() != timedelta(0):
            raise ValueError("UTC usage timestamp required")
        with self._lock:
            start, count = self._windows.get(session_id, (at, 0))
            if at < start or at >= start + timedelta(seconds=limits.period_seconds):
                start, count = at, 0
            if count >= limits.requests_per_period:
                return UsageDecision(UsageDecisionCode.RATE_LIMITED, limits)
            active = self._active.get(session_id, 0)
            if active >= limits.concurrent_requests:
                return UsageDecision(UsageDecisionCode.CONCURRENT_LIMIT, limits)
            self._windows[session_id] = (start, count + 1)
            self._active[session_id] = active + 1
        return UsageDecision(UsageDecisionCode.ALLOWED, limits)

    def release(self, session_id: str) -> None:
        with self._lock:
            active = self._active.get(session_id, 0)
            if active < 1:
                raise ValueError("no Product MEDAR usage lease to release")
            if active == 1:
                self._active.pop(session_id)
            else:
                self._active[session_id] = active - 1


def local_test_usage_gate() -> ProductMedarUsageGate:
    """Noncommercial limits used only by the explicit local test router."""
    limits = ProductMedarLimits(
        requests_per_period=20,
        period_seconds=3600,
        concurrent_requests=1,
        max_input_chars=8192,
        max_output_chars=16384,
    )
    return ProductMedarUsageGate({
        tier: limits for tier in (
            ProductTier.FREE, ProductTier.PRO, ProductTier.PREMIUM, ProductTier.ELITE,
        )
    })
