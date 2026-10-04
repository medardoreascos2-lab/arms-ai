"""R94C MEDAR decision journal contract tests."""

from datetime import datetime, timezone

import pytest

from backend.medar.decision_journal import DecisionJournalEntry


def _entry(**overrides):
    values = dict(
        entry_id="entry", decision="Choose a plan", options=("A", "B"),
        recommendation="A", chosen_option="A", expected_outcome="Lower risk",
        observed_outcome=None, recorded_at=datetime.now(timezone.utc),
    )
    values.update(overrides)
    return DecisionJournalEntry(**values)


def test_journal_captures_decision_recommendation_choice_and_outcomes():
    original = _entry()
    observed = original.with_observed_outcome("Risk decreased")
    assert original.observed_outcome is None
    assert observed.observed_outcome == "Risk decreased"
    assert observed.decision == original.decision
    assert observed.options == ("A", "B")


def test_chosen_option_must_be_recorded():
    with pytest.raises(ValueError, match="recorded options"):
        _entry(chosen_option="C")
