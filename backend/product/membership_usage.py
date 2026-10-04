"""Configurable Product membership usage limits."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Mapping

from backend.product.membership_catalog import ProductPlanId


class ProductUsageResource(str, Enum):
    MEDAR_REQUESTS = "MEDAR_REQUESTS"
    RESEARCH_JOBS = "RESEARCH_JOBS"
    PORTFOLIO_COUNT = "PORTFOLIO_COUNT"
    NOTIFICATION_COUNT = "NOTIFICATION_COUNT"
    MEMORY_QUOTA = "MEMORY_QUOTA"
    VOICE_QUOTA = "VOICE_QUOTA"
    VIDEO_QUOTA = "VIDEO_QUOTA"


@dataclass(frozen=True)
class ProductUsageLimits:
    medar_requests: int
    research_jobs: int
    portfolio_count: int
    notification_count: int
    memory_quota: int
    voice_quota: int | None = None
    video_quota: int | None = None

    def __post_init__(self) -> None:
        for name in (
            "medar_requests", "research_jobs", "portfolio_count",
            "notification_count", "memory_quota",
        ):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} must be a nonnegative integer")
        for name in ("voice_quota", "video_quota"):
            value = getattr(self, name)
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError(f"{name} must be a nonnegative integer or unavailable")


@dataclass(frozen=True)
class ProductUsageDecision:
    allowed: bool
    resource: ProductUsageResource
    limit: int | None
    remaining: int | None
    code: str

    def __post_init__(self) -> None:
        if self.allowed != (self.code == "ALLOWED"):
            raise ValueError("usage decision code must match allowed state")


PRODUCT_USAGE_LIMITS: Mapping[
    ProductPlanId, ProductUsageLimits
] = MappingProxyType({
    ProductPlanId.FREE: ProductUsageLimits(20, 0, 1, 50, 25),
    ProductPlanId.PRO: ProductUsageLimits(100, 10, 3, 250, 200),
    ProductPlanId.PREMIUM: ProductUsageLimits(500, 50, 10, 1000, 1000),
    ProductPlanId.ELITE: ProductUsageLimits(2000, 200, 25, 5000, 5000),
})


def evaluate_product_usage(
    plan_id: ProductPlanId, resource: ProductUsageResource,
    *, used: int, additional: int = 1,
) -> ProductUsageDecision:
    if not isinstance(plan_id, ProductPlanId):
        raise ValueError("canonical Product plan required")
    if not isinstance(resource, ProductUsageResource):
        raise ValueError("canonical Product usage resource required")
    if type(used) is not int or used < 0:
        raise ValueError("used must be a nonnegative integer")
    if type(additional) is not int or additional < 1:
        raise ValueError("additional must be a positive integer")
    field = resource.value.lower()
    limit = getattr(PRODUCT_USAGE_LIMITS[plan_id], field)
    if limit is None:
        return ProductUsageDecision(
            False, resource, None, None, "FEATURE_UNAVAILABLE",
        )
    remaining = max(0, limit - used)
    if used + additional > limit:
        return ProductUsageDecision(
            False, resource, limit, remaining, "LIMIT_REACHED",
        )
    return ProductUsageDecision(
        True, resource, limit, limit - used - additional, "ALLOWED",
    )
