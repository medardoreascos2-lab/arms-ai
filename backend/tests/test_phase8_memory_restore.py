"""R120B validates an isolated scoped memory restore."""

from datetime import datetime, timezone
import hashlib
import json

import pytest

from backend.medar.deterministic_embedding import DeterministicEmbeddingProvider
from backend.medar.durable_memory_record import (
    DurableMemoryDomain, DurableMemoryRecord, DurableMemoryType,
    DurableSensitivity, MemoryLifecycle, ProvenanceClass, RetentionPolicy,
    content_digest,
)
from backend.medar.embedding_provider import EmbeddingRequest
from backend.medar.memory_backup import create_memory_backup, restore_memory_backup
from backend.medar.memory_provenance import MemoryOrigin, MemoryProvenance
from backend.medar.sqlite_memory_store import MemoryScope, SQLiteMemoryStore
from backend.medar.vector_memory_index import SQLiteVectorMemoryIndex


NOW = datetime(2026, 10, 4, 18, 30, tzinfo=timezone.utc)
SCOPE = MemoryScope("tenant-a", "owner-a")


def _record():
    content = "Synthetic restored memory"
    return DurableMemoryRecord(
        "restore-memory", SCOPE.owner_id, SCOPE.tenant_id, DurableMemoryDomain.TECHNICAL,
        DurableMemoryType.FACT, content, content_digest(content), "synthetic_test", "restore-source",
        MemoryProvenance("restore-source", MemoryOrigin.OBSERVED, NOW, SCOPE.tenant_id, SCOPE.owner_id, "restore-context", 1.0),
        ProvenanceClass.DIRECT_OBSERVATION, 1.0, 0.8, DurableSensitivity.PUBLIC,
        NOW, NOW, None, RetentionPolicy.LONG_TERM, MemoryLifecycle.ACTIVE, 1,
    )


def _backup(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    memory_path = source / "memory.db"
    vector_path = source / "vectors.db"
    record = _record()
    provider = DeterministicEmbeddingProvider()
    request = EmbeddingRequest(provider.descriptor.model_id, record.content, record.sensitivity)
    embedding = provider.embed(request)
    with SQLiteMemoryStore(memory_path, read_only=False) as store:
        store.write(SCOPE, record)
    with SQLiteVectorMemoryIndex(vector_path, read_only=False) as index:
        index.write(SCOPE, record, request, embedding)
    payload = create_memory_backup(memory_path, vector_path, SCOPE, created_at=NOW)
    return source, memory_path, vector_path, record, embedding, payload


def test_restore_uses_new_directory_and_validates_memory_vector_and_metadata(tmp_path):
    source, source_memory, source_vector, record, embedding, payload = _backup(tmp_path)
    original_memory_hash = hashlib.sha256(source_memory.read_bytes()).hexdigest()
    original_vector_hash = hashlib.sha256(source_vector.read_bytes()).hexdigest()
    destination = tmp_path / "isolated-restore"

    restored = restore_memory_backup(payload, destination)

    assert restored.destination == destination
    assert restored.destination != source
    assert hashlib.sha256(source_memory.read_bytes()).hexdigest() == original_memory_hash
    assert hashlib.sha256(source_vector.read_bytes()).hexdigest() == original_vector_hash
    with SQLiteMemoryStore(restored.memory_database) as store:
        assert store.get(SCOPE, record.memory_id) == record
        assert store.get(MemoryScope("tenant-a", "other-owner"), record.memory_id) is None
    with SQLiteVectorMemoryIndex(restored.vector_index) as index:
        hits = index.search(SCOPE, embedding)
        assert [(hit.memory_id, hit.memory_version) for hit in hits] == [(record.memory_id, 1)]
        assert index.search(MemoryScope("other-tenant", "owner-a"), embedding) == ()
    metadata = json.loads(restored.metadata.read_bytes())
    assert metadata["backup_id"] == restored.backup_id
    assert metadata["scope"] == {"tenant_id": "tenant-a", "owner_id": "owner-a"}
    assert metadata["provenance"][0]["source_id"] == "restore-source"
    assert metadata["index_metadata"]["mapping_count"] == 1
    assert not restored.execution_authorized
    assert not restored.production_restore_authorized


def test_restore_refuses_existing_destination_without_modifying_it(tmp_path):
    _, _, _, _, _, payload = _backup(tmp_path)
    destination = tmp_path / "existing"
    destination.mkdir()
    marker = destination / "keep.txt"
    marker.write_text("unchanged", encoding="utf-8")
    with pytest.raises(FileExistsError, match="must not already exist"):
        restore_memory_backup(payload, destination)
    assert marker.read_text(encoding="utf-8") == "unchanged"
