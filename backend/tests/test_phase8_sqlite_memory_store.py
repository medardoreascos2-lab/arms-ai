"""R103A-D SQLite memory isolation, history, migration, and recovery tests."""

import sqlite3
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from backend.medar.durable_memory_record import (
    DurableMemoryDomain, DurableMemoryRecord, DurableMemoryType,
    DurableSensitivity, MemoryLifecycle, ProvenanceClass, RetentionPolicy,
    content_digest,
)
from backend.medar.memory_provenance import MemoryOrigin, MemoryProvenance
from backend.medar.sqlite_memory_store import MemoryScope, SQLiteMemoryStore


NOW = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)
SCOPE = MemoryScope("tenant-a", "owner-a")


def _record(memory_id="memory-1", **changes):
    provenance = MemoryProvenance("synthetic-source", MemoryOrigin.OBSERVED, NOW, "tenant-a", "owner-a", "synthetic-context", 0.9)
    fields = dict(
        memory_id=memory_id, owner_id="owner-a", tenant_id="tenant-a",
        domain=DurableMemoryDomain.TECHNICAL, memory_type=DurableMemoryType.LESSON,
        content="Synthetic lesson for safe retries", content_hash=content_digest("Synthetic lesson for safe retries"),
        source_type="synthetic_test", source_reference="synthetic-source",
        provenance=provenance, provenance_class=ProvenanceClass.DIRECT_OBSERVATION,
        confidence=0.9, importance=0.7, sensitivity=DurableSensitivity.INTERNAL,
        created_at=NOW, observed_at=NOW, expires_at=None,
        retention_policy=RetentionPolicy.LONG_TERM, status=MemoryLifecycle.ACTIVE, version=1,
    )
    fields.update(changes)
    return DurableMemoryRecord(**fields)


def test_write_restart_scoped_search_and_read_only(tmp_path):
    path = tmp_path / "memory.db"
    with SQLiteMemoryStore(path, read_only=False) as store:
        store.write(SCOPE, _record())
        assert [item.memory_id for item in store.search(SCOPE, "safe retries", (DurableMemoryDomain.TECHNICAL,))] == ["memory-1"]
        assert store.search(SCOPE, "safe retries", (DurableMemoryDomain.NQ,)) == ()
        assert store.search(MemoryScope("tenant-b", "owner-a"), "safe retries", (DurableMemoryDomain.TECHNICAL,)) == ()
        assert store.search(MemoryScope("tenant-a", "owner-b"), "safe retries", (DurableMemoryDomain.TECHNICAL,)) == ()
    with SQLiteMemoryStore(path) as store:
        assert store.get(SCOPE, "memory-1") == _record()
        with pytest.raises(PermissionError, match="read-only"):
            store.write(SCOPE, _record("memory-2"))


def test_scope_sensitive_write_and_duplicate_rejected_without_side_effect(tmp_path):
    path = tmp_path / "memory.db"
    with SQLiteMemoryStore(path, read_only=False) as store:
        with pytest.raises(PermissionError, match="scope"):
            store.write(MemoryScope("other", "owner-a"), _record())
        with pytest.raises(PermissionError, match="encryption"):
            store.write(SCOPE, _record(sensitivity=DurableSensitivity.PERSONAL))
        assert store.history(SCOPE, "memory-1") == ()
        store.write(SCOPE, _record())
        with pytest.raises(ValueError, match="already exists"):
            store.write(SCOPE, _record())
        assert len(store.history(SCOPE, "memory-1")) == 1


def test_lifecycle_is_append_only_and_removed_from_normal_retrieval(tmp_path):
    path = tmp_path / "memory.db"
    with SQLiteMemoryStore(path, read_only=False) as store:
        store.write(SCOPE, _record())
        superseded = store.supersede(SCOPE, "memory-1")
        assert superseded.version == 2 and superseded.status is MemoryLifecycle.SUPERSEDED
        assert [record.status for record in store.history(SCOPE, "memory-1")] == [MemoryLifecycle.ACTIVE, MemoryLifecycle.SUPERSEDED]
        assert store.search(SCOPE, "lesson", (DurableMemoryDomain.TECHNICAL,)) == ()
        with pytest.raises(ValueError, match="only active"):
            store.retract(SCOPE, "memory-1")
        store.write(SCOPE, _record("memory-2"))
        assert store.retract(SCOPE, "memory-2").status is MemoryLifecycle.RETRACTED
        store.write(SCOPE, _record("memory-3"))
        assert store.expire(SCOPE, "memory-3").status is MemoryLifecycle.EXPIRED


