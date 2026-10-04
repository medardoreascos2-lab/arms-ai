"""P111B closed-beta capacity policy tests."""

from datetime import datetime, timezone

import pytest

from backend.product.beta_access import BetaAccessRecord
from backend.product.beta_capacity import (
    BetaCapacityPolicy,
    BetaCapacityState,
    evaluate_beta_capacity,
)


NOW = datetime(2026, 10, 4, tzinfo=timezone.utc)


def records(count):
    return tuple(BetaAccessRecord(
        access_id=f"access-{index}", tenant_id="tenant", user_id=f"user-{index}",
        status="ACTIVE", invited_at=NOW, updated_at=NOW, version=1,
    ) for index in range(count))


def test_default_target_is_ten_to_thirty_users():
    policy = BetaCapacityPolicy()
    assert (policy.target_min_users, policy.target_max_users) == (10, 30)
    assert evaluate_beta_capacity(records(9), policy).state == BetaCapacityState.BELOW_TARGET
    assert evaluate_beta_capacity(records(10), policy).state == BetaCapacityState.WITHIN_TARGET
    full = evaluate_beta_capacity(records(30), policy)
    assert full.state == BetaCapacityState.AT_CAPACITY
    assert full.admission_available is False
    assert full.remaining_slots == 0


def test_capacity_is_configurable_and_counts_only_active_users():
    policy = BetaCapacityPolicy(target_min_users=2, target_max_users=3)
    mixed = list(records(2))
    mixed.append(mixed[0].model_copy(update={
        "access_id": "paused", "user_id": "paused", "status": "PAUSED",
    }))
    result = evaluate_beta_capacity(tuple(mixed), policy)
    assert result.active_users == 2
    assert result.remaining_slots == 1
    assert result.admission_available is True
    with pytest.raises(ValueError):
        BetaCapacityPolicy(target_min_users=5, target_max_users=4)