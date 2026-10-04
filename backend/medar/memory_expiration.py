"""Fail-closed normal-retrieval eligibility for expiring memory."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from backend.medar.durable_memory_record import DurableMemoryRecord, MemoryLifecycle


class MemoryExpirationStatus(str, Enum):
    CURRENT = "CURRENT"
    EXPIRED = "EXPIRED"
    NO_EXPIRY = "NO_EXPIRY"
    INACTIVE = "INACTIVE"


@dataclass(frozen=True)
class MemoryExpirationAssessment:
    memory_id: str
    version: int
    status: MemoryExpirationStatus
    normal_retrieval_allowed: bool
    history_retained: bool = True
    deletion_performed: bool = False
    lifecycle_mutation_performed: bool = False

    def __post_init__(self) -> None:
        if not self.history_retained or self.deletion_performed or self.lifecycle_mutation_performed:
            raise ValueError("expiration assessment cannot delete or rewrite history")


def assess_memory_expiration(
    record: DurableMemoryRecord,
    *,
    as_of: datetime,
) -> MemoryExpirationAssessment:
    if not isinstance(record, DurableMemoryRecord):
        raise TypeError("durable memory record is required")
    if not isinstance(as_of, datetime) or as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("expiration assessment time must be timezone-aware")
    if record.status is not MemoryLifecycle.ACTIVE:
        status = MemoryExpirationStatus.INACTIVE
        allowed = False
    elif record.expires_at is None:
        status = MemoryExpirationStatus.NO_EXPIRY
        allowed = True
    elif record.expires_at <= as_of:
        status = MemoryExpirationStatus.EXPIRED
        allowed = False
    else:
        status = MemoryExpirationStatus.CURRENT
        allowed = True
    return MemoryExpirationAssessment(
        record.memory_id, record.version, status, allowed,
    )


def filter_normal_retrieval(
    records: tuple[DurableMemoryRecord, ...],
    *,
    as_of: datetime,
) -> tuple[DurableMemoryRecord, ...]:
    if not isinstance(records, tuple) or any(not isinstance(record, DurableMemoryRecord) for record in records):
        raise TypeError("typed durable memory records are required")
    return tuple(
        record for record in records
        if assess_memory_expiration(record, as_of=as_of).normal_retrieval_allowed
    )
