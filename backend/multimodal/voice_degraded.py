"""Truthful voice degraded states with explicit text alternative."""

from dataclasses import dataclass
from enum import Enum


class VoiceDegradedState(str, Enum):
    MIC_PERMISSION_DENIED="MIC_PERMISSION_DENIED"
    MIC_UNAVAILABLE="MIC_UNAVAILABLE"
    STT_UNAVAILABLE="STT_UNAVAILABLE"
    TTS_UNAVAILABLE="TTS_UNAVAILABLE"
    AUDIO_INVALID="AUDIO_INVALID"
    MODEL_UNAVAILABLE="MODEL_UNAVAILABLE"


@dataclass(frozen=True)
class VoiceDegradedResponse:
    state: VoiceDegradedState
    message: str
    text_fallback_offered: bool = True
    provider_switched: bool = False
    audio_reference: None = None


_MESSAGES={
    VoiceDegradedState.MIC_PERMISSION_DENIED:"Microphone permission was denied. You can continue with text.",
    VoiceDegradedState.MIC_UNAVAILABLE:"A microphone is unavailable. You can continue with text.",
    VoiceDegradedState.STT_UNAVAILABLE:"Speech recognition is unavailable. No alternate provider was selected.",
    VoiceDegradedState.TTS_UNAVAILABLE:"Speech output is unavailable. Read the text response instead.",
    VoiceDegradedState.AUDIO_INVALID:"The audio did not pass validation and was not processed.",
    VoiceDegradedState.MODEL_UNAVAILABLE:"MEDAR is unavailable. No response was fabricated.",
}


def voice_degraded(state: VoiceDegradedState) -> VoiceDegradedResponse:
    return VoiceDegradedResponse(state=state,message=_MESSAGES[state])
