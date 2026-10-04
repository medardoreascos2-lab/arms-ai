"""Deterministic LOCAL_TEST_ONLY vision fixtures; no actual image analysis."""

from .vision_provider import VisionObservation


class SyntheticVisionProvider:
    provider_id="LOCAL_TEST_ONLY_SYNTHETIC_VISION"
    def __init__(self,fixtures: dict[tuple[str,str],VisionObservation]) -> None: self._fixtures=dict(fixtures)
    def _get(self,reference: str,operation: str) -> VisionObservation:
        value=self._fixtures.get((reference,operation))
        if value is None: raise LookupError("synthetic vision fixture unavailable")
        if not value.synthetic or value.provider != self.provider_id: raise ValueError("fixture must be explicitly synthetic")
        return value
    def describe_image(self,content_reference: str)->VisionObservation: return self._get(content_reference,"DESCRIBE")
    def extract_visible_text(self,content_reference: str)->VisionObservation: return self._get(content_reference,"OCR")
    def identify_objects(self,content_reference: str)->VisionObservation: return self._get(content_reference,"OBJECTS")
    def analyze_document_page(self,content_reference: str,page_number: int)->VisionObservation:
        if page_number<1: raise ValueError("page number must be positive")
        return self._get(f"{content_reference}#page={page_number}","DOCUMENT_PAGE")
