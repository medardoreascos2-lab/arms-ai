"""Explicit evidence classification for Rosita health knowledge."""

from dataclasses import dataclass
from enum import Enum

from backend.medar.rosita import RositaContentCategory, RositaKnowledgeItem


class RositaEvidenceClass(str, Enum):
    PERSONAL_EXPERIENCE = "PERSONAL_EXPERIENCE"
    TRADITIONAL_PRACTICE = "TRADITIONAL_PRACTICE"
    CLINICAL_EVIDENCE = "CLINICAL_EVIDENCE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class RositaHealthItem:
    item: RositaKnowledgeItem
    evidence_class: RositaEvidenceClass
    confidence: float

    def __post_init__(self) -> None:
        if not isinstance(self.evidence_class, RositaEvidenceClass):
            raise TypeError("every health item requires an evidence classification")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between zero and one")
        if (
            self.evidence_class is RositaEvidenceClass.CLINICAL_EVIDENCE
            and self.item.category is not RositaContentCategory.MEDICAL_SOURCE
        ):
            raise ValueError("clinical evidence must originate from a medical source")
