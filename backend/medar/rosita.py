"""Structured Rosita family knowledge domain contracts."""

from dataclasses import dataclass
from enum import Enum


class RositaContentCategory(str, Enum):
    FAMILY_EXPERIENCE = "family_experience"
    TRADITIONAL_PRACTICE = "traditional_practice"
    MEDICAL_SOURCE = "medical_source"
    AUDIO = "audio"
    VIDEO = "video"
    NOTES = "notes"
    TESTIMONY = "testimony"


@dataclass(frozen=True)
class RositaKnowledgeItem:
    item_id: str
    category: RositaContentCategory
    content: str
    source: str
    family_context: str | None = None

    def __post_init__(self) -> None:
        if not self.item_id.strip() or not self.content.strip() or not self.source.strip():
            raise ValueError("Rosita item identity, content, and source are required")
        if not isinstance(self.category, RositaContentCategory):
            raise TypeError("category must be RositaContentCategory")
