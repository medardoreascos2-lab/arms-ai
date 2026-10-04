"""Fail-closed audio metadata and ownership validation."""

from __future__ import annotations

from dataclasses import dataclass

from .domain import Modality
from .request import MultimodalRequest

_ALLOWED = {"audio/wav": "wav", "audio/webm": "webm", "audio/ogg": "ogg"}


@dataclass(frozen=True)
class AudioInputDescriptor:
    content_reference: str
    owner_session_id: str
    owner_user_id: str
    owner_tenant_id: str
    mime_type: str
    format: str
    size_bytes: int
    duration_seconds: float


@dataclass(frozen=True)
class AudioInputLimits:
    max_size_bytes: int = 10_000_000
    max_duration_seconds: float = 120.0


def validate_audio_input(descriptor: AudioInputDescriptor, request: MultimodalRequest,
                         limits: AudioInputLimits = AudioInputLimits()) -> None:
    if request.modality != Modality.AUDIO_INPUT:
        raise ValueError("audio input request required")
    if descriptor.content_reference != request.content_reference:
        raise PermissionError("audio reference mismatch")
    if (descriptor.owner_session_id, descriptor.owner_user_id, descriptor.owner_tenant_id) != (
        request.session_id, request.user_id, request.tenant_id,
    ):
        raise PermissionError("audio ownership mismatch")
    expected = _ALLOWED.get(descriptor.mime_type)
    if expected is None or descriptor.mime_type != request.mime_type or descriptor.format != expected:
        raise ValueError("audio format or mime mismatch")
    if descriptor.size_bytes <= 0 or descriptor.size_bytes > limits.max_size_bytes:
        raise ValueError("audio size outside configured limit")
    if descriptor.duration_seconds <= 0 or descriptor.duration_seconds > limits.max_duration_seconds:
        raise ValueError("audio duration outside configured limit")
