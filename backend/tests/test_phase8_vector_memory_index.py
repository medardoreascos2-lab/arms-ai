"""R106D scoped durable vector mapping and failure containment tests."""

import sqlite3
from dataclasses import replace
from datetime import datetime, timezone

import pytest

from backend.medar.deterministic_embedding import DeterministicEmbeddingProvider
from backend.medar.durable_memory_record import (
    DurableMemoryDomain, DurableMemoryRecord, DurableMemoryType,
    DurableSensitivity, MemoryLifecycle, ProvenanceClass, RetentionPolicy,
    content_digest,
)
from backend.medar.embedding_provider import EmbeddingRequest, EmbeddingResult
from backend.medar.memory_provenance import MemoryOrigin, MemoryProvenance
from backend.medar.sqlite_memory_store import MemoryScope
from backend.medar.vector_memory_index import SQLiteVectorMemoryIndex


NOW = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)
SCOPE = MemoryScope("tenant-a", "owner-a")


def _record(sensitivity=DurableSensitivity.PUBLIC):
    content = "Synthetic public technical memory"
    return DurableMemoryRecord(
        "memory-1", "owner-a", "tenant-a", DurableMemoryDomain.TECHNICAL,
        DurableMemoryType.FACT, content, content_digest(content),
        "synthetic_test", "synthetic-source",
        MemoryProvenance("synthetic-source", MemoryOrigin.OBSERVED, NOW, "tenant-a", "owner-a", "synthetic-context", 0.9),
        ProvenanceClass.DIRECT_OBSERVATION, 0.9, 0.7, sensitivity,
        NOW, NOW, None, RetentionPolicy.LONG_TERM, MemoryLifecycle.ACTIVE, 1,
    )


def _embedding(record=None):
    record = record or _record()
    provider = DeterministicEmbeddingProvider()
    request = EmbeddingRequest(provider.descriptor.model_id, record.content, record.sensitivity)
    return request, provider.embed(request)


def test_public_vector_mapping_persists_with_scope_model_version_and_hash(tmp_path):
    path = tmp_path / "vectors.db"
    record = _record()
    request, embedding = _embedding(record)
    with SQLiteVectorMemoryIndex(path, read_only=False) as index:
        index.write(SCOPE, record, request, embedding)
        with pytest.raises(sqlite3.IntegrityError):
            index.write(SCOPE, record, request, embedding)
    with SQLiteVectorMemoryIndex(path) as index:
        hits = index.search(SCOPE, embedding)
        assert len(hits) == 1
        assert hits[0].memory_id == record.memory_id
        assert hits[0].memory_version == record.version
        assert hits[0].content_hash == record.content_hash
        assert hits[0].embedding_model_id == embedding.model_id
        assert hits[0].embedding_version == embedding.version
        assert hits[0].cosine_score == pytest.approx(1.0)
        assert hits[0].semantic_quality_validated is False
        assert index.search(MemoryScope("tenant-b", "owner-a"), embedding) == ()
        assert index.search(MemoryScope("tenant-a", "owner-b"), embedding) == ()
        with pytest.raises(PermissionError, match="read-only"):
            index.write(SCOPE, record, request, embedding)


def test_sensitive_and_mismatched_embedding_inputs_cause_zero_vector_writes(tmp_path):
    path = tmp_path / "vectors.db"
    record = _record()
    request, embedding = _embedding(record)
    with SQLiteVectorMemoryIndex(path, read_only=False) as index:
        with pytest.raises(PermissionError, match="public"):
            index.write(SCOPE, replace(record, sensitivity=DurableSensitivity.INTERNAL), request, embedding)
        with pytest.raises(PermissionError, match="scope"):
            index.write(MemoryScope("other", "owner-a"), record, request, embedding)
        with pytest.raises(ValueError, match="input"):
            index.write(SCOPE, record, EmbeddingRequest(request.model_id, "different", DurableSensitivity.PUBLIC), embedding)
        assert index.search(SCOPE, embedding) == ()


def test_corrupt_vector_and_schema_mismatch_fail_on_restart(tmp_path):
    path = tmp_path / "vectors.db"
    record = _record()
    request, embedding = _embedding(record)
    with SQLiteVectorMemoryIndex(path, read_only=False) as index:
        index.write(SCOPE, record, request, embedding)
    connection = sqlite3.connect(path)
    connection.execute("UPDATE vectors SET vector_json = '[NaN]'")
    connection.commit()
    connection.close()
    with pytest.raises(ValueError, match="corrupt"):
        SQLiteVectorMemoryIndex(path)
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA user_version = 99")
    connection.close()
    with pytest.raises(ValueError, match="schema"):
        SQLiteVectorMemoryIndex(path)


def test_vector_migration_checksum_tampering_fails_closed(tmp_path):
    path = tmp_path / "vectors.db"
    with SQLiteVectorMemoryIndex(path, read_only=False):
        pass
    connection = sqlite3.connect(path)
    connection.execute("UPDATE vector_migrations SET checksum = 'wrong'")
    connection.commit()
    connection.close()
    with pytest.raises(ValueError, match="checksum"):
        SQLiteVectorMemoryIndex(path)


def test_vector_norm_overflow_is_rejected_before_write_or_search(tmp_path):
    path = tmp_path / "vectors.db"
    record = _record()
    request, embedding = _embedding(record)
    huge = EmbeddingResult(embedding.provider_id, embedding.model_id, embedding.version, (1e308,) * 16)
    with SQLiteVectorMemoryIndex(path, read_only=False) as index:
        with pytest.raises(ValueError, match="invalid"):
            index.write(SCOPE, record, request, huge)
        with pytest.raises(ValueError, match="nonzero"):
            index.search(SCOPE, huge)
        assert index.search(SCOPE, embedding) == ()
