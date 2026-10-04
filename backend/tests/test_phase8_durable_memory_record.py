"""R102A-C durable memory record, lifecycle and provenance regression tests."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from backend.medar.durable_memory_record import (
    DurableMemoryDomain, DurableMemoryRecord, DurableMemoryType,
    DurableSensitivity, MemoryLifecycle, ProvenanceClass, RetentionPolicy,
    content_digest,
)
from backend.medar.memory_provenance import MemoryOrigin, MemoryProvenance


NOW = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)


def _record(**changes):
    provenance = MemoryProvenance("source-1", MemoryOrigin.OBSERVED, NOW, "tenant-a", "owner-a", "context-1", 0.9)
    fields = dict(
        memory_id="memory-1", owner_id="owner-a", tenant_id="tenant-a",
        domain=DurableMemoryDomain.TECHNICAL, memory_type=DurableMemoryType.LESSON,
        content="A synthetic technical lesson", content_hash=content_digest("A synthetic technical lesson"),
        source_type="synthetic_test", source_reference="source-1",
        provenance=provenance, provenance_class=ProvenanceClass.DIRECT_OBSERVATION,
        confidence=0.9, importance=0.7, sensitivity=DurableSensitivity.INTERNAL,
        created_at=NOW, observed_at=NOW - timedelta(minutes=1), expires_at=None,
        retention_policy=RetentionPolicy.LONG_TERM, status=MemoryLifecycle.ACTIVE, version=1,
    )
    fields.update(changes)
    return DurableMemoryRecord(**fields)


def test_official_domains_lifecycle_and_provenance_are_explicit():
    assert len(DurableMemoryDomain) == 23
    assert {"NQ", "MNQ", "CRYPTO_ARBITRAGE", "ROSITA", "MODEL_PERFORMANCE"} <= {d.value for d in DurableMemoryDomain}
    assert {s.value for s in MemoryLifecycle} == {"ACTIVE", "SUPERSEDED", "EXPIRED", "RETRACTED", "QUARANTINED"}
    assert {p.value for p in ProvenanceClass} >= {"USER_STATED", "MODEL_INFERENCE", "IMPORTED", "UNKNOWN"}
    assert _record().content_hash == content_digest("A synthetic technical lesson")


def test_tampered_content_and_cross_scope_provenance_are_rejected():
    with pytest.raises(ValueError, match="hash"):
        _record(content="Changed content")
    with pytest.raises(ValueError, match="owner and tenant"):
        _record(owner_id="other")
    with pytest.raises(ValueError, match="owner and tenant"):
        _record(tenant_id="other")


def test_inference_and_imported_sources_remain_distinct():
    observed = _record()
    with pytest.raises(ValueError, match="inferred origin"):
        replace(observed, provenance_class=ProvenanceClass.MODEL_INFERENCE)
    inferred = replace(observed, provenance=replace(observed.provenance, origin=MemoryOrigin.INFERRED), provenance_class=ProvenanceClass.MODEL_INFERENCE)
    assert inferred.provenance.origin is MemoryOrigin.INFERRED
    with pytest.raises(ValueError, match="imported origin"):
        replace(observed, provenance_class=ProvenanceClass.IMPORTED)


def test_unknown_source_must_be_quarantined():
    with pytest.raises(ValueError, match="quarantined"):
        _record(provenance_class=ProvenanceClass.UNKNOWN)
    assert _record(provenance_class=ProvenanceClass.UNKNOWN, status=MemoryLifecycle.QUARANTINED).status is MemoryLifecycle.QUARANTINED


def test_working_retention_and_expiry_are_fail_closed():
    with pytest.raises(ValueError, match="working"):
        _record(domain=DurableMemoryDomain.WORKING)
    with pytest.raises(ValueError, match="expires_at"):
        _record(retention_policy=RetentionPolicy.UNTIL_DATE)
    with pytest.raises(ValueError, match="follow creation"):
        _record(expires_at=NOW)
    assert _record(retention_policy=RetentionPolicy.UNTIL_DATE, expires_at=NOW + timedelta(days=1)).expires_at is not None


@pytest.mark.parametrize("changes", [
    {"confidence": float("nan")},
    {"importance": float("inf")},
    {"created_at": datetime(2026, 10, 3)},
    {"version": 0},
    {"version": True},
])
def test_invalid_score_time_and_version_rejected(changes):
    with pytest.raises(ValueError):
        _record(**changes)


def test_nonfinite_source_confidence_cannot_enter_durable_memory():
    source = _record().provenance
    with pytest.raises(ValueError, match="confidence"):
        _record(provenance=replace(source, confidence=float("nan")))
