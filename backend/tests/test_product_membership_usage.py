"""P108C configurable Product usage limit tests."""

import pytest

from backend.product.membership_catalog import ProductPlanId
from backend.product.membership_usage import (
    PRODUCT_USAGE_LIMITS,
    ProductUsageLimits,
    ProductUsageResource,
    evaluate_product_usage,
)


def test_every_plan_configures_current_usage_limits_and_defers_voice_video():
    assert set(PRODUCT_USAGE_LIMITS) == set(ProductPlanId)
    for limits in PRODUCT_USAGE_LIMITS.values():
        assert limits.medar_requests >= 0
        assert limits.research_jobs >= 0
        assert limits.portfolio_count >= 0
        assert limits.notification_count >= 0
        assert limits.memory_quota >= 0
        assert limits.voice_quota is None
        assert limits.video_quota is None


def test_usage_evaluation_allows_with_remaining_capacity_and_blocks_at_limit():
    allowed = evaluate_product_usage(
        ProductPlanId.PREMIUM,
        ProductUsageResource.MEDAR_REQUESTS,
        used=499,
    )
    assert allowed.allowed is True
    assert allowed.remaining == 0
    denied = evaluate_product_usage(
        ProductPlanId.PREMIUM,
        ProductUsageResource.MEDAR_REQUESTS,
        used=500,
    )
    assert denied.allowed is False
    assert denied.code == "LIMIT_REACHED"
    assert denied.remaining == 0


def test_future_usage_is_unavailable_and_invalid_counts_fail_closed():
    future = evaluate_product_usage(
        ProductPlanId.ELITE,
        ProductUsageResource.VOICE_QUOTA,
        used=0,
    )
    assert future.allowed is False
    assert future.code == "FEATURE_UNAVAILABLE"
    with pytest.raises(ValueError):
        evaluate_product_usage(
            ProductPlanId.FREE,
            ProductUsageResource.NOTIFICATION_COUNT,
            used=-1,
        )
    with pytest.raises(ValueError):
        ProductUsageLimits(-1, 0, 0, 0, 0)
