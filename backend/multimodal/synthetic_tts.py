"""Deterministic TTS metadata without fabricated audio bytes."""

from __future__ import annotations

import hashlib

from .speech_output import SpeechOutput, VoiceDescriptor


class SyntheticSpeechOutputProvider:
    provider_id = "LOCAL_TEST_ONLY_SYNTHETIC_TTS"

    def synthesize(self, text: str, voice_id: str, language: str, speaking_rate: float) -> SpeechOutput:
        if not text.strip():
            raise ValueError("text required")
        if voice_id not in {voice.voice_id for voice in self.list_voices()}:
            raise ValueError("unknown synthetic voice")
        if language not in self.supported_languages() or not 0.5 <= speaking_rate <= 2.0:
            raise ValueError("unsupported language or speaking rate")
        digest=hashlib.sha256(f"{voice_id}|{language}|{speaking_rate}|{text}".encode()).hexdigest()[:20]
        return SpeechOutput(audio_reference=f"synthetic-audio:{digest}",status="SYNTHETIC_AUDIO_REFERENCE",provider=self.provider_id,language=language,duration_seconds=None)

    def list_voices(self) -> tuple[VoiceDescriptor, ...]:
        return (VoiceDescriptor("synthetic-neutral","en","Synthetic neutral",True), VoiceDescriptor("synthetic-neutral-es","es","Synthetic neutral Spanish",True))

    def supported_languages(self) -> frozenset[str]:
        return frozenset({"en","es"})

    def streaming_supported(self) -> bool:
        return False
