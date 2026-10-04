"""Provider-neutral speech input contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class SpeechTranscript:
    text: str
    language: str
    confidence: float | None
    provider: str
    synthetic: bool


class SpeechInputProvider(Protocol):
    provider_id: str

    def transcribe(self, content_reference: str, mime_type: str) -> SpeechTranscript: ...
    def detect_language(self, content_reference: str) -> str | None: ...
    def streaming_supported(self) -> bool: ...
    def supported_formats(self) -> frozenset[str]: ...
