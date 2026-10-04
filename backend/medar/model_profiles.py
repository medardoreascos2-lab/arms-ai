"""Declarative capability profiles for provider-neutral MEDAR models."""

from dataclasses import dataclass
from enum import Enum, IntEnum
from types import MappingProxyType
from typing import Mapping

from backend.medar.model_provider import ModelKind


class CapabilityStrength(IntEnum):
    NONE = 0
    BASIC = 1
    STRONG = 2
    ADVANCED = 3


class LatencyClass(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class CostClass(IntEnum):
    FREE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3


class ModelLocality(str, Enum):
    LOCAL = "LOCAL"
    REMOTE = "REMOTE"


@dataclass(frozen=True)
class ModelCapabilityProfile:
    model_id: str
    kind: ModelKind
    context_window: int
    reasoning_strength: CapabilityStrength
    coding_strength: CapabilityStrength
    latency_class: LatencyClass
    cost_class: CostClass
    locality: ModelLocality
    tool_call_support: bool
    vision_support: bool
    structured_output_support: bool
    available: bool = True

    def __post_init__(self) -> None:
        if not self.model_id.strip():
            raise ValueError("model_id is required")
        if isinstance(self.context_window, bool) or self.context_window <= 0:
            raise ValueError("context_window must be positive")
        if self.locality is ModelLocality.LOCAL and self.kind is ModelKind.REMOTE_LLM:
            raise ValueError("remote model kind cannot claim local locality")


class ModelProfileRegistry:
    def __init__(self, profiles: tuple[ModelCapabilityProfile, ...]):
        entries: dict[str, ModelCapabilityProfile] = {}
        for profile in profiles:
            if profile.model_id in entries:
                raise ValueError("duplicate model profile")
            entries[profile.model_id] = profile
        self._entries: Mapping[str, ModelCapabilityProfile] = MappingProxyType(entries)

    @property
    def profiles(self) -> tuple[ModelCapabilityProfile, ...]:
        return tuple(self._entries.values())

    def get(self, model_id: str) -> ModelCapabilityProfile:
        return self._entries[model_id]
