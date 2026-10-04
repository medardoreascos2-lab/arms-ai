"""R93C Rosita health response boundary tests."""

import pytest

from backend.medar.agents import RositaKnowledgeAgent
from backend.medar.rosita import RositaContentCategory, RositaKnowledgeItem
from backend.medar.rosita_boundary import RositaHealthResponse, RositaOperation
from backend.medar.rosita_evidence import RositaEvidenceClass, RositaHealthItem


def _health_item():
    item = RositaKnowledgeItem(
        "item", RositaContentCategory.FAMILY_EXPERIENCE, "family account", "interview",
    )
    return RositaHealthItem(item, RositaEvidenceClass.PERSONAL_EXPERIENCE, 0.6)


def test_agent_may_retrieve_summarize_compare_and_preserve_without_validating_treatment():
    operations = tuple(RositaOperation)
    response = RositaKnowledgeAgent().respond_health((_health_item(),), "Family account", operations)
    assert response.operations == operations
    assert response.treatment_validated is False
    assert response.items[0].evidence_class is RositaEvidenceClass.PERSONAL_EXPERIENCE


def test_family_experience_cannot_be_promoted_to_validated_treatment():
    with pytest.raises(ValueError, match="cannot validate"):
        RositaHealthResponse(
            (_health_item(),), "Claimed treatment", (RositaOperation.SUMMARIZE,),
            treatment_validated=True,
        )
