"""R88C MEDAR high-stakes escalation tests."""

import pytest

from backend.medar.high_stakes import HighStakesCategory, escalate_high_stakes


@pytest.mark.parametrize("category", tuple(HighStakesCategory))
def test_each_high_stakes_category_requires_professional_review(category):
    result = escalate_high_stakes(category, "Evidence-limited analysis")
    assert result.professional_review_required is True
    assert result.action_authorized is False
    assert "qualified professional" in result.caution


def test_unknown_category_fails_closed():
    with pytest.raises(TypeError, match="recognized"):
        escalate_high_stakes("MEDICAL", "analysis")
