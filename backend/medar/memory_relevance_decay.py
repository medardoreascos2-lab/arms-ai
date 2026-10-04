"""Time-based retrieval weight decay that never deletes memory."""

import math
from dataclasses import dataclass
from datetime import datetime

from backend.medar.durable_memory_record import DurableMemoryRecord, MemoryLifecycle


@dataclass(frozen=True)
class MemoryRelevanceAssessment:
    memory_id: str
    version: int
    original_importance: float
    effective_weight: float
    age_days: float
    deletion_authority: bool = False
    lifecycle_changed: bool = False

    def __post_init__(self) -> None:
        if self.deletion_authority or self.lifecycle_changed:
            raise ValueError("relevance decay cannot delete or transition memory")


def assess_memory_relevance(
    record: DurableMemoryRecord,
    *,
    as_of: datetime,
    base_half_life_days: float = 30.0,
) -> MemoryRelevanceAssessment:
    if not isinstance(record, DurableMemoryRecord):
        raise TypeError("durable memory record is required")
    if record.status is not MemoryLifecycle.ACTIVE:
        raise PermissionError("normal retrieval decay applies only to active memory")
    if not isinstance(as_of, datetime) or as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("relevance assessment time must be timezone-aware")
    if isinstance(base_half_life_days, bool) or not isinstance(base_half_life_days, (int, float)) or not math.isfinite(base_half_life_days) or base_half_life_days <= 0:
        raise ValueError("base half life must be finite and positive")
    if as_of < record.observed_at:
        raise ValueError("relevance assessment cannot precede observation")
    age_days = (as_of - record.observed_at).total_seconds() / 86400.0
    effective_half_life = base_half_life_days * (1.0 + 3.0 * record.importance)
    weight = record.importance * math.pow(0.5, age_days / effective_half_life)
    return MemoryRelevanceAssessment(
        record.memory_id, record.version, record.importance,
        max(0.0, min(record.importance, weight)), age_days,
    )
