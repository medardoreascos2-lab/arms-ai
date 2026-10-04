"""F101B: scorecard preserves unknown dimensions and source evidence."""

import pytest

from backend.financial.scorecard import (
    CompanyScorecard, DimensionAssessment, EvidenceGrade, ScoreDimension,
)


def test_scorecard_uses_qualitative_evidence_without_fabricated_number():
    scorecard = CompanyScorecard(
        "NASDAQ:TEST", "2026-Q2",
        {ScoreDimension.GROWTH: DimensionAssessment(EvidenceGrade.STRONG, ("synthetic:filing#revenue",))},
    )
    assert scorecard.get(ScoreDimension.GROWTH).grade is EvidenceGrade.STRONG
    assert scorecard.get(ScoreDimension.RISK).grade is EvidenceGrade.UNKNOWN
    assert not hasattr(scorecard, "total_score")
    with pytest.raises(TypeError):
        scorecard.assessments[ScoreDimension.RISK] = DimensionAssessment(EvidenceGrade.UNKNOWN)


def test_assessment_requires_evidence_and_unknown_cannot_claim_it():
    with pytest.raises(ValueError, match="requires evidence"):
        DimensionAssessment(EvidenceGrade.STRONG)
    with pytest.raises(ValueError, match="cannot claim evidence"):
        DimensionAssessment(EvidenceGrade.UNKNOWN, ("source",))
