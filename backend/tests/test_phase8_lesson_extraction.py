"""R114C lesson extraction is explicit, cited, concise, and reasoning-safe."""

from datetime import datetime, timezone

import pytest

from backend.medar.lesson_extraction import LessonDraft, extract_lesson
from backend.medar.outcome_evaluator import OutcomeEvidence, evaluate_outcome
from backend.medar.outcome_event import OutcomeEvent


NOW = datetime(2026, 10, 4, 12, tzinfo=timezone.utc)
EVENT = OutcomeEvent(
    "outcome-1", "tenant-a", "owner-a", "session-a",
    "synthetic-test:task-1", "run synthetic validation",
    "use bounded validation", "all checks pass", "green result",
    "green result", "all assertions pass", None, NOW,
)
EVALUATION = evaluate_outcome(
    EVENT,
    OutcomeEvidence("outcome-1", ("synthetic-test:evidence-1",), True, 1.0, False),
    evaluated_at=NOW,
)


def test_lesson_extracts_only_explicit_structured_summary_with_citations():
    draft = LessonDraft(
        "  bounded checks   worked ", "no observed failure",
        "synthetic local validation", "repeat bounded checks",
    )
    lesson = extract_lesson(
        EVENT, EVALUATION, draft, lesson_id="lesson-1", extracted_at=NOW,
    )
    assert lesson.what_worked == "bounded checks worked"
    assert lesson.what_failed == "no observed failure"
    assert lesson.conditions == "synthetic local validation"
    assert lesson.future_recommendation == "repeat bounded checks"
    assert lesson.evidence_references == ("synthetic-test:evidence-1",)
    assert (lesson.tenant_id, lesson.owner_id, lesson.session_id) == (
        "tenant-a", "owner-a", "session-a",
    )
    assert lesson.source_reference == "synthetic-test:task-1"
    assert not lesson.hidden_chain_of_thought_included
    assert not lesson.learning_authority
    assert lesson.what_worked not in repr(lesson)


def test_unknown_or_cross_event_evaluation_cannot_create_lesson():
    draft = LessonDraft("worked", "failed", "conditions", "recommendation")
    unknown = evaluate_outcome(
        EVENT, OutcomeEvidence("outcome-1", ()), evaluated_at=NOW,
    )
    with pytest.raises(PermissionError):
        extract_lesson(EVENT, unknown, draft, lesson_id="lesson-1", extracted_at=NOW)
    other_event = OutcomeEvent(
        "other", "tenant-a", "owner-a", "session-a",
        "synthetic-test:task-2", "task", "decision", "prediction",
        "expected", "observed", "metric", None, NOW,
    )
    with pytest.raises(PermissionError):
        extract_lesson(other_event, EVALUATION, draft, lesson_id="lesson-1", extracted_at=NOW)


def test_lesson_draft_rejects_secret_like_or_unbounded_content():
    with pytest.raises(PermissionError):
        LessonDraft("worked", "failed", "conditions", "api_key: synthetic")
    with pytest.raises(ValueError):
        LessonDraft("x" * 513, "failed", "conditions", "recommendation")


def test_secret_like_evidence_reference_cannot_enter_extracted_lesson():
    evaluation = evaluate_outcome(
        EVENT,
        OutcomeEvidence("outcome-1", ("api_key: synthetic",), True, 1.0, False),
        evaluated_at=NOW,
    )
    with pytest.raises(PermissionError):
        extract_lesson(
            EVENT, evaluation, LessonDraft("worked", "failed", "conditions", "recommendation"),
            lesson_id="lesson-1", extracted_at=NOW,
        )
