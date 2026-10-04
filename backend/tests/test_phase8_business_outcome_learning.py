"""R121E validates business outcome learning without action or spend authority."""

from datetime import datetime, timezone
from decimal import Decimal

from backend.medar.business_memory import BusinessMemory
from backend.medar.lesson_extraction import LessonDraft, extract_lesson
from backend.medar.marketing_memory import MarketingMemory
from backend.medar.outcome_evaluator import OutcomeClassification, OutcomeEvidence, evaluate_outcome
from backend.medar.outcome_event import OutcomeEvent

NOW = datetime(2026, 10, 4, 22, tzinfo=timezone.utc)


def test_business_and_marketing_outcomes_create_cited_advisory_lesson_only():
    business = BusinessMemory(
        "tenant-a", "owner-a", "session-a", "synthetic-company", "synthetic-report:business-1",
        "synthetic-dataset:kpis-1", "improve retention", "retention", Decimal("0.81"), "fraction",
        "test onboarding message", "keep test isolated", "retention target met in synthetic data", NOW,
    )
    marketing = MarketingMemory(
        "tenant-a", "owner-a", "session-a", "synthetic-campaign", "synthetic-report:campaign-1",
        "synthetic-dataset:campaign-1", "synthetic audience", "synthetic creative", "local-test",
        Decimal("0.00"), "USD", "synthetic target met", "retain bounded test", NOW,
    )
    event = OutcomeEvent(
        "business-outcome-1", "tenant-a", "owner-a", "session-a", business.source_reference,
        business.goal, business.decision, "retention reaches 0.80", "0.80", str(business.kpi_value),
        business.kpi_name, None, NOW,
    )
    evaluation = evaluate_outcome(
        event,
        OutcomeEvidence(event.event_id, (business.dataset_reference, marketing.dataset_reference), True, 1.0, False),
        evaluated_at=NOW,
    )
    lesson = extract_lesson(
        event, evaluation,
        LessonDraft("bounded onboarding test met target", "no observed failure", "synthetic datasets only", "repeat only after human review"),
        lesson_id="business-lesson-1", extracted_at=NOW,
    )

    assert evaluation.classification is OutcomeClassification.SUCCESS
    assert lesson.evidence_references == (business.dataset_reference, marketing.dataset_reference)
    assert lesson.future_recommendation == "repeat only after human review"
    assert not any((
        business.business_action_authority, business.trading_authority,
        marketing.ad_spend_authority, marketing.campaign_mutation_authority,
        evaluation.learning_authority, lesson.learning_authority,
    ))
    assert business.session_only and marketing.session_only
    assert not lesson.hidden_chain_of_thought_included
