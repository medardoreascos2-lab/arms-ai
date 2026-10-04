"""Review-only MEDAR memory duplicate and conflict detection.

Semantic similarity is optional and caller supplied. No comparator here claims
real semantic quality, and no result mutates or supersedes stored memory.
"""

import math
import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Protocol

from backend.medar.durable_memory_record import DurableMemoryDomain, DurableMemoryRecord, MemoryLifecycle
from backend.medar.memory_candidates import MemoryCandidate


class MemoryConflictKind(str, Enum):
    EXACT_DUPLICATE = "EXACT_DUPLICATE"
    NEAR_DUPLICATE = "NEAR_DUPLICATE"
    CONTRADICTION = "CONTRADICTION"
    POSSIBLE_SUPERSESSION = "POSSIBLE_SUPERSESSION"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class MemoryConflictReference:
    memory_id: str
    tenant_id: str
    owner_id: str
    domain: DurableMemoryDomain
    content: str
    observed_at: datetime
    status: MemoryLifecycle

    @classmethod
    def from_record(cls, record: DurableMemoryRecord) -> "MemoryConflictReference":
        return cls(
            record.memory_id, record.tenant_id, record.owner_id,
            record.domain, record.content, record.observed_at, record.status,
        )

    def __post_init__(self) -> None:
        for name in ("memory_id", "tenant_id", "owner_id", "content"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be non-empty text")
        if not isinstance(self.domain, DurableMemoryDomain) or not isinstance(self.status, MemoryLifecycle):
            raise TypeError("conflict reference classification must be typed")
        if not isinstance(self.observed_at, datetime) or self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")


class SemanticSimilarityProvider(Protocol):
    def score(self, left: str, right: str) -> float | None: ...


@dataclass(frozen=True)
class MemoryConflictAssessment:
    kind: MemoryConflictKind
    existing_memory_id: str
    reason_codes: tuple[str, ...]
    requires_review: bool
    persistence_performed: bool = False

    def __post_init__(self) -> None:
        if self.persistence_performed:
            raise ValueError("conflict assessment cannot mutate memory")


_CLAIM = re.compile(r"^([^:\n]{2,80}):\s*(\S.*)$")


def _normalize(value: str) -> str:
    return " ".join(value.casefold().split())


def _claim(value: str) -> tuple[str, str] | None:
    matched = _CLAIM.fullmatch(value.strip())
    if matched is None:
        return None
    return _normalize(matched.group(1)), _normalize(matched.group(2))


def compare_memory_candidate(
    candidate: MemoryCandidate,
    existing: MemoryConflictReference,
    *,
    similarity: SemanticSimilarityProvider | None = None,
    verified_new_fact: bool = False,
    candidate_observed_at: datetime | None = None,
) -> MemoryConflictAssessment:
    if candidate.tenant_id != existing.tenant_id or candidate.owner_id != existing.owner_id:
        raise PermissionError("cross-scope memory comparison denied")
    if not isinstance(verified_new_fact, bool):
        raise TypeError("verified_new_fact must be boolean")
    if candidate_observed_at is not None and (
        not isinstance(candidate_observed_at, datetime)
        or candidate_observed_at.tzinfo is None
        or candidate_observed_at.utcoffset() is None
    ):
        raise ValueError("candidate_observed_at must be timezone-aware")
    if candidate.domain is not existing.domain or existing.status is not MemoryLifecycle.ACTIVE:
        return MemoryConflictAssessment(MemoryConflictKind.UNKNOWN, existing.memory_id, ("INELIGIBLE_REFERENCE",), True)
    if _normalize(candidate.content) == _normalize(existing.content):
        return MemoryConflictAssessment(MemoryConflictKind.EXACT_DUPLICATE, existing.memory_id, ("NORMALIZED_TEXT_MATCH",), False)
    new_claim = _claim(candidate.content)
    old_claim = _claim(existing.content)
    if new_claim is not None and old_claim is not None and new_claim[0] == old_claim[0] and new_claim[1] != old_claim[1]:
        if verified_new_fact and candidate_observed_at is not None and candidate_observed_at > existing.observed_at:
            return MemoryConflictAssessment(MemoryConflictKind.POSSIBLE_SUPERSESSION, existing.memory_id, ("NEWER_VERIFIED_CONFLICTING_CLAIM",), True)
        return MemoryConflictAssessment(MemoryConflictKind.CONTRADICTION, existing.memory_id, ("CONFLICTING_CLAIM_VALUE",), True)
    if similarity is not None:
        score = similarity.score(candidate.content, existing.content)
        if score is not None:
            if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score) or not 0 <= score <= 1:
                raise ValueError("semantic similarity score must be finite between zero and one")
            if score >= 0.9:
                return MemoryConflictAssessment(MemoryConflictKind.NEAR_DUPLICATE, existing.memory_id, ("SEMANTIC_SIMILARITY_SIGNAL",), True)
    return MemoryConflictAssessment(MemoryConflictKind.UNKNOWN, existing.memory_id, ("RELATION_UNRESOLVED",), True)
