"""R107B context selection tests for bounded and policy-filtered memory."""

from datetime import datetime, timezone

import pytest

from backend.medar.durable_memory_record import (
    DurableMemoryDomain, DurableMemoryRecord, DurableMemoryType,
    DurableSensitivity, MemoryLifecycle, ProvenanceClass, RetentionPolicy,
    content_digest,
)
from backend.medar.memory_access import AuthorizedMemoryStore, MemoryAccessContext, MemoryAgentPermission, MemoryPurpose
from backend.medar.memory_context_budget import MemoryContextBudget, select_memory_context
from backend.medar.memory_hybrid_retrieval import HybridMemoryRetriever
from backend.medar.memory_provenance import MemoryOrigin, MemoryProvenance
from backend.medar.memory_reranking import MemoryReranker
from backend.medar.sqlite_memory_store import MemoryScope, SQLiteMemoryStore


NOW = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)
SCOPE = MemoryScope("tenant-a", "owner-a")


def _record(memory_id, content):
    return DurableMemoryRecord(
        memory_id, "owner-a", "tenant-a", DurableMemoryDomain.TECHNICAL,
        DurableMemoryType.FACT, content, content_digest(content), "synthetic_test",
        "source-" + memory_id,
        MemoryProvenance("source-" + memory_id, MemoryOrigin.OBSERVED, NOW, "tenant-a", "owner-a", "context", 0.9),
        ProvenanceClass.DIRECT_OBSERVATION, 0.9, 0.8, DurableSensitivity.PUBLIC,
        NOW, NOW, None, RetentionPolicy.LONG_TERM, MemoryLifecycle.ACTIVE, 1,
    )


def _ranked(tmp_path):
    path = tmp_path / "memory.db"
    with SQLiteMemoryStore(path, read_only=False) as memory:
        memory.write(SCOPE, _record("one", "schema checksum"))
        memory.write(SCOPE, _record("two", "schema startup"))
        memory.write(SCOPE, _record("three", "schema archive"))
    context = MemoryAccessContext(
        "owner-a", "tenant-a", "owner-a", "tenant-a", DurableMemoryDomain.TECHNICAL,
        DurableSensitivity.PUBLIC, MemoryPurpose.TECHNICAL_ASSISTANCE, MemoryAgentPermission.READ,
    )
    with SQLiteMemoryStore(path) as memory:
        store = AuthorizedMemoryStore(memory)
        hybrid = HybridMemoryRetriever(store, clock=lambda: NOW).retrieve((context,), "schema")
        return MemoryReranker(store, clock=lambda: NOW).rerank((context,), "schema", hybrid)


def test_context_selection_enforces_count_and_total_token_limits(tmp_path):
    ranked = _ranked(tmp_path)
    generous = MemoryContextBudget(10000, 10, {DurableMemoryDomain.TECHNICAL: 10000})
    full = select_memory_context(ranked, generous)
    assert len(full.selected) == 3
    first_cost = full.selected[0].reserved_tokens
    count_limited = select_memory_context(ranked, MemoryContextBudget(10000, 1, {DurableMemoryDomain.TECHNICAL: 10000}))
    assert len(count_limited.selected) == 1
    assert all(reason == "MEMORY_COUNT_EXCEEDED" for _, reason in count_limited.skipped)
    token_limited = select_memory_context(ranked, MemoryContextBudget(first_cost, 10, {DurableMemoryDomain.TECHNICAL: 10000}))
    assert len(token_limited.selected) == 1
    assert token_limited.reserved_tokens == first_cost
    assert all(reason == "TOTAL_TOKEN_BUDGET_EXCEEDED" for _, reason in token_limited.skipped)
    assert not token_limited.persistence_performed


def test_context_selection_requires_domain_allocation_and_respects_domain_cap(tmp_path):
    ranked = _ranked(tmp_path)
    absent = select_memory_context(ranked, MemoryContextBudget(10000, 10, {DurableMemoryDomain.RESEARCH: 10000}))
    assert absent.selected == ()
    assert all(reason == "DOMAIN_NOT_BUDGETED" for _, reason in absent.skipped)
    full = select_memory_context(ranked, MemoryContextBudget(10000, 10, {DurableMemoryDomain.TECHNICAL: 10000}))
    first_cost = full.selected[0].reserved_tokens
    capped = select_memory_context(ranked, MemoryContextBudget(10000, 10, {DurableMemoryDomain.TECHNICAL: first_cost}))
    assert len(capped.selected) == 1
    assert all(reason == "DOMAIN_TOKEN_BUDGET_EXCEEDED" for _, reason in capped.skipped)


def test_sensitive_context_cannot_be_enabled_by_budget_configuration():
    with pytest.raises(PermissionError):
        MemoryContextBudget(1000, 10, {DurableMemoryDomain.PERSONAL: 1000}, frozenset({DurableSensitivity.PERSONAL}))
    with pytest.raises(ValueError):
        MemoryContextBudget(0, 10, {DurableMemoryDomain.TECHNICAL: 1000})
