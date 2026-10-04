"""Canonical multimodal response with explicit provenance and degraded state."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Mapping


class MultimodalDegradedState(str, Enum):
    NONE = "NONE"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    UNSUPPORTED_MODALITY = "UNSUPPORTED_MODALITY"
    INVALID_CONTENT = "INVALID_CONTENT"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"


@dataclass(frozen=True)
class MultimodalResponse:
    response_id: str
    request_id: str
    text: str | None
    audio_reference: str | None = None
    visual_reference: str | None = None
    avatar_instruction: Mapping[str, str] = field(default_factory=dict)
    notification_instruction: Mapping[str, str] = field(default_factory=dict)
    confidence: float | None = None
    sources: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    provenance: Mapping[str, str] = field(default_factory=dict)
    degraded_state: MultimodalDegradedState = MultimodalDegradedState.NONE

    def __post_init__(self) -> None:
        if not self.response_id or not self.request_id:
            raise ValueError("response and request identifiers required")
        if self.confidence is not None and not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between zero and one")
        if not isinstance(self.degraded_state, MultimodalDegradedState):
            raise ValueError("canonical degraded state required")
        for name in ("sources", "warnings"):
            value = getattr(self, name)
            if not isinstance(value, tuple) or any(not isinstance(item, str) for item in value):
                raise ValueError(f"{name} must be immutable text")
        for name in ("avatar_instruction", "notification_instruction", "provenance"):
            value = getattr(self, name)
            if not isinstance(value, Mapping) or any(
                not isinstance(k, str) or not isinstance(v, str) for k, v in value.items()
            ):
                raise ValueError(f"{name} must contain text pairs")
            object.__setattr__(self, name, MappingProxyType(dict(value)))
