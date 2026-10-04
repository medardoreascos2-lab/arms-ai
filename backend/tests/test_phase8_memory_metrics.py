"""R123A memory metrics remain scoped, aggregate, and content-free."""

from datetime import datetime, timezone

import pytest

from backend.medar.durable_memory_record import DurableMemoryDomain, DurableMemoryRecord, DurableMemoryType, DurableSensitivity, MemoryLifecycle, ProvenanceClass, RetentionPolicy, content_digest
from backend.medar.memory_metrics import MemoryMetrics
from backend.medar.memory_provenance import MemoryOrigin, MemoryProvenance
from backend.medar.sqlite_memory_store import MemoryScope

NOW = datetime(2026, 10, 5, tzinfo=timezone.utc)
SCOPE = MemoryScope("tenant-a", "owner-a")


def _record():
    content = "private-looking but synthetic metric content"
    return DurableMemoryRecord("memory-1", "owner-a", "tenant-a", DurableMemoryDomain.TECHNICAL, DurableMemoryType.FACT, content, content_digest(content), "synthetic_test", "source", MemoryProvenance("source", MemoryOrigin.OBSERVED, NOW, "tenant-a", "owner-a", "context", 1.0), ProvenanceClass.DIRECT_OBSERVATION, 1.0, 0.5, DurableSensitivity.INTERNAL, NOW, NOW, None, RetentionPolicy.LONG_TERM, MemoryLifecycle.ACTIVE, 1)


def test_metrics_aggregate_memory_dimensions_without_content_or_authority():
    metrics = MemoryMetrics(SCOPE)
    record = _record()
    metrics.observe_record(record)
    metrics.record_retrieval(hits=2, stale_skipped=1)
    metrics.record_retrieval(hits=0, blocked=True)
    metrics.record_backup()
    metrics.record_backup(restored=True)
    snapshot = metrics.snapshot()
    assert snapshot.records_observed == 1
    assert snapshot.records_by_domain == {"TECHNICAL": 1}
    assert snapshot.records_by_status == {"ACTIVE": 1}
    assert snapshot.records_by_sensitivity == {"INTERNAL": 1}
    assert snapshot.retrieval_queries == 2 and snapshot.retrieval_hits == 2
    assert snapshot.retrieval_hit_rate == 1.0
    assert snapshot.stale_records_skipped == 1 and snapshot.blocked_queries == 1
    assert snapshot.backup_successes == 1 and snapshot.restore_successes == 1
    assert record.content not in repr(snapshot)
    assert not snapshot.authority_granted


def test_metrics_reject_cross_scope_records_and_invalid_counts():
    metrics = MemoryMetrics(SCOPE)
    with pytest.raises(PermissionError, match="scope"):
        metrics.observe_record(_record().__class__(**{**_record().__dict__, "tenant_id": "other", "provenance": MemoryProvenance("source", MemoryOrigin.OBSERVED, NOW, "other", "owner-a", "context", 1.0)}))
    with pytest.raises(ValueError):
        metrics.record_retrieval(hits=-1)
    with pytest.raises(ValueError):
        metrics.record_retrieval(hits=1, blocked=True)
