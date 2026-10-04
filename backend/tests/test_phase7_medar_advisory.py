"""R88B MEDAR advisory boundary tests."""

import pytest

from backend.medar.advisory import AdvisoryOutput, AdvisoryTopic
from backend.medar.decision_support import DecisionFramework, DecisionOption, Reversibility
from backend.medar.uncertainty import assess_uncertainty


def _framework():
    option = DecisionOption(
        "a", "Option", ("benefit",), ("risk",), ("tradeoff",),
        Reversibility.REVERSIBLE, assess_uncertainty(0.7, 1),
    )
    return DecisionFramework("d", ("goal",), (), (option,))


def test_supported_advisory_topics_are_explicit_and_advisory_only():
    assert tuple(item.value for item in AdvisoryTopic) == (
        "BUSINESS", "MARKETING", "CAREER", "LIFE_DECISION",
    )
    output = AdvisoryOutput(AdvisoryTopic.BUSINESS, "Consider option A", _framework(), 0.7)
    assert output.subjective_outcome is True
    assert output.action_authorized is False


def test_subjective_advice_cannot_claim_certainty_or_authorize_action():
    with pytest.raises(ValueError, match="certainty"):
        AdvisoryOutput(AdvisoryTopic.LIFE_DECISION, "Choose A", _framework(), 1.0)
    with pytest.raises(ValueError, match="authorize"):
        AdvisoryOutput(AdvisoryTopic.CAREER, "Choose A", _framework(), 0.6, action_authorized=True)
