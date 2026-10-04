"""Explicit uncertainty classification for MEDAR outputs."""

from dataclasses import dataclass
from enum import Enum


class UncertaintyLevel(str, Enum):
    HIGH_CONFIDENCE = "HIGH_CONFIDENCE"
    MEDIUM_CONFIDENCE = "MEDIUM_CONFIDENCE"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


@dataclass(frozen=True)
class UncertaintyAssessment:
    level: UncertaintyLevel
    confidence: float
    evidence_count: int
    reasons: tuple[str, ...]


def assess_uncertainty(
    confidence: float,
    evidence_count: int,
    *,
    has_conflict: bool = False,
) -> UncertaintyAssessment:
    if not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must be between zero and one")
    if evidence_count < 0:
        raise ValueError("evidence_count cannot be negative")
    if evidence_count == 0:
        return UncertaintyAssessment(
            UncertaintyLevel.INSUFFICIENT_EVIDENCE, 0.0, 0, ("no usable evidence",),
        )
    if has_conflict:
        return UncertaintyAssessment(
            UncertaintyLevel.LOW_CONFIDENCE,
            min(confidence, 0.54),
            evidence_count,
            ("evidence conflict remains unresolved",),
        )
    if confidence >= 0.8:
        level = UncertaintyLevel.HIGH_CONFIDENCE
    elif confidence >= 0.55:
        level = UncertaintyLevel.MEDIUM_CONFIDENCE
    else:
        level = UncertaintyLevel.LOW_CONFIDENCE
    return UncertaintyAssessment(level, confidence, evidence_count, ())
