"""Provider-neutral visual observation contract; no model capability is assumed."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class VisionObservation:
    content_reference: str
    operation: str
    observations: tuple[str,...]
    visible_text: tuple[str,...]
    confidence: float | None
    provider: str
    synthetic: bool
    limitations: tuple[str,...]=()


class VisionProvider(Protocol):
    provider_id: str
    def describe_image(self,content_reference: str) -> VisionObservation: ...
    def extract_visible_text(self,content_reference: str) -> VisionObservation: ...
    def identify_objects(self,content_reference: str) -> VisionObservation: ...
    def analyze_document_page(self,content_reference: str,page_number: int) -> VisionObservation: ...
