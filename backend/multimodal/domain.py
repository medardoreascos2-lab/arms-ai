"""Canonical multimodal types. Interfaces never receive independent authority."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Modality(str, Enum):
    TEXT = "TEXT"
    AUDIO_INPUT = "AUDIO_INPUT"
    AUDIO_OUTPUT = "AUDIO_OUTPUT"
    IMAGE = "IMAGE"
    DOCUMENT = "DOCUMENT"
    CAMERA_FRAME = "CAMERA_FRAME"
    VIDEO_CLIP = "VIDEO_CLIP"
    AVATAR_OUTPUT = "AVATAR_OUTPUT"
    NOTIFICATION = "NOTIFICATION"


@dataclass(frozen=True)
class ModalityAuthority:
    """Authority is intentionally unavailable to every multimodal interface."""

    broker: bool = False
    paper: bool = False
    live: bool = False
    portfolio_mutation: bool = False
    payments: bool = False
    external_delivery: bool = False
    device_control: bool = False
