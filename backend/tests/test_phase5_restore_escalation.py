"""R60B isolated database restore escalation rehearsal."""

from contextlib import closing
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sqlite3

import pytest

from backend.phase5 import (
    AppRollbackStatus,
    EncryptedRestoreEscalation,
    EphemeralStagingBackupKey,
    LocalEphemeralBackupCipher,
    RestoreEscalationPlan,
    StagingAppRollbackRehearsal,
    StagingBackupPayload,
    StagingReleaseArtifact,
    StagingRestorePolicy,
    StagingRuntimeSnapshot,
    create_encrypted_staging_backup,
)


NOW = datetime(2026, 10, 7, 14, tzinfo=timezone.utc)
KEY = bytes(range(32))
NONCE = bytes(reversed(range(32)))


def _canonical(document) -> bytes:
    return json.dumps(
        document, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _database(path: Path) -> bytes:
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute("PRAGMA user_version = 3")
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("CREATE TABLE tenants (tenant_id TEXT PRIMARY KEY)")
        connection.execute(
            "CREATE TABLE state (tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id), "
            "state_key TEXT NOT NULL, PRIMARY KEY (tenant_id, state_key))"
        )
        connection.executemany(
            "INSERT INTO tenants VALUES (?)", (("tenant-a",), ("tenant-b",))
        )
        connection.executemany(
            "INSERT INTO state VALUES (?, ?)",
            (("tenant-a", "risk-blocked"), ("tenant-b", "risk-blocked")),
        )
    return path.read_bytes()


def _audit(*, corrupt: bool = False) -> bytes:
    previous = "0" * 64
    entries = []
    for sequence, tenant in enumerate(("tenant-a", "tenant-b"), start=1):
        evidence = {
            "event": "RESTORE_CHECKPOINT",
            "previous_hash": previous,
            "sequence": sequence,
            "tenant_id": tenant,
        }
        current = hashlib.sha256(_canonical(evidence)).hexdigest()
        entries.append({**evidence, "hash": current})
        previous = current
    if corrupt:
        entries[-1]["previous_hash"] = "f" * 64
    return _canonical({"entries": entries, "tip": previous})


def _research() -> bytes:
    return _canonical({
        "dataset_sha256": "a" * 64,
        "evaluation_id": "phase5-r60b-evaluation",
        "strategy_sha256": "b" * 64,
    })


def _rollback(schema_version: int = 3):
    candidate = StagingReleaseArtifact(
        "phase5.60.0", 1, 2, ("api_reads",), ("worker.v2",)
    )
    current = StagingRuntimeSnapshot(
        "phase5.60.1", schema_version, ("api_reads", "research_queue"),
        ("worker.v2",), True,
    )
    return StagingAppRollbackRehearsal().rehearse(current, candidate)


def _cipher():
    key = EphemeralStagingBackupKey(KEY, local_test_enabled=True)
    return LocalEphemeralBackupCipher(
        key, local_test_enabled=True, nonce_factory=lambda size: NONCE
    )


def _archive(database: bytes, *, audit: bytes | None = None):
    payload = StagingBackupPayload(
        database=database,
        database_schema_version=3,
        audit_continuity=audit or _audit(),
        research_provenance=_research(),
        created_at=NOW,
    )
    cipher = _cipher()
    return create_encrypted_staging_backup(payload, cipher), cipher, payload


def _policy():
    return StagingRestorePolicy(3, timedelta(hours=1), NOW + timedelta(minutes=5))


def test_incompatible_app_rollback_escalates_to_verified_isolated_restore(tmp_path):
    source = tmp_path / "active" / "staging.sqlite3"
    source.parent.mkdir()
    database = _database(source)
    source_hash = hashlib.sha256(database).hexdigest()
    archive, cipher, payload = _archive(database)
    destination = tmp_path / "isolated-restore" / "restored.sqlite3"
    rollback = _rollback()

    report = EncryptedRestoreEscalation().rehearse(
        rollback,
        archive,
        cipher,
        _policy(),
        RestoreEscalationPlan(source, destination, ("tenant-a", "tenant-b")),
    )

    assert rollback.status is AppRollbackStatus.BLOCKED_SCHEMA
    assert source.resolve() != report.destination
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash
    assert hashlib.sha256(destination.read_bytes()).hexdigest() == source_hash
    assert report.payload_id == payload.payload_id
    assert report.database_sha256 == source_hash
    assert report.database_schema_version == 3
    assert report.tenants == ("tenant-a", "tenant-b")
    assert report.research_evaluation_id == "phase5-r60b-evaluation"
    assert all((
        report.backup_hash_verified,
        report.schema_verified,
        report.audit_chain_verified,
        report.tenant_isolation_verified,
        report.research_provenance_verified,
        report.active_source_unchanged,
    ))
    assert report.execution_authorized is False
    assert report.production_mutation_authorized is False
    assert report.production_restore_authorized is False
    assert report.live_store_overwrite_authorized is False


def test_restore_requires_schema_escalation_and_never_materializes_for_healthy_rollback(tmp_path):
    source = tmp_path / "active" / "staging.sqlite3"
    source.parent.mkdir()
    database = _database(source)
    archive, cipher, _ = _archive(database)
    compatible = _rollback(schema_version=2)
    destination = tmp_path / "isolated" / "restored.sqlite3"

    with pytest.raises(ValueError, match="blocked schema"):
        EncryptedRestoreEscalation().rehearse(
            compatible,
            archive,
            cipher,
            _policy(),
            RestoreEscalationPlan(source, destination, ("tenant-a", "tenant-b")),
        )

    assert destination.exists() is False
    assert source.read_bytes() == database


def test_existing_destination_is_never_overwritten(tmp_path):
    source = tmp_path / "active" / "staging.sqlite3"
    source.parent.mkdir()
    database = _database(source)
    archive, cipher, _ = _archive(database)
    destination = tmp_path / "isolated" / "restored.sqlite3"
    destination.parent.mkdir()
    destination.write_bytes(b"existing-isolated-evidence")

    with pytest.raises(FileExistsError, match="already exists"):
        EncryptedRestoreEscalation().rehearse(
            _rollback(),
            archive,
            cipher,
            _policy(),
            RestoreEscalationPlan(source, destination, ("tenant-a", "tenant-b")),
        )

    assert destination.read_bytes() == b"existing-isolated-evidence"
    assert source.read_bytes() == database


def test_invalid_audit_chain_fails_closed_and_cleans_isolated_staging(tmp_path):
    source = tmp_path / "active" / "staging.sqlite3"
    source.parent.mkdir()
    database = _database(source)
    archive, cipher, _ = _archive(database, audit=_audit(corrupt=True))
    destination = tmp_path / "isolated" / "restored.sqlite3"

    with pytest.raises(ValueError, match="audit continuity sequence"):
        EncryptedRestoreEscalation().rehearse(
            _rollback(),
            archive,
            cipher,
            _policy(),
            RestoreEscalationPlan(source, destination, ("tenant-a", "tenant-b")),
        )

    assert destination.exists() is False
    assert source.read_bytes() == database
    assert list(destination.parent.glob(".restore-*.sqlite3")) == []
