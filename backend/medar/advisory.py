"""Boundaries for subjective business, marketing, career, and life advice."""

from dataclasses import dataclass
from enum import Enum

from backend.medar.decision_support import DecisionFramework


class AdvisoryTopic(str, Enum):
    BUSINESS = "BUSINESS"
    MARKETING = "MARKETING"
    CAREER = "CAREER"
    LIFE_DECISION = "LIFE_DECISION"


@dataclass(frozen=True)
class AdvisoryOutput:
    topic: AdvisoryTopic
    recommendation: str
    comparison: DecisionFramework
    confidence: float
    subjective_outcome: bool = True
    action_authorized: bool = False

    def __post_init__(self) -> None:
        if not self.recommendation.strip():
            raise ValueError("recommendation is required")
        if not self.subjective_outcome:
            raise ValueError("advisory outcomes must retain their subjective classification")
        if not 0.0 <= self.confidence < 1.0:
            raise ValueError("subjective advice cannot claim certainty")
        if self.action_authorized:
            raise ValueError("advisory output cannot authorize action")
