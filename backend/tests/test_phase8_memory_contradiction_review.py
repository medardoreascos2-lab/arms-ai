"""R117D high-importance contradictions require human review without mutation."""

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from backend.medar.durable_memory_record import (
    DurableMemoryDomain, DurableMemoryRecord, DurableMemoryType,
    DurableSensitivity, MemoryLifecycle, ProvenanceClass, RetentionPolicy,
    content_digest,
)
from backend.medar.memory_candidates import (
    CandidateImportance, CandidateSource, CandidateSourceType,
    MemoryCandidateExtractor,
)
from backend.medar.memory_conflicts import MemoryConflictReference, compare_memory_candidate
from backend.medar.memory_contradiction_review import (
    ContradictionReviewStatus, assess_contradiction_review,
)
from backend.medar.memory_provenance import MemoryOrigin, MemoryProvenance


NOW = datetime(2026, 10, 5, tzinfo=timezone.utc)


def _candidate(importance=CandidateImportance.HIGH):
    source = CandidateSource(
        "tenant-a", "owner-a", "synthetic-test:new", CandidateSourceType.TASK_OUTCOME,
        DurableMemoryDomain.TECHNICAL, "Outcome: deployment setting: disabled",
    )
    candidate = MemoryCandidateExtractor().extract(source).candidates[0]
    return replace(candidate, importance=importance, confidence=1.0)


def _record():
    content = "deployment setting: enabled"
    provenance = MemoryProvenance("synthetic-test:old", MemoryOrigin.OBSERVED, NOW, "tenant-a", "owner-a", "session-a", 1.0)
    return DurableMemoryRecord(
        "old", "owner-a", "tenant-a", DurableMemoryDomain.TECHNICAL,
        DurableMemoryType.FACT, content, content_digest(content), "synthetic_test",
        "synthetic-test:old", provenance, ProvenanceClass.DIRECT_OBSERVATION,
        1.0, 0.9, DurableSensitivity.INTERNAL, NOW, NOW, None,
        RetentionPolicy.LONG_TERM, MemoryLifecycle.ACTIVE, 1,
    )


def test_high_importance_conflict_requires_human_review_without_mutation():
    candidate = _candidate()
    existing = _record()
    conflict = compare_memory_candidate(
        candidate, MemoryConflictReference.from_record(existing),
    )
    review = assess_contradiction_review(
        candidate, existing, conflict, review_id="review-1", created_at=NOW,
    )
    assert review.status is ContradictionReviewStatus.REQUIRES_HUMAN_REVIEW
    assert review.reason_codes[0] == "HIGH_IMPORTANCE_CONFLICT"
    assert not review.resolution_authority
    assert not review.persistence_performed
    assert not review.memory_mutation_performed
    assert existing.status is MemoryLifecycle.ACTIVE


def test_lower_importance_conflict_does_not_create_required_review():
    candidate = _candidate(CandidateImportance.MEDIUM)
    existing = _record()
    conflict = compare_memory_candidate(
        candidate, MemoryConflictReference.from_record(existing),
    )
    review = assess_contradiction_review(
        candidate, existing, conflict, review_id="unused", created_at=NOW,
    )
    assert review.status is ContradictionReviewStatus.NOT_REQUIRED
    assert review.review_id is None


def test_cross_scope_or_mismatched_conflict_reference_is_denied():
    candidate = _candidate()
    existing = _record()
    conflict = compare_memory_candidate(
        candidate, MemoryConflictReference.from_record(existing),
    )
    with pytest.raises(PermissionError):
        assess_contradiction_review(
            candidate, replace(existing, owner_id="other", provenance=replace(existing.provenance, user_id="other")),
            conflict, review_id="review-1", created_at=NOW,
        )
    with pytest.raises(PermissionError):
        assess_contradiction_review(
            candidate, replace(existing, memory_id="other"), conflict,
            review_id="review-1", created_at=NOW,
        )
