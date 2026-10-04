"""R114B deterministic outcome evaluation requires cited evidence."""

from datetime import datetime, timezone

import pytest

from backend.medar.outcome_evaluator import (
    OutcomeClassification, OutcomeEvidence, evaluate_outcome,
)
from backend.medar.outcome_event import OutcomeEvent


NOW = datetime(2026, 10, 4, 12, tzinfo=timezone.utc)
EVENT = OutcomeEvent(
    "outcome-1", "tenant-a", "owner-a", "session-a",
    "synthetic-test:task-1", "run synthetic validation",
    "use bounded validation", "all checks pass", "green result",
    "green result", "all assertions pass", None, NOW,
)


@pytest.mark.parametrize(("evidence", "classification"), [
    (OutcomeEvidence("outcome-1", ("synthetic-test:e1",), True, 1.0, False), OutcomeClassification.SUCCESS),
    (OutcomeEvidence("outcome-1", ("synthetic-test:e2",), True, 0.5, False), OutcomeClassification.PARTIAL_SUCCESS),
    (OutcomeEvidence("outcome-1", ("synthetic-test:e3",), False, 0.0, False), OutcomeClassification.FAILURE),
    (OutcomeEvidence("outcome-1", ("synthetic-test:e4",), True, 1.0, True), OutcomeClassification.FAILURE),
    (OutcomeEvidence("outcome-1", (), True, 1.0, False), OutcomeClassification.UNKNOWN),
    (OutcomeEvidence("outcome-1", ("synthetic-test:e5",)), OutcomeClassification.UNKNOWN),
])
def test_outcome_evaluator_classifies_only_from_explicit_evidence(evidence, classification):
    result = evaluate_outcome(EVENT, evidence, evaluated_at=NOW)
    assert result.classification is classification
    assert result.evidence_sufficient is (classification is not OutcomeClassification.UNKNOWN)
    assert not result.learning_authority


def test_outcome_evaluator_rejects_cross_event_evidence_and_bad_time():
    with pytest.raises(PermissionError):
        evaluate_outcome(
            EVENT, OutcomeEvidence("other", ("synthetic-test:e1",), True, 1.0),
            evaluated_at=NOW,
        )
    with pytest.raises(ValueError):
        evaluate_outcome(
            EVENT, OutcomeEvidence("outcome-1", ("synthetic-test:e1",), True, 1.0),
            evaluated_at=datetime(2026, 10, 4),
        )


@pytest.mark.parametrize("score", [float("nan"), float("inf"), -0.1, 1.1])
def test_outcome_evidence_rejects_invalid_scores(score):
    with pytest.raises(ValueError):
        OutcomeEvidence("outcome-1", ("synthetic-test:e1",), True, score)
