"""Provider-neutral speech output contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class VoiceDescriptor:
    voice_id: str
    language: str
    display_name: str
    synthetic_only: bool


@dataclass(frozen=True)
class SpeechOutput:
    audio_reference: str
    status: str
    provider: str
    language: str
    duration_seconds: float | None


class SpeechOutputProvider(Protocol):
    provider_id: str
    def synthesize(self, text: str, voice_id: str, language: str, speaking_rate: float) -> SpeechOutput: ...
    def list_voices(self) -> tuple[VoiceDescriptor, ...]: ...
    def supported_languages(self) -> frozenset[str]: ...
    def streaming_supported(self) -> bool: ...
