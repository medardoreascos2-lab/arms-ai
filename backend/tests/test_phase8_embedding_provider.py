"""R106B embedding contract and remote-disabled behavior."""

import pytest

from backend.medar.durable_memory_record import DurableSensitivity
from backend.medar.embedding_provider import (
    DisabledRemoteEmbeddingProvider, EmbeddingDescriptor, EmbeddingProvider,
    EmbeddingProviderKind, EmbeddingRequest, EmbeddingResult,
)
from backend.medar.local_model_provider import ModelReadiness


class LocalContractDouble:
    @property
    def descriptor(self):
        return EmbeddingDescriptor("local-test", "test-embedding", "v1", EmbeddingProviderKind.TEST_EMBEDDING, 2, DurableSensitivity.INTERNAL)

    def readiness(self):
        return ModelReadiness.READY

    def embed(self, request):
        return EmbeddingResult("local-test", request.model_id, "v1", (1.0, 0.0))


def test_local_embedding_contract_can_return_finite_vector_without_external_call():
    provider: EmbeddingProvider = LocalContractDouble()
    result = provider.embed(EmbeddingRequest("test-embedding", "synthetic text"))
    assert result.vector == (1.0, 0.0)
    assert result.external_call_performed is False
    assert result.semantic_quality_validated is False


def test_remote_embedding_provider_is_disabled_by_default():
    provider = DisabledRemoteEmbeddingProvider()
    assert provider.descriptor.kind is EmbeddingProviderKind.REMOTE_EMBEDDING_DISABLED_BY_DEFAULT
    assert provider.readiness() is ModelReadiness.PRIVACY_BLOCKED
    with pytest.raises(PermissionError, match="disabled"):
        provider.embed(EmbeddingRequest(provider.descriptor.model_id, "synthetic text"))


@pytest.mark.parametrize("vector", [(), (float("nan"),), (float("inf"),), (True,)])
def test_invalid_vectors_are_rejected(vector):
    with pytest.raises(ValueError):
        EmbeddingResult("local-test", "test", "v1", vector)


def test_embedding_request_and_descriptor_validate_size_and_scope():
    with pytest.raises(ValueError):
        EmbeddingRequest("test", "x" * 8193)
    with pytest.raises(ValueError):
        EmbeddingDescriptor("local", "test", "v1", EmbeddingProviderKind.LOCAL_EMBEDDING, 0, DurableSensitivity.PUBLIC)
