"""Fail-closed escalation contract for high-stakes MEDAR advice."""

from dataclasses import dataclass
from enum import Enum


class HighStakesCategory(str, Enum):
    MEDICAL = "MEDICAL"
    LEGAL = "LEGAL"
    HIGH_RISK_FINANCIAL = "HIGH_RISK_FINANCIAL"
    PERSONAL_SAFETY = "PERSONAL_SAFETY"


@dataclass(frozen=True)
class HighStakesAssessment:
    category: HighStakesCategory
    analysis: str
    caution: str
    professional_review_required: bool = True
    action_authorized: bool = False

    def __post_init__(self) -> None:
        if not self.analysis.strip() or not self.caution.strip():
            raise ValueError("high-stakes analysis and caution are required")
        if not self.professional_review_required:
            raise ValueError("high-stakes output requires professional review")
        if self.action_authorized:
            raise ValueError("high-stakes analysis cannot authorize action")


def escalate_high_stakes(
    category: HighStakesCategory,
    analysis: str,
) -> HighStakesAssessment:
    if not isinstance(category, HighStakesCategory):
        raise TypeError("a recognized high-stakes category is required")
    return HighStakesAssessment(
        category,
        analysis,
        "Treat this as general analysis and obtain review from a qualified professional.",
    )
