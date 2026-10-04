"""R117B relevance decay lowers retrieval weight without deleting memory."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from backend.medar.durable_memory_record import (
    DurableMemoryDomain, DurableMemoryRecord, DurableMemoryType,
    DurableSensitivity, MemoryLifecycle, ProvenanceClass, RetentionPolicy,
    content_digest,
)
from backend.medar.memory_provenance import MemoryOrigin, MemoryProvenance
from backend.medar.memory_relevance_decay import assess_memory_relevance


NOW = datetime(2026, 10, 4, 22, tzinfo=timezone.utc)


def _record(importance=0.5, observed_at=None):
    observed = observed_at or NOW - timedelta(days=60)
    provenance = MemoryProvenance("synthetic-test:m1", MemoryOrigin.OBSERVED, observed, "tenant-a", "owner-a", "session-a", 1.0)
    return DurableMemoryRecord(
        "m1", "owner-a", "tenant-a", DurableMemoryDomain.TECHNICAL,
        DurableMemoryType.LESSON, "bounded lesson", content_digest("bounded lesson"),
        "synthetic_test", "synthetic-test:m1", provenance,
        ProvenanceClass.DIRECT_OBSERVATION, 1.0, importance,
        DurableSensitivity.INTERNAL, observed, observed, None,
        RetentionPolicy.LONG_TERM, MemoryLifecycle.ACTIVE, 1,
    )


def test_lower_priority_and_older_memory_lose_retrieval_weight():
    low = assess_memory_relevance(_record(0.2), as_of=NOW)
    high = assess_memory_relevance(_record(0.9), as_of=NOW)
    newer = assess_memory_relevance(
        _record(0.2, NOW - timedelta(days=5)), as_of=NOW,
    )
    assert 0 < low.effective_weight < low.original_importance
    assert high.effective_weight > low.effective_weight
    assert newer.effective_weight > low.effective_weight
    assert low.age_days == 60.0


def test_decay_never_deletes_or_changes_lifecycle():
    record = _record()
    assessment = assess_memory_relevance(record, as_of=NOW)
    assert record.status is MemoryLifecycle.ACTIVE
    assert record.version == 1
    assert not assessment.deletion_authority
    assert not assessment.lifecycle_changed


def test_inactive_future_and_invalid_half_life_fail_closed():
    record = _record()
    with pytest.raises(PermissionError):
        assess_memory_relevance(replace(record, status=MemoryLifecycle.EXPIRED), as_of=NOW)
    with pytest.raises(ValueError):
        assess_memory_relevance(record, as_of=record.observed_at - timedelta(seconds=1))
    with pytest.raises(ValueError):
        assess_memory_relevance(record, as_of=NOW, base_half_life_days=0)
