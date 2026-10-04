"""R106A local scoped lexical retrieval with SQLite FTS5."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from backend.medar.durable_memory_record import (
    DurableMemoryDomain, DurableMemoryRecord, DurableMemoryType,
    DurableSensitivity, MemoryLifecycle, ProvenanceClass, RetentionPolicy,
    content_digest,
)
from backend.medar.memory_access import AuthorizedMemoryStore, MemoryAccessContext, MemoryAgentPermission, MemoryPurpose
from backend.medar.memory_lexical_retrieval import LexicalMemoryRetriever
from backend.medar.memory_provenance import MemoryOrigin, MemoryProvenance
from backend.medar.sqlite_memory_store import MemoryScope, SQLiteMemoryStore


NOW = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)
SCOPE = MemoryScope("tenant-a", "owner-a")


def _record(memory_id, content, *, domain=DurableMemoryDomain.TECHNICAL, importance=0.7, source_type="synthetic_test", observed_at=NOW):
    return DurableMemoryRecord(
        memory_id, "owner-a", "tenant-a", domain, DurableMemoryType.LESSON,
        content, content_digest(content), source_type, "synthetic-source-" + memory_id,
        MemoryProvenance("synthetic-source-" + memory_id, MemoryOrigin.OBSERVED, observed_at, "tenant-a", "owner-a", "synthetic-context", 0.9),
        ProvenanceClass.DIRECT_OBSERVATION, 0.9, importance, DurableSensitivity.INTERNAL,
        NOW, observed_at, None, RetentionPolicy.LONG_TERM, MemoryLifecycle.ACTIVE, 1,
    )


def _context(**changes):
    values = dict(
        requester_id="owner-a", requester_tenant_id="tenant-a", owner_id="owner-a", tenant_id="tenant-a",
        domain=DurableMemoryDomain.TECHNICAL, sensitivity=DurableSensitivity.INTERNAL,
        purpose=MemoryPurpose.TECHNICAL_ASSISTANCE, permission=MemoryAgentPermission.READ,
    )
    values.update(changes)
    return MemoryAccessContext(**values)


def test_fts_retrieval_filters_owner_domain_date_importance_and_source(tmp_path):
    path = tmp_path / "memory.db"
    with SQLiteMemoryStore(path, read_only=False) as store:
        store.write(SCOPE, _record("m1", "Verify schema migration checksum", importance=0.9, source_type="task_outcome"))
        store.write(SCOPE, _record("m2", "Check schema on startup", importance=0.4, observed_at=NOW - timedelta(days=5)))
        store.write(SCOPE, _record("m3", "Schema marketing note", domain=DurableMemoryDomain.MARKETING))
    with SQLiteMemoryStore(path) as store:
        retriever = LexicalMemoryRetriever(AuthorizedMemoryStore(store))
        result = retriever.retrieve(
            _context(), "schema", observed_from=NOW - timedelta(days=1),
            minimum_importance=0.8, source_type="task_outcome",
        )
        assert result.engine == "SQLITE_FTS5"
        assert [hit.memory_id for hit in result.hits] == ["m1"]
        assert result.hits[0].source_reference == "synthetic-source-m1"
        assert isinstance(result.hits[0].bm25_rank, float)
        assert result.semantic_quality_validated is False
        assert len(store.history(SCOPE, "m1")) == 1


def test_inactive_and_cross_scope_memory_never_retrieved(tmp_path):
    path = tmp_path / "memory.db"
    with SQLiteMemoryStore(path, read_only=False) as store:
        store.write(SCOPE, _record("m1", "Scoped technical lesson"))
        store.retract(SCOPE, "m1")
        store.write(SCOPE, _record("m2", "Another scoped lesson"))
    with SQLiteMemoryStore(path) as store:
        retriever = LexicalMemoryRetriever(AuthorizedMemoryStore(store))
        assert retriever.retrieve(_context(), "technical").hits == ()
        with pytest.raises(PermissionError):
            retriever.retrieve(_context(requester_id="other"), "scoped")
        assert [hit.memory_id for hit in retriever.retrieve(_context(), "scoped").hits] == ["m2"]


def test_active_listing_fails_closed_instead_of_silent_truncation(tmp_path):
    path = tmp_path / "memory.db"
    with SQLiteMemoryStore(path, read_only=False) as store:
        store.write(SCOPE, _record("m1", "schema one"))
        store.write(SCOPE, _record("m2", "schema two"))
        with pytest.raises(ValueError, match="budget"):
            store.list_active(SCOPE, DurableMemoryDomain.TECHNICAL, DurableSensitivity.INTERNAL, max_records=1)


@pytest.mark.parametrize("kwargs", [
    {"minimum_importance": float("nan")},
    {"observed_from": datetime(2026, 10, 3)},
    {"limit": 0},
    {"source_type": ""},
])
def test_invalid_filters_fail_before_store_access(kwargs):
    class FailIfCalled:
        def list_active(self, *args):
            raise AssertionError("store must not be called")
    retriever = LexicalMemoryRetriever(FailIfCalled())
    with pytest.raises(ValueError):
        retriever.retrieve(_context(), "schema", **kwargs)


def test_unavailable_fts_uses_explicit_lexical_fallback(tmp_path, monkeypatch):
    path = tmp_path / "memory.db"
    with SQLiteMemoryStore(path, read_only=False) as store:
        store.write(SCOPE, _record("m1", "Verify schema migration checksum"))
    with SQLiteMemoryStore(path) as store:
        from backend.medar import memory_lexical_retrieval as module
        real_connect = module.sqlite3.connect

        class NoFtsConnection:
            def __init__(self):
                self.inner = real_connect(":memory:")

            def execute(self, sql, *args):
                if sql.startswith("CREATE VIRTUAL TABLE"):
                    raise module.sqlite3.OperationalError("no such module: fts5")
                return self.inner.execute(sql, *args)

            def close(self):
                self.inner.close()

        monkeypatch.setattr(module.sqlite3, "connect", lambda *_args: NoFtsConnection())
        result = LexicalMemoryRetriever(AuthorizedMemoryStore(store)).retrieve(_context(), "schema")
        assert result.engine == "LEXICAL_FALLBACK"
        assert [hit.memory_id for hit in result.hits] == ["m1"]
        assert result.hits[0].bm25_rank is None
