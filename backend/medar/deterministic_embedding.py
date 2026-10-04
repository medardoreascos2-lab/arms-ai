"""Deterministic hash projection for tests only; not a semantic embedding."""

import hashlib
import math

from backend.medar.durable_memory_record import DurableSensitivity
from backend.medar.embedding_provider import (
    EmbeddingDescriptor, EmbeddingProviderKind, EmbeddingRequest, EmbeddingResult,
)
from backend.medar.local_model_provider import ModelReadiness


class DeterministicEmbeddingProvider:
    provider_id = "deterministic-test-embedding"

    def __init__(self, model_id: str = "deterministic-test-embedding-model"):
        self._descriptor = EmbeddingDescriptor(
            self.provider_id, model_id, "sha256-projection-v1",
            EmbeddingProviderKind.TEST_EMBEDDING, 16, DurableSensitivity.INTERNAL,
        )

    @property
    def descriptor(self) -> EmbeddingDescriptor:
        return self._descriptor

    def readiness(self) -> ModelReadiness:
        return ModelReadiness.READY

    def embed(self, request: EmbeddingRequest) -> EmbeddingResult:
        if request.model_id != self.descriptor.model_id:
            raise ValueError("embedding model identity mismatch")
        if request.sensitivity not in (DurableSensitivity.PUBLIC, DurableSensitivity.INTERNAL):
            raise PermissionError("test embedding rejects sensitive memory")
        normalized = " ".join(request.text.split()).casefold()
        digest = hashlib.sha256(normalized.encode("utf-8", errors="strict")).digest()
        raw = tuple(
            int.from_bytes(digest[index:index + 2], "big") / 32767.5 - 1.0
            for index in range(0, 32, 2)
        )
        length = math.sqrt(sum(value * value for value in raw))
        vector = tuple(value / length for value in raw) if length else (1.0,) + (0.0,) * 15
        return EmbeddingResult(
            self.provider_id, self.descriptor.model_id,
            self.descriptor.version, vector,
        )
