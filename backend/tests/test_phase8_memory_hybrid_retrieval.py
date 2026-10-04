"""R106E hybrid retrieval evidence, stale-vector, and scope tests."""

from datetime import datetime, timezone

import pytest

from backend.medar.deterministic_embedding import DeterministicEmbeddingProvider
from backend.medar.durable_memory_record import (
    DurableMemoryDomain, DurableMemoryRecord, DurableMemoryType,
    DurableSensitivity, MemoryLifecycle, ProvenanceClass, RetentionPolicy,
    content_digest,
)
from backend.medar.embedding_provider import EmbeddingRequest
from backend.medar.memory_access import AuthorizedMemoryStore, MemoryAccessContext, MemoryAgentPermission, MemoryPurpose
from backend.medar.memory_hybrid_retrieval import HybridMemoryRetriever
from backend.medar.memory_provenance import MemoryOrigin, MemoryProvenance
from backend.medar.sqlite_memory_store import MemoryScope, SQLiteMemoryStore
from backend.medar.vector_memory_index import SQLiteVectorMemoryIndex


NOW = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)
SCOPE = MemoryScope("tenant-a", "owner-a")


def _record(memory_id, content, domain=DurableMemoryDomain.TECHNICAL):
    return DurableMemoryRecord(
        memory_id, "owner-a", "tenant-a", domain, DurableMemoryType.FACT,
        content, content_digest(content), "synthetic_test", "source-" + memory_id,
        MemoryProvenance("source-" + memory_id, MemoryOrigin.OBSERVED, NOW, "tenant-a", "owner-a", "context", 0.9),
        ProvenanceClass.DIRECT_OBSERVATION, 0.9, 0.8, DurableSensitivity.PUBLIC,
        NOW, NOW, None, RetentionPolicy.LONG_TERM, MemoryLifecycle.ACTIVE, 1,
    )


def _context(domain=DurableMemoryDomain.TECHNICAL, **changes):
    values = dict(
        requester_id="owner-a", requester_tenant_id="tenant-a",
        owner_id="owner-a", tenant_id="tenant-a", domain=domain,
        sensitivity=DurableSensitivity.PUBLIC,
        purpose=MemoryPurpose.TECHNICAL_ASSISTANCE if domain is DurableMemoryDomain.TECHNICAL else MemoryPurpose.RESEARCH,
        permission=MemoryAgentPermission.READ,
    )
    values.update(changes)
    return MemoryAccessContext(**values)


def _query_embedding(provider, text):
    return provider.embed(EmbeddingRequest(provider.descriptor.model_id, text, DurableSensitivity.PUBLIC))


def test_hybrid_returns_scoped_evidence_scores_and_test_vector_only_when_enabled(tmp_path):
    memory_path = tmp_path / "memory.db"
    vector_path = tmp_path / "vectors.db"
    primary = _record("m1", "schema migration checksum")
    secondary = _record("m2", "schema startup checklist")
    provider = DeterministicEmbeddingProvider()
    request = EmbeddingRequest(provider.descriptor.model_id, primary.content, DurableSensitivity.PUBLIC)
    with SQLiteMemoryStore(memory_path, read_only=False) as memory, SQLiteVectorMemoryIndex(vector_path, read_only=False) as vectors:
        memory.write(SCOPE, primary)
        memory.write(SCOPE, secondary)
        vectors.write(SCOPE, primary, request, provider.embed(request))
    with SQLiteMemoryStore(memory_path) as memory, SQLiteVectorMemoryIndex(vector_path) as vectors:
        store = AuthorizedMemoryStore(memory)
        query_embedding = _query_embedding(provider, primary.content)
        default = HybridMemoryRetriever(store, vector_index=vectors, clock=lambda: NOW).retrieve(
            (_context(),), "schema", query_embedding=query_embedding,
        )
        assert all(item.vector_score == 0 for item in default.evidence)
        enabled = HybridMemoryRetriever(store, vector_index=vectors, clock=lambda: NOW, allow_test_embeddings=True).retrieve(
            (_context(),), "schema", query_embedding=query_embedding,
        )
        assert [item.memory_id for item in enabled.evidence] == ["m1", "m2"]
        assert enabled.evidence[0].vector_score == pytest.approx(1.0)
        assert enabled.evidence[0].source_reference == "source-m1"
        assert enabled.evidence[0].record.provenance.source_id == "source-m1"
        assert enabled.evidence[0].semantic_quality_validated is False
        assert enabled.external_call_performed is False
        assert enabled.persistence_performed is False


