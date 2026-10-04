"""Deterministic, evidence-required MEDAR outcome classification."""

import math
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from backend.medar.outcome_event import OutcomeEvent


class OutcomeClassification(str, Enum):
    SUCCESS = "SUCCESS"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    FAILURE = "FAILURE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class OutcomeEvidence:
    event_id: str
    evidence_references: tuple[str, ...]
    metric_met: bool | None = None
    expectation_match_score: float | None = None
    error_verified: bool | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.event_id, str) or not self.event_id.strip():
            raise ValueError("outcome evidence event ID is required")
        if not isinstance(self.evidence_references, tuple) or len(self.evidence_references) > 20:
            raise ValueError("outcome evidence references must be bounded")
        for reference in self.evidence_references:
            if not isinstance(reference, str) or not reference.strip() or len(reference) > 240:
                raise ValueError("outcome evidence reference must be bounded text")
        for name in ("metric_met", "error_verified"):
            if getattr(self, name) is not None and not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be boolean or None")
        if self.expectation_match_score is not None and (
            isinstance(self.expectation_match_score, bool)
            or not isinstance(self.expectation_match_score, (int, float))
            or not math.isfinite(self.expectation_match_score)
            or not 0.0 <= self.expectation_match_score <= 1.0
        ):
            raise ValueError("expectation match score must be finite and between zero and one")


@dataclass(frozen=True)
class OutcomeEvaluation:
    event_id: str
    classification: OutcomeClassification
    evidence_references: tuple[str, ...]
    reason_codes: tuple[str, ...]
    evaluated_at: datetime
    evidence_sufficient: bool
    learning_authority: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.classification, OutcomeClassification):
            raise TypeError("outcome classification must be explicit")
        if not isinstance(self.evaluated_at, datetime) or self.evaluated_at.tzinfo is None or self.evaluated_at.utcoffset() is None:
            raise ValueError("evaluation time must be timezone-aware")
        if self.classification is OutcomeClassification.UNKNOWN and self.evidence_sufficient:
            raise ValueError("unknown evaluation cannot claim sufficient evidence")
        if self.classification is not OutcomeClassification.UNKNOWN and not self.evidence_sufficient:
            raise ValueError("classified outcome requires sufficient evidence")
        if self.learning_authority:
            raise ValueError("outcome evaluation cannot authorize learning")


def evaluate_outcome(
    event: OutcomeEvent,
    evidence: OutcomeEvidence,
    *,
    evaluated_at: datetime,
) -> OutcomeEvaluation:
    if not isinstance(event, OutcomeEvent) or not isinstance(evidence, OutcomeEvidence):
        raise TypeError("outcome event and evidence are required")
    if evidence.event_id != event.event_id:
        raise PermissionError("outcome evidence does not match event")
    if not isinstance(evaluated_at, datetime) or evaluated_at.tzinfo is None or evaluated_at.utcoffset() is None:
        raise ValueError("evaluation time must be timezone-aware")
    has_signal = any(
        value is not None
        for value in (evidence.metric_met, evidence.expectation_match_score, evidence.error_verified)
    )
    if not evidence.evidence_references or not has_signal:
        return OutcomeEvaluation(
            event.event_id, OutcomeClassification.UNKNOWN,
            evidence.evidence_references, ("EVIDENCE_REQUIRED",),
            evaluated_at, False,
        )
    if evidence.error_verified is True:
        classification = OutcomeClassification.FAILURE
        reasons = ("VERIFIED_ERROR",)
    elif evidence.metric_met is True and evidence.expectation_match_score is not None and evidence.expectation_match_score >= 0.8:
        classification = OutcomeClassification.SUCCESS
        reasons = ("METRIC_MET", "EXPECTED_RESULT_MATCHED")
    elif evidence.metric_met is False and (
        evidence.expectation_match_score is None or evidence.expectation_match_score <= 0.2
    ):
        classification = OutcomeClassification.FAILURE
        reasons = ("METRIC_NOT_MET", "EXPECTED_RESULT_NOT_OBSERVED")
    else:
        classification = OutcomeClassification.PARTIAL_SUCCESS
        reasons = ("MIXED_OUTCOME_EVIDENCE",)
    return OutcomeEvaluation(
        event.event_id, classification, evidence.evidence_references,
        reasons, evaluated_at, True,
    )
