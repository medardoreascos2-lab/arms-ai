"""R107C citation tests for source traceability, scope, and stale memory."""

from datetime import datetime, timezone

import pytest

from backend.medar.durable_memory_record import (
    DurableMemoryDomain, DurableMemoryRecord, DurableMemoryType,
    DurableSensitivity, MemoryLifecycle, ProvenanceClass, RetentionPolicy,
    content_digest,
)
from backend.medar.memory_access import AuthorizedMemoryStore, MemoryAccessContext, MemoryAgentPermission, MemoryPurpose
from backend.medar.memory_context_budget import MemoryContextBudget, select_memory_context
from backend.medar.memory_evidence_references import build_cited_memory_context
from backend.medar.memory_hybrid_retrieval import HybridMemoryRetriever
from backend.medar.memory_provenance import MemoryOrigin, MemoryProvenance
from backend.medar.memory_reranking import MemoryReranker
from backend.medar.sqlite_memory_store import MemoryScope, SQLiteMemoryStore


NOW = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)
SCOPE = MemoryScope("tenant-a", "owner-a")


def _context(**changes):
    values = dict(
        requester_id="owner-a", requester_tenant_id="tenant-a",
        owner_id="owner-a", tenant_id="tenant-a", domain=DurableMemoryDomain.TECHNICAL,
        sensitivity=DurableSensitivity.PUBLIC, purpose=MemoryPurpose.TECHNICAL_ASSISTANCE,
        permission=MemoryAgentPermission.READ,
    )
    values.update(changes)
    return MemoryAccessContext(**values)


def _fixture(tmp_path):
    path = tmp_path / "memory.db"
    content = "schema checksum verified"
    record = DurableMemoryRecord(
        "memory-1", "owner-a", "tenant-a", DurableMemoryDomain.TECHNICAL,
        DurableMemoryType.FACT, content, content_digest(content), "synthetic_test",
        "source-1", MemoryProvenance("source-1", MemoryOrigin.OBSERVED, NOW, "tenant-a", "owner-a", "context", 0.9),
        ProvenanceClass.DIRECT_OBSERVATION, 0.9, 0.8, DurableSensitivity.PUBLIC,
        NOW, NOW, None, RetentionPolicy.LONG_TERM, MemoryLifecycle.ACTIVE, 1,
    )
    with SQLiteMemoryStore(path, read_only=False) as memory:
        memory.write(SCOPE, record)
    with SQLiteMemoryStore(path) as memory:
        store = AuthorizedMemoryStore(memory)
        hybrid = HybridMemoryRetriever(store, clock=lambda: NOW).retrieve((_context(),), "schema")
        ranked = MemoryReranker(store, clock=lambda: NOW).rerank((_context(),), "schema", hybrid)
        selection = select_memory_context(ranked, MemoryContextBudget(1000, 10, {DurableMemoryDomain.TECHNICAL: 1000}))
    return path, record, selection


def test_cited_context_retains_memory_id_version_hash_and_source(tmp_path):
    path, record, selection = _fixture(tmp_path)
    with SQLiteMemoryStore(path) as memory:
        context = build_cited_memory_context(selection, AuthorizedMemoryStore(memory), (_context(),))
        assert len(context.items) == 1
        item = context.items[0]
        assert item.content == record.content
        assert item.reference.memory_id == record.memory_id
        assert item.reference.version == record.version
        assert item.reference.content_hash == record.content_hash
        assert item.reference.source_reference == record.source_reference
        assert item.reference.provenance == record.provenance
        assert context.reserved_tokens == selection.reserved_tokens
        assert not context.external_call_performed and not context.persistence_performed


def test_cited_context_rejects_stale_or_unauthorized_memory(tmp_path):
    path, _, selection = _fixture(tmp_path)
    with SQLiteMemoryStore(path) as memory:
        with pytest.raises(PermissionError):
            build_cited_memory_context(selection, AuthorizedMemoryStore(memory), (_context(requester_id="other"),))
    with SQLiteMemoryStore(path, read_only=False) as memory:
        memory.supersede(SCOPE, "memory-1")
    with SQLiteMemoryStore(path) as memory:
        with pytest.raises(ValueError, match="changed"):
            build_cited_memory_context(selection, AuthorizedMemoryStore(memory), (_context(),))
