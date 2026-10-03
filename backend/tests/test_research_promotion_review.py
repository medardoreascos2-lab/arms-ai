from datetime import datetime, timezone
from pathlib import Path

import pytest

from backend.research.promotion_review import (
    PromotionEvidenceKind,
    PromotionReviewSection,
    PromotionReviewStatus,
    ProductionPromotionReviewBuilder,
    REQUIRED_PROMOTION_EVIDENCE,
)


NOW = datetime(2026, 10, 3, 15, tzinfo=timezone.utc)


def section(kind: PromotionEvidenceKind, passed: bool = True) -> PromotionReviewSection:
    return PromotionReviewSection(kind, passed, (f"evidence-{kind.value.lower()}",), ("a" * 64,), () if passed else ("GATE_FAILED",))


def build(sections: tuple[PromotionReviewSection, ...]):
    return ProductionPromotionReviewBuilder().build(
        review_id="review-1", candidate_id="candidate-1", candidate_revision=3,
        candidate_record_hash="b" * 64, sections=sections, generated_at=NOW,
    )


def test_complete_passing_evidence_is_ready_only_for_human_review() -> None:
    report = build(tuple(section(kind) for kind in REQUIRED_PROMOTION_EVIDENCE))
    assert report.status is PromotionReviewStatus.READY_FOR_HUMAN_REVIEW
    assert report.missing_evidence == ()
    assert report.human_decision_required is True
    assert report.auto_promotion_authorized is False
    assert report.production_mutation_authorized is False
    assert report.execution_authorized is False


def test_missing_evidence_is_not_ready_and_named() -> None:
    report = build((section(PromotionEvidenceKind.CANDIDATE),))
    assert report.status is PromotionReviewStatus.NOT_READY
    assert set(report.missing_evidence) == set(REQUIRED_PROMOTION_EVIDENCE) - {PromotionEvidenceKind.CANDIDATE}


def test_failed_complete_evidence_requires_more_research() -> None:
    sections = tuple(section(kind, passed=kind is not PromotionEvidenceKind.STRESS) for kind in REQUIRED_PROMOTION_EVIDENCE)
    report = build(sections)
    assert report.status is PromotionReviewStatus.RESEARCH_CONTINUE
    assert report.missing_evidence == ()


def test_all_required_review_outputs_are_explicit() -> None:
    assert {item.value for item in REQUIRED_PROMOTION_EVIDENCE} == {
        "CANDIDATE", "BACKTESTS", "WALK_FORWARD", "OUT_OF_SAMPLE", "STRESS",
        "PAPER_CHALLENGER", "RISK_COMPARISON", "PARAMETER_STABILITY",
    }
    assert {item.value for item in PromotionReviewStatus} == {
        "NOT_READY", "RESEARCH_CONTINUE", "READY_FOR_HUMAN_REVIEW",
    }


def test_source_hashes_are_deduplicated_and_reconciled() -> None:
    report = build(tuple(section(kind) for kind in REQUIRED_PROMOTION_EVIDENCE))
    assert report.source_hashes == ("a" * 64,)
    assert len(report.review_hash) == 64


def test_failed_section_requires_reason_and_passed_section_forbids_it() -> None:
    with pytest.raises(ValueError, match="requires blocking"):
        PromotionReviewSection(PromotionEvidenceKind.STRESS, False, ("e",), ("a" * 64,), ())
    with pytest.raises(ValueError, match="cannot have"):
        PromotionReviewSection(PromotionEvidenceKind.STRESS, True, ("e",), ("a" * 64,), ("FAILED",))


def test_duplicate_section_kinds_are_rejected() -> None:
    duplicate = section(PromotionEvidenceKind.CANDIDATE)
    with pytest.raises(ValueError, match="unique kinds"):
        build((duplicate, duplicate))


def test_naive_generation_time_is_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        ProductionPromotionReviewBuilder().build(
            review_id="review", candidate_id="candidate", candidate_revision=1,
            candidate_record_hash="b" * 64, sections=(), generated_at=datetime(2026, 10, 3),
        )


def test_review_is_deterministic_regardless_of_input_order() -> None:
    sections = tuple(section(kind) for kind in REQUIRED_PROMOTION_EVIDENCE)
    assert build(sections).document() == build(tuple(reversed(sections))).document()


def test_module_contains_no_auto_promotion_or_execution_calls() -> None:
    text = (Path(__file__).parents[1] / "research" / "promotion_review.py").read_text(encoding="utf-8")
    assert "AUTO_PROMOTED" not in text
    assert "submit_order" not in text
    assert "promote_candidate(" not in text
