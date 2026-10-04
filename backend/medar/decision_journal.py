"""Immutable decision journal contract for future Phase 8 learning."""

from dataclasses import dataclass, replace
from datetime import datetime


@dataclass(frozen=True)
class DecisionJournalEntry:
    entry_id: str
    decision: str
    options: tuple[str, ...]
    recommendation: str
    chosen_option: str | None
    expected_outcome: str
    observed_outcome: str | None
    recorded_at: datetime

    def __post_init__(self) -> None:
        if not self.entry_id.strip() or not self.decision.strip() or not self.options:
            raise ValueError("journal entry identity, decision, and options are required")
        if not self.recommendation.strip() or not self.expected_outcome.strip():
            raise ValueError("recommendation and expected outcome are required")
        if self.chosen_option is not None and self.chosen_option not in self.options:
            raise ValueError("chosen option must be one of the recorded options")
        if self.recorded_at.tzinfo is None or self.recorded_at.utcoffset() is None:
            raise ValueError("recorded_at must be timezone-aware")

    def with_observed_outcome(self, outcome: str) -> "DecisionJournalEntry":
        if not outcome.strip():
            raise ValueError("observed outcome must be non-empty")
        return replace(self, observed_outcome=outcome)
