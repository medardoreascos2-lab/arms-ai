"""Deterministic retention plans for every durable memory policy."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from backend.medar.durable_memory_record import RetentionPolicy


@dataclass(frozen=True)
class MemoryRetentionPlan:
    policy: RetentionPolicy
    created_at: datetime
    expires_at: datetime | None
    durable_storage_allowed: bool
    normal_retrieval_allowed: bool
    human_review_required: bool
    deletion_authority: bool = False

    def __post_init__(self) -> None:
        if self.deletion_authority:
            raise ValueError("retention plan cannot authorize deletion")
        if self.policy is RetentionPolicy.UNTIL_DATE and self.expires_at is None:
            raise ValueError("until-date retention requires expiration")
        if self.expires_at is not None and self.expires_at <= self.created_at:
            raise ValueError("retention expiration must follow creation")


def plan_memory_retention(
    policy: RetentionPolicy,
    *,
    created_at: datetime,
    until_date: datetime | None = None,
    short_term_days: int = 30,
) -> MemoryRetentionPlan:
    if not isinstance(policy, RetentionPolicy):
        raise TypeError("retention policy must be typed")
    if not isinstance(created_at, datetime) or created_at.tzinfo is None or created_at.utcoffset() is None:
        raise ValueError("retention creation time must be timezone-aware")
    if isinstance(short_term_days, bool) or not isinstance(short_term_days, int) or not 1 <= short_term_days <= 365:
        raise ValueError("short-term retention days must be from 1 to 365")
    if until_date is not None and (
        not isinstance(until_date, datetime)
        or until_date.tzinfo is None or until_date.utcoffset() is None
        or until_date <= created_at
    ):
        raise ValueError("until_date must be an aware future time")
    if policy is not RetentionPolicy.UNTIL_DATE and until_date is not None:
        raise ValueError("until_date is valid only for UNTIL_DATE retention")
    if policy is RetentionPolicy.SESSION:
        return MemoryRetentionPlan(policy, created_at, None, False, True, False)
    if policy is RetentionPolicy.SHORT_TERM:
        return MemoryRetentionPlan(
            policy, created_at, created_at + timedelta(days=short_term_days),
            True, True, False,
        )
    if policy is RetentionPolicy.LONG_TERM:
        return MemoryRetentionPlan(policy, created_at, None, True, True, False)
    if policy is RetentionPolicy.ARCHIVE:
        return MemoryRetentionPlan(policy, created_at, None, True, False, False)
    if policy is RetentionPolicy.UNTIL_DATE:
        return MemoryRetentionPlan(policy, created_at, until_date, True, True, False)
    return MemoryRetentionPlan(policy, created_at, None, True, True, True)
