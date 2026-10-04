"""General, advisory-only decision support structures."""

from dataclasses import dataclass
from enum import Enum

from backend.medar.uncertainty import UncertaintyAssessment


class Reversibility(str, Enum):
    REVERSIBLE = "REVERSIBLE"
    PARTIALLY_REVERSIBLE = "PARTIALLY_REVERSIBLE"
    IRREVERSIBLE = "IRREVERSIBLE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class DecisionOption:
    option_id: str
    title: str
    benefits: tuple[str, ...]
    risks: tuple[str, ...]
    tradeoffs: tuple[str, ...]
    reversibility: Reversibility
    uncertainty: UncertaintyAssessment

    def __post_init__(self) -> None:
        if not self.option_id.strip() or not self.title.strip():
            raise ValueError("option identity and title are required")
        if not isinstance(self.reversibility, Reversibility):
            raise TypeError("reversibility must be typed")
        if not isinstance(self.uncertainty, UncertaintyAssessment):
            raise TypeError("uncertainty assessment is required")


@dataclass(frozen=True)
class DecisionFramework:
    decision_id: str
    goals: tuple[str, ...]
    constraints: tuple[str, ...]
    options: tuple[DecisionOption, ...]
    advisory_only: bool = True

    def __post_init__(self) -> None:
        if not self.decision_id.strip() or not self.goals or not self.options:
            raise ValueError("decision identity, goals, and options are required")
        if not self.advisory_only:
            raise ValueError("Phase 7 decision support must remain advisory")
        option_ids = tuple(item.option_id for item in self.options)
        if len(option_ids) != len(set(option_ids)):
            raise ValueError("decision option ids must be unique")
