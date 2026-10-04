"""R106C deterministic test embedding behavior without semantic claims."""

import math

import pytest

from backend.medar.deterministic_embedding import DeterministicEmbeddingProvider
from backend.medar.durable_memory_record import DurableSensitivity
from backend.medar.embedding_provider import EmbeddingProviderKind, EmbeddingRequest


def test_same_text_has_stable_normalized_test_vector():
    provider = DeterministicEmbeddingProvider()
    first = provider.embed(EmbeddingRequest(provider.descriptor.model_id, "Synthetic technical lesson"))
    second = provider.embed(EmbeddingRequest(provider.descriptor.model_id, "  synthetic   TECHNICAL lesson  "))
    assert first.vector == second.vector
    assert len(first.vector) == provider.descriptor.dimensions == 16
    assert math.isclose(sum(value * value for value in first.vector), 1.0, rel_tol=1e-12)
    assert first.external_call_performed is False
    assert first.semantic_quality_validated is False
    assert provider.descriptor.kind is EmbeddingProviderKind.TEST_EMBEDDING


def test_different_text_has_different_test_vector_without_quality_claim():
    provider = DeterministicEmbeddingProvider()
    left = provider.embed(EmbeddingRequest(provider.descriptor.model_id, "synthetic one"))
    right = provider.embed(EmbeddingRequest(provider.descriptor.model_id, "synthetic two"))
    assert left.vector != right.vector
    assert left.semantic_quality_validated is False


def test_model_mismatch_and_sensitive_input_fail_closed():
    provider = DeterministicEmbeddingProvider()
    with pytest.raises(ValueError, match="identity"):
        provider.embed(EmbeddingRequest("other", "synthetic text"))
    with pytest.raises(PermissionError, match="sensitive"):
        provider.embed(EmbeddingRequest(provider.descriptor.model_id, "private", DurableSensitivity.SENSITIVE))


def test_untyped_sensitivity_is_rejected_at_request_boundary():
    with pytest.raises(TypeError):
        EmbeddingRequest("test", "synthetic", "INTERNAL")
