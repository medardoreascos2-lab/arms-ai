"""R120C corruption drills prove memory recovery fails closed."""

import base64
from datetime import datetime, timezone
import hashlib
import json

import pytest

from backend.medar.durable_memory_record import (
    DurableMemoryDomain, DurableMemoryRecord, DurableMemoryType,
    DurableSensitivity, MemoryLifecycle, ProvenanceClass, RetentionPolicy,
    content_digest,
)
from backend.medar.memory_backup import create_memory_backup, restore_memory_backup
from backend.medar.memory_provenance import MemoryOrigin, MemoryProvenance
from backend.medar.sqlite_memory_store import MemoryScope, SQLiteMemoryStore
from backend.medar.vector_memory_index import SQLiteVectorMemoryIndex


NOW = datetime(2026, 10, 4, 19, tzinfo=timezone.utc)
SCOPE = MemoryScope("tenant-recovery", "owner-recovery")


def _canonical(value):
    return json.dumps(value, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")).encode()


def _rehash(document):
    core = dict(document)
    core.pop("backup_id", None)
    core["backup_id"] = hashlib.sha256(_canonical(core)).hexdigest()
    return _canonical(core)


def _payload(tmp_path):
    memory_path = tmp_path / "memory.db"
    vector_path = tmp_path / "vectors.db"
    content = "Synthetic recovery drill memory"
    record = DurableMemoryRecord(
        "recovery-memory", SCOPE.owner_id, SCOPE.tenant_id, DurableMemoryDomain.TECHNICAL,
        DurableMemoryType.FACT, content, content_digest(content), "synthetic_test", "recovery-source",
        MemoryProvenance("recovery-source", MemoryOrigin.OBSERVED, NOW, SCOPE.tenant_id, SCOPE.owner_id, "recovery-context", 1.0),
        ProvenanceClass.DIRECT_OBSERVATION, 1.0, 0.7, DurableSensitivity.PUBLIC,
        NOW, NOW, None, RetentionPolicy.LONG_TERM, MemoryLifecycle.ACTIVE, 1,
    )
    with SQLiteMemoryStore(memory_path, read_only=False) as store:
        store.write(SCOPE, record)
    with SQLiteVectorMemoryIndex(vector_path, read_only=False):
        pass
    return create_memory_backup(memory_path, vector_path, SCOPE, created_at=NOW)


@pytest.mark.parametrize("artifact", ("memory_database", "vector_index"))
def test_corrupt_database_or_vector_index_is_rejected_without_restore(tmp_path, artifact):
    document = json.loads(_payload(tmp_path))
    corrupt = b"not-a-sqlite-database"
    document["artifacts"][artifact] = base64.b64encode(corrupt).decode("ascii")
    document["hashes"][artifact + "_sha256"] = hashlib.sha256(corrupt).hexdigest()
    payload = _rehash(document)
    destination = tmp_path / "restore"

    with pytest.raises(ValueError, match="corrupt|database|schema"):
        restore_memory_backup(payload, destination)

    assert not destination.exists()
    assert not list(tmp_path.glob(".restore.*.restore"))


def test_partial_backup_is_rejected_without_publishing_any_files(tmp_path):
    document = json.loads(_payload(tmp_path))
    del document["artifacts"]["vector_index"]
    payload = _rehash(document)
    destination = tmp_path / "restore"

    with pytest.raises(ValueError, match="structure"):
        restore_memory_backup(payload, destination)

    assert not destination.exists()
    assert not any(path.name == "restore" or path.name.startswith(".restore.") for path in tmp_path.iterdir())
