"""R120A scoped local memory backup captures integrity metadata."""

from datetime import datetime, timezone
import json
import sqlite3

from backend.medar.deterministic_embedding import DeterministicEmbeddingProvider
from backend.medar.durable_memory_record import (
    DurableMemoryDomain, DurableMemoryRecord, DurableMemoryType,
    DurableSensitivity, MemoryLifecycle, ProvenanceClass, RetentionPolicy,
    content_digest,
)
from backend.medar.embedding_provider import EmbeddingRequest
from backend.medar.memory_backup import create_memory_backup, open_memory_backup
from backend.medar.memory_provenance import MemoryOrigin, MemoryProvenance
from backend.medar.sqlite_memory_store import MemoryScope, SQLiteMemoryStore
from backend.medar.vector_memory_index import SQLiteVectorMemoryIndex


NOW = datetime(2026, 10, 4, 18, tzinfo=timezone.utc)
SCOPE = MemoryScope("tenant-a", "owner-a")
OTHER_SCOPE = MemoryScope("tenant-b", "owner-b")


def make_record(scope=SCOPE, memory_id="memory-1"):
    content = f"Synthetic public backup evidence for {memory_id}"
    return DurableMemoryRecord(
        memory_id, scope.owner_id, scope.tenant_id, DurableMemoryDomain.TECHNICAL,
        DurableMemoryType.FACT, content, content_digest(content), "synthetic_test", "synthetic-source",
        MemoryProvenance("synthetic-source", MemoryOrigin.OBSERVED, NOW, scope.tenant_id, scope.owner_id, "synthetic-context", 0.9),
        ProvenanceClass.DIRECT_OBSERVATION, 0.9, 0.8, DurableSensitivity.PUBLIC,
        NOW, NOW, None, RetentionPolicy.LONG_TERM, MemoryLifecycle.ACTIVE, 1,
    )


def create_sources(tmp_path):
    memory_path = tmp_path / "memory.db"
    vector_path = tmp_path / "vectors.db"
    provider = DeterministicEmbeddingProvider()
    with SQLiteMemoryStore(memory_path, read_only=False) as store, SQLiteVectorMemoryIndex(vector_path, read_only=False) as index:
        for scope, memory_id in ((SCOPE, "memory-1"), (OTHER_SCOPE, "foreign-memory")):
            record = make_record(scope, memory_id)
            store.write(scope, record)
            request = EmbeddingRequest(provider.descriptor.model_id, record.content, record.sensitivity)
            index.write(scope, record, request, provider.embed(request))
    return memory_path, vector_path


def test_backup_is_scope_isolated_and_captures_schema_provenance_index_and_hashes(tmp_path):
    memory_path, vector_path = create_sources(tmp_path)
    payload = create_memory_backup(memory_path, vector_path, SCOPE, created_at=NOW)
    bundle = open_memory_backup(payload)

    assert bundle.scope == SCOPE
    assert bundle.schema["memory_user_version"] == 1
    assert bundle.schema["vector_user_version"] == 1
    assert len(bundle.schema["memory_migration_checksum"]) == 64
    assert len(bundle.schema["vector_migration_checksum"]) == 64
    assert bundle.provenance == ({
        "memory_id": "memory-1", "version": 1, "source_id": "synthetic-source",
        "origin": "OBSERVED", "recorded_at": NOW.isoformat(),
        "context_id": "synthetic-context", "confidence": 0.9,
    },)
    assert bundle.index_metadata["mapping_count"] == 1
    assert len(bundle.hashes["memory_database_sha256"]) == 64
    assert len(bundle.hashes["vector_index_sha256"]) == 64
    assert not bundle.execution_authorized
    assert not bundle.production_restore_authorized

    memory = sqlite3.connect(":memory:")
    memory.deserialize(bundle.memory_database)
    assert memory.execute("SELECT tenant_id, owner_id, memory_id FROM memory_versions").fetchall() == [("tenant-a", "owner-a", "memory-1")]
    memory.close()


def test_backup_is_canonical_and_tampering_fails_closed(tmp_path):
    memory_path, vector_path = create_sources(tmp_path)
    payload = create_memory_backup(memory_path, vector_path, SCOPE, created_at=NOW)
    assert create_memory_backup(memory_path, vector_path, SCOPE, created_at=NOW) == payload
    document = json.loads(payload)
    document["schema"]["memory_user_version"] = 99
    tampered = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    try:
        open_memory_backup(tampered)
    except ValueError as exc:
        assert "identity" in str(exc) or "mismatch" in str(exc)
    else:
        raise AssertionError("tampered backup was accepted")
