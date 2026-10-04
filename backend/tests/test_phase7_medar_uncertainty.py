"""R87C MEDAR uncertainty model tests."""

from backend.medar.uncertainty import UncertaintyLevel, assess_uncertainty


def test_uncertainty_levels_match_contract_and_thresholds():
    assert tuple(item.value for item in UncertaintyLevel) == (
        "HIGH_CONFIDENCE", "MEDIUM_CONFIDENCE", "LOW_CONFIDENCE", "INSUFFICIENT_EVIDENCE",
    )
    assert assess_uncertainty(0.8, 2).level is UncertaintyLevel.HIGH_CONFIDENCE
    assert assess_uncertainty(0.55, 1).level is UncertaintyLevel.MEDIUM_CONFIDENCE
    assert assess_uncertainty(0.54, 1).level is UncertaintyLevel.LOW_CONFIDENCE


def test_zero_evidence_overrides_claimed_confidence():
    assessment = assess_uncertainty(0.99, 0)
    assert assessment.level is UncertaintyLevel.INSUFFICIENT_EVIDENCE
    assert assessment.confidence == 0.0


def test_unresolved_conflict_caps_confidence_and_reports_reason():
    assessment = assess_uncertainty(0.95, 3, has_conflict=True)
    assert assessment.level is UncertaintyLevel.LOW_CONFIDENCE
    assert assessment.confidence == 0.54
    assert assessment.reasons
