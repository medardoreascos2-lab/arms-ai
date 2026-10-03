"""Read-only production promotion review package for human decision making."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import re


_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_HASH = re.compile(r"^[0-9a-f]{64}$")


class PromotionReviewStatus(str, Enum):
    NOT_READY = "NOT_READY"
    RESEARCH_CONTINUE = "RESEARCH_CONTINUE"
    READY_FOR_HUMAN_REVIEW = "READY_FOR_HUMAN_REVIEW"


class PromotionEvidenceKind(str, Enum):
    CANDIDATE = "CANDIDATE"
    BACKTESTS = "BACKTESTS"
    WALK_FORWARD = "WALK_FORWARD"
    OUT_OF_SAMPLE = "OUT_OF_SAMPLE"
    STRESS = "STRESS"
    PAPER_CHALLENGER = "PAPER_CHALLENGER"
    RISK_COMPARISON = "RISK_COMPARISON"
    PARAMETER_STABILITY = "PARAMETER_STABILITY"


REQUIRED_PROMOTION_EVIDENCE = tuple(PromotionEvidenceKind)


def _id(value: object, name: str) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise ValueError(f"{name} is invalid")
    return value


def _hash_value(value: object, name: str) -> str:
    if not isinstance(value, str) or _HASH.fullmatch(value) is None:
        raise ValueError(f"{name} must be lowercase SHA-256")
    return value


def _utc(value: datetime, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class PromotionReviewSection:
    kind: PromotionEvidenceKind
    passed: bool
    evidence_ids: tuple[str, ...]
    source_hashes: tuple[str, ...]
    blocking_reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.kind, PromotionEvidenceKind) or type(self.passed) is not bool:
            raise ValueError("kind and passed are invalid")
        evidence = tuple(sorted(_id(item, "evidence_id") for item in self.evidence_ids))
        hashes = tuple(sorted(_hash_value(item, "source_hash") for item in self.source_hashes))
        reasons = tuple(sorted(_id(item, "blocking_reason") for item in self.blocking_reasons))
        if not evidence or not hashes or evidence != self.evidence_ids or hashes != self.source_hashes:
            raise ValueError("evidence_ids and source_hashes must be nonempty, sorted, and unique")
        if len(set(evidence)) != len(evidence) or len(set(hashes)) != len(hashes) or len(set(reasons)) != len(reasons):
            raise ValueError("review section values must be unique")
        if reasons != self.blocking_reasons:
            raise ValueError("blocking_reasons must be sorted")
        if self.passed and reasons:
            raise ValueError("passed section cannot have blocking reasons")
        if not self.passed and not reasons:
            raise ValueError("failed section requires blocking reasons")

    def document(self) -> dict[str, object]:
        return {"blocking_reasons": list(self.blocking_reasons), "evidence_ids": list(self.evidence_ids),
                "kind": self.kind.value, "passed": self.passed, "source_hashes": list(self.source_hashes)}


@dataclass(frozen=True)
class ProductionPromotionReview:
    review_id: str
    candidate_id: str
    candidate_revision: int
    candidate_record_hash: str
    generated_at: datetime
    status: PromotionReviewStatus
    sections: tuple[PromotionReviewSection, ...]
    missing_evidence: tuple[PromotionEvidenceKind, ...]
    source_hashes: tuple[str, ...]
    review_hash: str = field(init=False)
    human_decision_required: bool = field(default=True, init=False)
    auto_promotion_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)
    execution_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "review_id", _id(self.review_id, "review_id"))
        object.__setattr__(self, "candidate_id", _id(self.candidate_id, "candidate_id"))
        if type(self.candidate_revision) is not int or self.candidate_revision < 0:
            raise ValueError("candidate_revision must be nonnegative")
        object.__setattr__(self, "candidate_record_hash", _hash_value(self.candidate_record_hash, "candidate_record_hash"))
        object.__setattr__(self, "generated_at", _utc(self.generated_at, "generated_at"))
        if not isinstance(self.status, PromotionReviewStatus):
            raise ValueError("status is invalid")
        kinds = tuple(item.kind for item in self.sections)
        if kinds != tuple(sorted(kinds, key=lambda item: item.value)) or len(set(kinds)) != len(kinds):
            raise ValueError("sections must be sorted with unique kinds")
        expected_missing = tuple(sorted(set(REQUIRED_PROMOTION_EVIDENCE) - set(kinds), key=lambda item: item.value))
        if self.missing_evidence != expected_missing:
            raise ValueError("missing_evidence does not reconcile")
        expected_hashes = tuple(sorted({value for item in self.sections for value in item.source_hashes}))
        if self.source_hashes != expected_hashes:
            raise ValueError("source_hashes do not reconcile")
        expected_status = (PromotionReviewStatus.NOT_READY if expected_missing else
                           PromotionReviewStatus.RESEARCH_CONTINUE if any(not item.passed for item in self.sections) else
                           PromotionReviewStatus.READY_FOR_HUMAN_REVIEW)
        if self.status is not expected_status:
            raise ValueError("status does not reconcile with evidence")
        object.__setattr__(self, "review_hash", _digest(self.document(include_hash=False)))

    def document(self, *, include_hash: bool = True) -> dict[str, object]:
        value = {"auto_promotion_authorized": self.auto_promotion_authorized, "candidate_id": self.candidate_id,
                 "candidate_record_hash": self.candidate_record_hash, "candidate_revision": self.candidate_revision,
                 "execution_authorized": self.execution_authorized, "generated_at": self.generated_at.isoformat(),
                 "human_decision_required": self.human_decision_required, "missing_evidence": [item.value for item in self.missing_evidence],
                 "production_mutation_authorized": self.production_mutation_authorized, "review_id": self.review_id,
                 "sections": [item.document() for item in self.sections], "source_hashes": list(self.source_hashes), "status": self.status.value}
        if include_hash:
            value["review_hash"] = self.review_hash
        return value


class ProductionPromotionReviewBuilder:
    def build(self, *, review_id: str, candidate_id: str, candidate_revision: int,
              candidate_record_hash: str, sections: tuple[PromotionReviewSection, ...],
              generated_at: datetime) -> ProductionPromotionReview:
        if not isinstance(sections, tuple):
            raise ValueError("sections must be a tuple")
        ordered = tuple(sorted(sections, key=lambda item: item.kind.value))
        kinds = {item.kind for item in ordered}
        missing = tuple(sorted(set(REQUIRED_PROMOTION_EVIDENCE) - kinds, key=lambda item: item.value))
        status = (PromotionReviewStatus.NOT_READY if missing else
                  PromotionReviewStatus.RESEARCH_CONTINUE if any(not item.passed for item in ordered) else
                  PromotionReviewStatus.READY_FOR_HUMAN_REVIEW)
        hashes = tuple(sorted({value for item in ordered for value in item.source_hashes}))
        return ProductionPromotionReview(review_id, candidate_id, candidate_revision, candidate_record_hash,
                                         generated_at, status, ordered, missing, hashes)
