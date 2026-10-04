"""R118A all declared memory retention policies have deterministic plans."""

from datetime import datetime, timedelta, timezone

import pytest

from backend.medar.durable_memory_record import RetentionPolicy
from backend.medar.memory_retention import plan_memory_retention


NOW = datetime(2026, 10, 5, 1, tzinfo=timezone.utc)


def test_every_retention_policy_has_an_explicit_plan():
    until = NOW + timedelta(days=10)
    plans = {
        policy: plan_memory_retention(
            policy, created_at=NOW,
            until_date=until if policy is RetentionPolicy.UNTIL_DATE else None,
        )
        for policy in RetentionPolicy
    }
    assert set(plans) == set(RetentionPolicy)
    assert not plans[RetentionPolicy.SESSION].durable_storage_allowed
    assert plans[RetentionPolicy.SHORT_TERM].expires_at == NOW + timedelta(days=30)
    assert plans[RetentionPolicy.LONG_TERM].expires_at is None
    assert not plans[RetentionPolicy.ARCHIVE].normal_retrieval_allowed
    assert plans[RetentionPolicy.UNTIL_DATE].expires_at == until
    assert plans[RetentionPolicy.MANUAL_REVIEW].human_review_required
    assert all(not plan.deletion_authority for plan in plans.values())


def test_short_term_window_is_bounded_and_configurable():
    plan = plan_memory_retention(
        RetentionPolicy.SHORT_TERM, created_at=NOW, short_term_days=7,
    )
    assert plan.expires_at == NOW + timedelta(days=7)
    with pytest.raises(ValueError):
        plan_memory_retention(
            RetentionPolicy.SHORT_TERM, created_at=NOW, short_term_days=0,
        )


def test_until_date_is_required_and_forbidden_for_other_policies():
    with pytest.raises(ValueError):
        plan_memory_retention(RetentionPolicy.UNTIL_DATE, created_at=NOW)
    with pytest.raises(ValueError):
        plan_memory_retention(
            RetentionPolicy.LONG_TERM, created_at=NOW,
            until_date=NOW + timedelta(days=1),
        )
    with pytest.raises(ValueError):
        plan_memory_retention(
            RetentionPolicy.UNTIL_DATE, created_at=NOW,
            until_date=NOW,
        )
