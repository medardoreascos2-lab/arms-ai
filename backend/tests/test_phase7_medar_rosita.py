"""R93A Rosita knowledge domain model tests."""

import pytest

from backend.medar.rosita import RositaContentCategory, RositaKnowledgeItem


def test_rosita_content_categories_match_roadmap():
    assert tuple(item.value for item in RositaContentCategory) == (
        "family_experience", "traditional_practice", "medical_source", "audio",
        "video", "notes", "testimony",
    )


def test_rosita_item_preserves_category_source_and_family_context():
    item = RositaKnowledgeItem(
        "item-1", RositaContentCategory.FAMILY_EXPERIENCE,
        "A family account", "interview-1", "maternal family",
    )
    assert item.category is RositaContentCategory.FAMILY_EXPERIENCE
    assert item.source == "interview-1"
    assert item.family_context == "maternal family"


def test_untyped_category_is_rejected():
    with pytest.raises(TypeError, match="category"):
        RositaKnowledgeItem("item", "notes", "content", "source")
