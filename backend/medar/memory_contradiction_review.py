"""Human review state for conflicting high-importance memory."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from backend.medar.durable_memory_record import DurableMemoryRecord, MemoryLifecycle
from backend.medar.memory_candidates import CandidateImportance, MemoryCandidate
from backend.medar.memory_conflicts import MemoryConflictAssessment, MemoryConflictKind


class ContradictionReviewStatus(str, Enum):
    NOT_REQUIRED = "NOT_REQUIRED"
    REQUIRES_HUMAN_REVIEW = "REQUIRES_HUMAN_REVIEW"


@dataclass(frozen=True)
class MemoryContradictionReview:
    review_id: str | None
    tenant_id: str
    owner_id: str
    candidate_id: str
    existing_memory_id: str
    status: ContradictionReviewStatus
    reason_codes: tuple[str, ...]
    created_at: datetime
    resolution_authority: bool = False
    persistence_performed: bool = False
    memory_mutation_performed: bool = False

    def __post_init__(self) -> None:
        if self.status is ContradictionReviewStatus.REQUIRES_HUMAN_REVIEW and not self.review_id:
            raise ValueError("required contradiction review needs an ID")
        if self.status is ContradictionReviewStatus.NOT_REQUIRED and self.review_id is not None:
            raise ValueError("non-required contradiction cannot claim a review ID")
        if self.resolution_authority or self.persistence_performed or self.memory_mutation_performed:
            raise ValueError("contradiction review cannot resolve or mutate memory")


def assess_contradiction_review(
    candidate: MemoryCandidate,
    existing: DurableMemoryRecord,
    conflict: MemoryConflictAssessment,
    *,
    review_id: str,
    created_at: datetime,
) -> MemoryContradictionReview:
    if not isinstance(candidate, MemoryCandidate) or not isinstance(existing, DurableMemoryRecord):
        raise TypeError("candidate and existing durable memory are required")
    if not isinstance(conflict, MemoryConflictAssessment):
        raise TypeError("memory conflict assessment is required")
    if not isinstance(review_id, str) or not review_id.strip() or len(review_id) > 240:
        raise ValueError("contradiction review ID must be bounded text")
    if not isinstance(created_at, datetime) or created_at.tzinfo is None or created_at.utcoffset() is None:
        raise ValueError("contradiction review time must be timezone-aware")
    if candidate.tenant_id != existing.tenant_id or candidate.owner_id != existing.owner_id:
        raise PermissionError("contradiction review scope mismatch")
    if candidate.domain is not existing.domain or existing.status is not MemoryLifecycle.ACTIVE:
        raise PermissionError("contradiction review requires active same-domain memory")
    if conflict.existing_memory_id != existing.memory_id or conflict.persistence_performed:
        raise PermissionError("contradiction assessment does not match durable memory")
    high_importance = (
        candidate.importance in (CandidateImportance.HIGH, CandidateImportance.CRITICAL)
        and existing.importance >= 0.8
    )
    conflicting = conflict.kind in (
        MemoryConflictKind.CONTRADICTION,
        MemoryConflictKind.POSSIBLE_SUPERSESSION,
    )
    if high_importance and conflicting:
        return MemoryContradictionReview(
            review_id, candidate.tenant_id, candidate.owner_id,
            candidate.candidate_id, existing.memory_id,
            ContradictionReviewStatus.REQUIRES_HUMAN_REVIEW,
            ("HIGH_IMPORTANCE_CONFLICT", *conflict.reason_codes), created_at,
        )
    return MemoryContradictionReview(
        None, candidate.tenant_id, candidate.owner_id,
        candidate.candidate_id, existing.memory_id,
        ContradictionReviewStatus.NOT_REQUIRED,
        ("HIGH_IMPORTANCE_CONFLICT_NOT_ESTABLISHED",), created_at,
    )
