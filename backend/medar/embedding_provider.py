"""Provider-neutral local embedding contract; remote embeddings are disabled."""

import math
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from backend.medar.durable_memory_record import DurableSensitivity
from backend.medar.local_model_provider import ModelReadiness


class EmbeddingProviderKind(str, Enum):
    LOCAL_EMBEDDING = "LOCAL_EMBEDDING"
    TEST_EMBEDDING = "TEST_EMBEDDING"
    REMOTE_EMBEDDING_DISABLED_BY_DEFAULT = "REMOTE_EMBEDDING_DISABLED_BY_DEFAULT"


@dataclass(frozen=True)
class EmbeddingDescriptor:
    provider_id: str
    model_id: str
    version: str
    kind: EmbeddingProviderKind
    dimensions: int
    maximum_sensitivity: DurableSensitivity

    def __post_init__(self) -> None:
        for name in ("provider_id", "model_id", "version"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} is required")
        if not isinstance(self.kind, EmbeddingProviderKind):
            raise TypeError("kind must be EmbeddingProviderKind")
        if isinstance(self.dimensions, bool) or not isinstance(self.dimensions, int) or not 1 <= self.dimensions <= 65_536:
            raise ValueError("embedding dimensions must be 1 to 65536")
        if not isinstance(self.maximum_sensitivity, DurableSensitivity):
            raise TypeError("maximum_sensitivity must be DurableSensitivity")


@dataclass(frozen=True)
class EmbeddingRequest:
    model_id: str
    text: str
    sensitivity: DurableSensitivity = DurableSensitivity.INTERNAL

    def __post_init__(self) -> None:
        if not isinstance(self.model_id, str) or not self.model_id.strip():
            raise ValueError("model_id is required")
        if not isinstance(self.text, str) or not self.text.strip() or len(self.text) > 8192:
            raise ValueError("embedding text must be non-empty and at most 8192 characters")
        if not isinstance(self.sensitivity, DurableSensitivity):
            raise TypeError("embedding sensitivity must be typed")


@dataclass(frozen=True)
class EmbeddingResult:
    provider_id: str
    model_id: str
    version: str
    vector: tuple[float, ...]
    external_call_performed: bool = False
    semantic_quality_validated: bool = False

    def __post_init__(self) -> None:
        for name in ("provider_id", "model_id", "version"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} is required")
        if self.external_call_performed or self.semantic_quality_validated:
            raise ValueError("Phase 8 embeddings cannot claim external calls or semantic quality")
        if not isinstance(self.vector, tuple) or not self.vector or any(
            isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
            for value in self.vector
        ):
            raise ValueError("embedding vector must contain finite numbers")


class EmbeddingProvider(Protocol):
    @property
    def descriptor(self) -> EmbeddingDescriptor: ...

    def readiness(self) -> ModelReadiness: ...

    def embed(self, request: EmbeddingRequest) -> EmbeddingResult: ...


class DisabledRemoteEmbeddingProvider:
    def __init__(self, model_id: str = "disabled-remote-embedding"):
        self._descriptor = EmbeddingDescriptor(
            "remote-disabled", model_id, "disabled",
            EmbeddingProviderKind.REMOTE_EMBEDDING_DISABLED_BY_DEFAULT,
            1, DurableSensitivity.PUBLIC,
        )

    @property
    def descriptor(self) -> EmbeddingDescriptor:
        return self._descriptor

    def readiness(self) -> ModelReadiness:
        return ModelReadiness.PRIVACY_BLOCKED

    def embed(self, request: EmbeddingRequest) -> EmbeddingResult:
        raise PermissionError("remote embeddings are disabled")
