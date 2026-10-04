"""Local inference provider metadata and fail-closed readiness contract.

This module defines capabilities only. Registration or metadata never grants model,
network, tool, or trading authority.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from backend.medar.model_policy import PrivacyClass
from backend.medar.model_provider import ModelInvocation, ModelKind, ModelProvider, ModelResult


class LocalProviderKind(str, Enum):
    OLLAMA = "OLLAMA"
    LLAMA_CPP = "LLAMA_CPP"
    LOCAL_HTTP = "LOCAL_HTTP"
    IN_PROCESS = "IN_PROCESS"
    DETERMINISTIC_TEST = "DETERMINISTIC_TEST"


class ModelReadiness(str, Enum):
    READY = "READY"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    MISCONFIGURED = "MISCONFIGURED"
    PRIVACY_BLOCKED = "PRIVACY_BLOCKED"


@dataclass(frozen=True)
class LocalModelCapabilities:
    supported_kinds: tuple[ModelKind, ...]
    context_length: int
    structured_output: bool
    tool_support: bool
    privacy_class: PrivacyClass

    def __post_init__(self) -> None:
        if not self.supported_kinds or any(
            not isinstance(kind, ModelKind) or kind is ModelKind.REMOTE_LLM
            for kind in self.supported_kinds
        ):
            raise ValueError("local provider requires supported local model kinds")
        if isinstance(self.context_length, bool) or not isinstance(self.context_length, int) or self.context_length <= 0:
            raise ValueError("context_length must be a positive integer")
        if not isinstance(self.structured_output, bool) or not isinstance(self.tool_support, bool):
            raise TypeError("capability flags must be boolean")
        if not isinstance(self.privacy_class, PrivacyClass):
            raise TypeError("privacy_class must be PrivacyClass")


@dataclass(frozen=True)
class LocalModelDescriptor:
    provider_id: str
    model_id: str
    provider_kind: LocalProviderKind
    capabilities: LocalModelCapabilities

    def __post_init__(self) -> None:
        if not isinstance(self.provider_id, str) or not self.provider_id.strip():
            raise ValueError("provider_id is required")
        if not isinstance(self.model_id, str) or not self.model_id.strip():
            raise ValueError("model_id is required")
        if not isinstance(self.provider_kind, LocalProviderKind):
            raise TypeError("provider_kind must be LocalProviderKind")
        if not isinstance(self.capabilities, LocalModelCapabilities):
            raise TypeError("capabilities must be LocalModelCapabilities")


@dataclass(frozen=True)
class LocalModelHealth:
    readiness: ModelReadiness
    reason: str
    checked_at: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.readiness, ModelReadiness):
            raise TypeError("readiness must be ModelReadiness")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("health reason is required")

    @property
    def available(self) -> bool:
        return self.readiness is ModelReadiness.READY


class LocalModelProvider(ModelProvider, Protocol):
    """Phase 7 model invocation plus inspectable local runtime properties."""

    is_local: bool

    @property
    def descriptor(self) -> LocalModelDescriptor: ...

    def health(self) -> LocalModelHealth: ...

    def is_available(self) -> bool: ...

    def invoke(self, invocation: ModelInvocation) -> ModelResult: ...
