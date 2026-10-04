"""R107A reranking tests for relevance, authorization, and stale evidence."""

from datetime import datetime, timezone

import pytest

from backend.medar.durable_memory_record import (
    DurableMemoryDomain, DurableMemoryRecord, DurableMemoryType,
    DurableSensitivity, MemoryLifecycle, ProvenanceClass, RetentionPolicy,
    content_digest,
)
from backend.medar.memory_access import AuthorizedMemoryStore, MemoryAccessContext, MemoryAgentPermission, MemoryPurpose
from backend.medar.memory_hybrid_retrieval import HybridMemoryRetriever
from backend.medar.memory_provenance import MemoryOrigin, MemoryProvenance
from backend.medar.memory_reranking import MemoryReranker
from backend.medar.sqlite_memory_store import MemoryScope, SQLiteMemoryStore


NOW = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)
SCOPE = MemoryScope("tenant-a", "owner-a")


def _record(memory_id, content, provenance_class=ProvenanceClass.DIRECT_OBSERVATION):
    origin = MemoryOrigin.INFERRED if provenance_class is ProvenanceClass.MODEL_INFERENCE else MemoryOrigin.OBSERVED
    return DurableMemoryRecord(
        memory_id, "owner-a", "tenant-a", DurableMemoryDomain.TECHNICAL,
        DurableMemoryType.FACT, content, content_digest(content), "synthetic_test",
        "source-" + memory_id,
        MemoryProvenance("source-" + memory_id, origin, NOW, "tenant-a", "owner-a", "context", 0.9),
        provenance_class, 0.9, 0.8, DurableSensitivity.PUBLIC,
        NOW, NOW, None, RetentionPolicy.LONG_TERM, MemoryLifecycle.ACTIVE, 1,
    )


def _context(**changes):
    values = dict(
        requester_id="owner-a", requester_tenant_id="tenant-a",
        owner_id="owner-a", tenant_id="tenant-a", domain=DurableMemoryDomain.TECHNICAL,
        sensitivity=DurableSensitivity.PUBLIC, purpose=MemoryPurpose.TECHNICAL_ASSISTANCE,
        permission=MemoryAgentPermission.READ,
    )
    values.update(changes)
    return MemoryAccessContext(**values)


def test_reranking_uses_query_relevance_and_retains_traceable_evidence(tmp_path):
    path = tmp_path / "memory.db"
    with SQLiteMemoryStore(path, read_only=False) as memory:
        memory.write(SCOPE, _record("one", "schema checksum"))
        memory.write(SCOPE, _record("two", "schema configuration"))
    with SQLiteMemoryStore(path) as memory:
        store = AuthorizedMemoryStore(memory)
        hybrid = HybridMemoryRetriever(store, clock=lambda: NOW).retrieve((_context(),), "schema")
        ranked = MemoryReranker(store, clock=lambda: NOW).rerank((_context(),), "schema checksum", hybrid)
        assert [item.memory_id for item in ranked.evidence] == ["one", "two"]
        assert ranked.evidence[0].query_score > ranked.evidence[1].query_score
        assert ranked.evidence[0].source_reference == "source-one"
        assert ranked.evidence[0].record.provenance.source_id == "source-one"
        assert ranked.evidence[0].original_evidence.record == ranked.evidence[0].record
        assert ranked.evidence[0].heuristic_only
        assert not ranked.external_call_performed and not ranked.persistence_performed


def test_source_quality_favors_direct_observation_over_model_inference(tmp_path):
    path = tmp_path / "memory.db"
    with SQLiteMemoryStore(path, read_only=False) as memory:
        memory.write(SCOPE, _record("direct", "schema guidance"))
        memory.write(SCOPE, _record("inferred", "schema guidance", ProvenanceClass.MODEL_INFERENCE))
    with SQLiteMemoryStore(path) as memory:
        store = AuthorizedMemoryStore(memory)
        hybrid = HybridMemoryRetriever(store, clock=lambda: NOW).retrieve((_context(),), "schema guidance")
        ranked = MemoryReranker(store, clock=lambda: NOW).rerank((_context(),), "schema guidance", hybrid)
        assert [item.memory_id for item in ranked.evidence] == ["direct", "inferred"]
        assert ranked.evidence[0].source_quality_score > ranked.evidence[1].source_quality_score


def test_reranking_skips_stale_candidate_after_supersession(tmp_path):
    path = tmp_path / "memory.db"
    with SQLiteMemoryStore(path, read_only=False) as memory:
        memory.write(SCOPE, _record("one", "schema checksum"))
    with SQLiteMemoryStore(path) as memory:
        hybrid = HybridMemoryRetriever(AuthorizedMemoryStore(memory), clock=lambda: NOW).retrieve((_context(),), "schema")
    with SQLiteMemoryStore(path, read_only=False) as memory:
        memory.supersede(SCOPE, "one")
    with SQLiteMemoryStore(path) as memory:
        ranked = MemoryReranker(AuthorizedMemoryStore(memory), clock=lambda: NOW).rerank((_context(),), "schema", hybrid)
        assert ranked.evidence == ()
        assert ranked.stale_records_skipped == 1


def test_reranking_denies_unapproved_requester_before_reading_candidates(tmp_path):
    path = tmp_path / "memory.db"
    with SQLiteMemoryStore(path, read_only=False) as memory:
        memory.write(SCOPE, _record("one", "schema checksum"))
    with SQLiteMemoryStore(path) as memory:
        store = AuthorizedMemoryStore(memory)
        hybrid = HybridMemoryRetriever(store, clock=lambda: NOW).retrieve((_context(),), "schema")
        with pytest.raises(PermissionError):
            MemoryReranker(store, clock=lambda: NOW).rerank((_context(requester_id="other"),), "schema", hybrid)
