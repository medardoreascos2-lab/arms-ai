"""Deterministic LOCAL_TEST_ONLY speech recognition fixtures."""

from __future__ import annotations

from .speech_input import SpeechTranscript


class SyntheticSpeechInputProvider:
    provider_id = "LOCAL_TEST_ONLY_SYNTHETIC_STT"

    def __init__(self, fixtures: dict[str, tuple[str, str]]) -> None:
        self._fixtures = dict(fixtures)

    def transcribe(self, content_reference: str, mime_type: str) -> SpeechTranscript:
        if mime_type not in self.supported_formats():
            raise ValueError("unsupported synthetic audio format")
        fixture = self._fixtures.get(content_reference)
        if fixture is None:
            raise LookupError("synthetic transcript fixture unavailable")
        text, language = fixture
        return SpeechTranscript(text=text, language=language, confidence=1.0, provider=self.provider_id, synthetic=True)

    def detect_language(self, content_reference: str) -> str | None:
        fixture = self._fixtures.get(content_reference)
        return None if fixture is None else fixture[1]

    def streaming_supported(self) -> bool:
        return False

    def supported_formats(self) -> frozenset[str]:
        return frozenset({"audio/wav", "audio/webm", "audio/ogg"})