def test_expired_record_excluded_without_deleting_history(tmp_path):
    path = tmp_path / "memory.db"
    with SQLiteMemoryStore(path, read_only=False, clock=lambda: NOW + timedelta(days=2)) as store:
        store.write(SCOPE, _record(retention_policy=RetentionPolicy.UNTIL_DATE, expires_at=NOW + timedelta(days=1)))
        assert store.search(SCOPE, "lesson", (DurableMemoryDomain.TECHNICAL,)) == ()
        assert len(store.history(SCOPE, "memory-1")) == 1


def test_interrupted_transaction_does_not_report_recovered_write(tmp_path):
    path = tmp_path / "memory.db"
    with SQLiteMemoryStore(path, read_only=False):
        pass
    connection = sqlite3.connect(path)
    connection.execute("BEGIN IMMEDIATE")
    connection.execute("INSERT INTO memory_versions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                       ("tenant-a", "owner-a", "uncommitted", 1, "ACTIVE", "TECHNICAL", "INTERNAL", None, "x", "{}", NOW.isoformat()))
    connection.close()
    with SQLiteMemoryStore(path) as store:
        assert store.get(SCOPE, "uncommitted") is None


def test_corrupt_row_and_schema_mismatch_fail_closed(tmp_path):
    path = tmp_path / "memory.db"
    with SQLiteMemoryStore(path, read_only=False) as store:
        store.write(SCOPE, _record())
    connection = sqlite3.connect(path)
    connection.execute("UPDATE memory_versions SET record_json = '{}' WHERE memory_id = 'memory-1'")
    connection.commit()
    connection.close()
    with pytest.raises(ValueError, match="corrupt"):
        SQLiteMemoryStore(path)
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA user_version = 99")
    connection.close()
    with pytest.raises(ValueError, match="schema version"):
        SQLiteMemoryStore(path)


def test_migration_checksum_tampering_rejected(tmp_path):
    path = tmp_path / "memory.db"
    with SQLiteMemoryStore(path, read_only=False):
        pass
    connection = sqlite3.connect(path)
    connection.execute("UPDATE schema_migrations SET checksum = 'wrong'")
    connection.commit()
    connection.close()
    with pytest.raises(ValueError, match="checksum"):
        SQLiteMemoryStore(path)



def test_row_metadata_mismatch_fails_on_restart(tmp_path):
    path = tmp_path / "memory.db"
    with SQLiteMemoryStore(path, read_only=False) as store:
        store.write(SCOPE, _record())
    connection = sqlite3.connect(path)
    connection.execute("UPDATE memory_versions SET content = 'tampered' WHERE memory_id = 'memory-1'")
    connection.commit()
    connection.close()
    with pytest.raises(ValueError, match="metadata"):
        SQLiteMemoryStore(path)


def test_missing_history_version_fails_on_restart(tmp_path):
    path = tmp_path / "memory.db"
    with SQLiteMemoryStore(path, read_only=False) as store:
        store.write(SCOPE, _record())
        store.supersede(SCOPE, "memory-1")
    connection = sqlite3.connect(path)
    connection.execute("DELETE FROM memory_versions WHERE memory_id = 'memory-1' AND version = 1")
    connection.commit()
    connection.close()
    with pytest.raises(ValueError, match="history is incomplete"):
        SQLiteMemoryStore(path)


def test_session_working_memory_cannot_be_persisted(tmp_path):
    path = tmp_path / "memory.db"
    with SQLiteMemoryStore(path, read_only=False) as store:
        with pytest.raises(PermissionError, match="session memory"):
            store.write(SCOPE, _record(domain=DurableMemoryDomain.WORKING, retention_policy=RetentionPolicy.SESSION))
        assert store.history(SCOPE, "memory-1") == ()
