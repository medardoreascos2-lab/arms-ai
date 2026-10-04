"""Separates untrusted media content from instructions and system authority."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any, Callable, Mapping

from .domain import Modality


class MediaTrust(str, Enum):
    UNTRUSTED_DATA = "UNTRUSTED_DATA"


class ExtractedSegmentKind(str, Enum):
    CONTENT = "CONTENT"
    EMBEDDED_INSTRUCTION = "EMBEDDED_INSTRUCTION"


@dataclass(frozen=True)
class ExtractedMediaSegment:
    kind: ExtractedSegmentKind
    text: str

    def __post_init__(self) -> None:
        if not self.text or len(self.text) > 20_000:
            raise ValueError("bounded extracted media text required")


@dataclass(frozen=True)
class UntrustedMediaContext:
    content_reference: str
    modality: Modality
    content: tuple[str, ...]
    embedded_instructions: tuple[str, ...]
    trust: MediaTrust = MediaTrust.UNTRUSTED_DATA
    system_authority: bool = False
    tool_authority: bool = False
    device_authority: bool = False
    trading_authority: bool = False

    def as_model_context(self) -> Mapping[str, Any]:
        """Return structured data; callers must not concatenate it into system instructions."""
        return MappingProxyType({
            "classification": self.trust.value,
            "content": self.content,
            "embedded_instructions": self.embedded_instructions,
            "instruction_policy": "DO_NOT_EXECUTE_OR_ELEVATE",
            "system_authority": self.system_authority,
            "tool_authority": self.tool_authority,
            "device_authority": self.device_authority,
            "trading_authority": self.trading_authority,
        })


@dataclass(frozen=True)
class MediaInstructionDecision:
    allowed: bool = False
    reason: str = "UNTRUSTED_MEDIA_INSTRUCTIONS_HAVE_NO_AUTHORITY"


def build_untrusted_media_context(*, content_reference: str, modality: Modality,
                                  segments: tuple[ExtractedMediaSegment, ...]) -> UntrustedMediaContext:
    if modality not in {Modality.AUDIO_INPUT, Modality.IMAGE, Modality.DOCUMENT,
                        Modality.CAMERA_FRAME, Modality.VIDEO_CLIP}:
        raise ValueError("captured media modality required")
    if not content_reference or not segments:
        raise ValueError("media reference and extracted segments required")
    return UntrustedMediaContext(
        content_reference=content_reference,
        modality=modality,
        content=tuple(segment.text for segment in segments if segment.kind is ExtractedSegmentKind.CONTENT),
        embedded_instructions=tuple(
            segment.text for segment in segments
            if segment.kind is ExtractedSegmentKind.EMBEDDED_INSTRUCTION
        ),
    )


def execute_embedded_media_instruction(
    context: UntrustedMediaContext,
    operation: Callable[[UntrustedMediaContext], Any],
) -> tuple[MediaInstructionDecision, None]:
    """A media-derived instruction never reaches an executable operation."""
    del context, operation
    return MediaInstructionDecision(), None