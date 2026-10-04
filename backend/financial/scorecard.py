"""Evidence-backed qualitative company intelligence without synthetic scores."""

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Mapping


class ScoreDimension(str, Enum):
    FUNDAMENTAL = "FUNDAMENTAL"
    GROWTH = "GROWTH"
    VALUATION = "VALUATION"
    QUALITY = "QUALITY"
    MOMENTUM = "MOMENTUM"
    RISK = "RISK"


class EvidenceGrade(str, Enum):
    UNKNOWN = "UNKNOWN"
    WEAK = "WEAK"
    MIXED = "MIXED"
    STRONG = "STRONG"


@dataclass(frozen=True)
class DimensionAssessment:
    grade: EvidenceGrade
    evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.grade, EvidenceGrade):
            raise TypeError("grade must be explicit")
        if self.grade is EvidenceGrade.UNKNOWN and self.evidence:
            raise ValueError("unknown assessment cannot claim evidence")
        if self.grade is not EvidenceGrade.UNKNOWN and not self.evidence:
            raise ValueError("assessment requires evidence")
        if any(not isinstance(item, str) or not item.strip() for item in self.evidence):
            raise ValueError("evidence references must be nonblank")


UNKNOWN_ASSESSMENT = DimensionAssessment(EvidenceGrade.UNKNOWN)


@dataclass(frozen=True)
class CompanyScorecard:
    asset_id: str
    fiscal_period: str
    assessments: Mapping[ScoreDimension, DimensionAssessment] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.asset_id.strip() or not self.fiscal_period.strip():
            raise ValueError("asset and period are required")
        if not isinstance(self.assessments, Mapping) or any(
            not isinstance(k, ScoreDimension) or not isinstance(v, DimensionAssessment)
            for k, v in self.assessments.items()
        ):
            raise ValueError("assessments require explicit dimensions and evidence")
        object.__setattr__(self, "assessments", MappingProxyType(dict(self.assessments)))

    def get(self, dimension: ScoreDimension) -> DimensionAssessment:
        return self.assessments.get(dimension, UNKNOWN_ASSESSMENT)
