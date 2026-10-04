"""R93B Rosita medical evidence classification tests."""

import pytest

from backend.medar.rosita import RositaContentCategory, RositaKnowledgeItem
from backend.medar.rosita_evidence import RositaEvidenceClass, RositaHealthItem


def _item(category=RositaContentCategory.FAMILY_EXPERIENCE):
    return RositaKnowledgeItem("item", category, "health account", "source")


def test_rosita_health_evidence_labels_are_exact():
    assert tuple(item.value for item in RositaEvidenceClass) == (
        "PERSONAL_EXPERIENCE", "TRADITIONAL_PRACTICE", "CLINICAL_EVIDENCE", "UNKNOWN",
    )


def test_health_item_preserves_personal_experience_label():
    health = RositaHealthItem(_item(), RositaEvidenceClass.PERSONAL_EXPERIENCE, 0.6)
    assert health.evidence_class is RositaEvidenceClass.PERSONAL_EXPERIENCE


def test_clinical_label_requires_medical_source_category():
    with pytest.raises(ValueError, match="medical source"):
        RositaHealthItem(_item(), RositaEvidenceClass.CLINICAL_EVIDENCE, 0.9)
    health = RositaHealthItem(
        _item(RositaContentCategory.MEDICAL_SOURCE), RositaEvidenceClass.CLINICAL_EVIDENCE, 0.9,
    )
    assert health.evidence_class is RositaEvidenceClass.CLINICAL_EVIDENCE
