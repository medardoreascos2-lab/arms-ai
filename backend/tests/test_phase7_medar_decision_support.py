"""R88A MEDAR general decision framework tests."""

import pytest

from backend.medar.decision_support import DecisionFramework, DecisionOption, Reversibility
from backend.medar.uncertainty import assess_uncertainty


def _option(option_id="a"):
    return DecisionOption(
        option_id, "Option A", ("benefit",), ("risk",), ("cost versus speed",),
        Reversibility.REVERSIBLE, assess_uncertainty(0.7, 2),
    )


def test_decision_framework_preserves_all_required_dimensions():
    framework = DecisionFramework("decision-1", ("grow safely",), ("budget",), (_option(),))
    option = framework.options[0]
    assert framework.goals == ("grow safely",)
    assert framework.constraints == ("budget",)
    assert option.benefits == ("benefit",)
    assert option.risks == ("risk",)
    assert option.tradeoffs == ("cost versus speed",)
    assert option.reversibility is Reversibility.REVERSIBLE
    assert framework.advisory_only is True


def test_framework_cannot_claim_decision_authority():
    with pytest.raises(ValueError, match="advisory"):
        DecisionFramework("decision", ("goal",), (), (_option(),), advisory_only=False)


def test_duplicate_options_fail_closed():
    with pytest.raises(ValueError, match="unique"):
        DecisionFramework("decision", ("goal",), (), (_option(), _option()))
