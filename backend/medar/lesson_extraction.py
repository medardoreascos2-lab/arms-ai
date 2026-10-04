"""Structured lesson extraction from cited outcomes without hidden reasoning."""

from dataclasses import dataclass, field
from datetime import datetime

from backend.medar.memory_candidates import has_secret_like_content
from backend.medar.outcome_evaluator import OutcomeClassification, OutcomeEvaluation
from backend.medar.outcome_event import OutcomeEvent


@dataclass(frozen=True)
class LessonDraft:
    what_worked: str = field(repr=False)
    what_failed: str = field(repr=False)
    conditions: str = field(repr=False)
    future_recommendation: str = field(repr=False)

    def __post_init__(self) -> None:
        for name in ("what_worked", "what_failed", "conditions", "future_recommendation"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or len(value) > 512:
                raise ValueError(f"{name} must be concise bounded text")
            if has_secret_like_content(value):
                raise PermissionError("secret-like lesson content is not retained")


@dataclass(frozen=True)
class ExtractedLesson:
    lesson_id: str
    outcome_event_id: str
    classification: OutcomeClassification
    evidence_references: tuple[str, ...]
    what_worked: str = field(repr=False)
    what_failed: str = field(repr=False)
    conditions: str = field(repr=False)
    future_recommendation: str = field(repr=False)
    extracted_at: datetime
    hidden_chain_of_thought_included: bool = False
    learning_authority: bool = False

    def __post_init__(self) -> None:
        if self.hidden_chain_of_thought_included or self.learning_authority:
            raise ValueError("lessons cannot contain hidden reasoning or authorize learning")


def extract_lesson(
    event: OutcomeEvent,
    evaluation: OutcomeEvaluation,
    draft: LessonDraft,
    *,
    lesson_id: str,
    extracted_at: datetime,
) -> ExtractedLesson:
    if not isinstance(event, OutcomeEvent) or not isinstance(evaluation, OutcomeEvaluation) or not isinstance(draft, LessonDraft):
        raise TypeError("outcome event, evaluation, and explicit lesson draft are required")
    if evaluation.event_id != event.event_id:
        raise PermissionError("lesson evaluation does not match outcome event")
    if evaluation.classification is OutcomeClassification.UNKNOWN or not evaluation.evidence_sufficient:
        raise PermissionError("validated outcome evidence is required before lesson extraction")
    if not isinstance(lesson_id, str) or not lesson_id.strip() or len(lesson_id) > 240:
        raise ValueError("lesson ID must be bounded non-empty text")
    if not isinstance(extracted_at, datetime) or extracted_at.tzinfo is None or extracted_at.utcoffset() is None:
        raise ValueError("lesson extraction time must be timezone-aware")

    def normalized(value: str) -> str:
        return " ".join(value.split())

    return ExtractedLesson(
        lesson_id=lesson_id,
        outcome_event_id=event.event_id,
        classification=evaluation.classification,
        evidence_references=evaluation.evidence_references,
        what_worked=normalized(draft.what_worked),
        what_failed=normalized(draft.what_failed),
        conditions=normalized(draft.conditions),
        future_recommendation=normalized(draft.future_recommendation),
        extracted_at=extracted_at,
    )