def test_stale_vector_is_skipped_after_memory_supersession(tmp_path):
    memory_path = tmp_path / "memory.db"
    vector_path = tmp_path / "vectors.db"
    record = _record("m1", "schema migration checksum")
    provider = DeterministicEmbeddingProvider()
    request = EmbeddingRequest(provider.descriptor.model_id, record.content, DurableSensitivity.PUBLIC)
    with SQLiteMemoryStore(memory_path, read_only=False) as memory, SQLiteVectorMemoryIndex(vector_path, read_only=False) as vectors:
        memory.write(SCOPE, record)
        vectors.write(SCOPE, record, request, provider.embed(request))
        memory.supersede(SCOPE, record.memory_id)
    with SQLiteMemoryStore(memory_path) as memory, SQLiteVectorMemoryIndex(vector_path) as vectors:
        result = HybridMemoryRetriever(AuthorizedMemoryStore(memory), vector_index=vectors, clock=lambda: NOW, allow_test_embeddings=True).retrieve(
            (_context(),), "schema", query_embedding=_query_embedding(provider, record.content),
        )
        assert result.evidence == ()
        assert result.stale_vectors_skipped == 1


def test_primary_domain_has_higher_relevance_when_other_components_equal(tmp_path):
    path = tmp_path / "memory.db"
    with SQLiteMemoryStore(path, read_only=False) as memory:
        memory.write(SCOPE, _record("technical", "schema guidance", DurableMemoryDomain.TECHNICAL))
        memory.write(SCOPE, _record("research", "schema guidance", DurableMemoryDomain.RESEARCH))
    with SQLiteMemoryStore(path) as memory:
        result = HybridMemoryRetriever(AuthorizedMemoryStore(memory), clock=lambda: NOW).retrieve(
            (_context(), _context(DurableMemoryDomain.RESEARCH)), "schema",
        )
        assert [item.record.domain for item in result.evidence] == [DurableMemoryDomain.TECHNICAL, DurableMemoryDomain.RESEARCH]
        assert result.evidence[0].domain_score == 1.0
        assert result.evidence[1].domain_score == 0.7


def test_cross_user_context_is_denied_before_any_result(tmp_path):
    path = tmp_path / "memory.db"
    with SQLiteMemoryStore(path, read_only=False):
        pass
    with SQLiteMemoryStore(path) as memory:
        retriever = HybridMemoryRetriever(AuthorizedMemoryStore(memory), clock=lambda: NOW)
        with pytest.raises(PermissionError):
            retriever.retrieve((_context(requester_id="other"),), "schema")

def test_vector_only_match_is_returned_when_test_embeddings_are_explicitly_enabled(tmp_path):
    memory_path = tmp_path / "memory.db"
    vector_path = tmp_path / "vectors.db"
    record = _record("m1", "checksum verification")
    provider = DeterministicEmbeddingProvider()
    request = EmbeddingRequest(provider.descriptor.model_id, record.content, DurableSensitivity.PUBLIC)
    with SQLiteMemoryStore(memory_path, read_only=False) as memory, SQLiteVectorMemoryIndex(vector_path, read_only=False) as vectors:
        memory.write(SCOPE, record)
        vectors.write(SCOPE, record, request, provider.embed(request))
    with SQLiteMemoryStore(memory_path) as memory, SQLiteVectorMemoryIndex(vector_path) as vectors:
        retriever = HybridMemoryRetriever(AuthorizedMemoryStore(memory), vector_index=vectors, clock=lambda: NOW, allow_test_embeddings=True)
        result = retriever.retrieve((_context(),), "unmatched lexical phrase", query_embedding=_query_embedding(provider, record.content))
        assert [item.memory_id for item in result.evidence] == ["m1"]
        assert result.evidence[0].lexical_score == 0
        assert result.evidence[0].vector_score == pytest.approx(1.0)
