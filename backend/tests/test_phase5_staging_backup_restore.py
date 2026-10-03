"""R56B isolated encrypted staging backup and restore rehearsal."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3

from backend.phase5.encrypted_backup import (
    EphemeralStagingBackupKey,
    LocalEphemeralBackupCipher,
    StagingBackupPayload,
    create_encrypted_staging_backup,
    open_encrypted_staging_backup,
)


NOW = datetime(2026, 10, 4, 6, 0, tzinfo=timezone.utc)
KEY_MATERIAL = bytes(range(31, -1, -1))
NONCE = bytes(range(32))


def _canonical(document):
    return json.dumps(
        document,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _create_database(path: Path):
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA user_version = 7")
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            "CREATE TABLE tenants (tenant_id TEXT PRIMARY KEY)"
        )
        connection.execute(
            "CREATE TABLE tenant_state ("
            "tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id), "
            "state_key TEXT NOT NULL, state_value TEXT NOT NULL, "
            "PRIMARY KEY (tenant_id, state_key))"
        )
        connection.execute(
            "CREATE TABLE outbox_events ("
            "event_id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL "
            "REFERENCES tenants(tenant_id), status TEXT NOT NULL, "
            "attempt_count INTEGER NOT NULL)"
        )
        connection.executemany(
            "INSERT INTO tenants VALUES (?)",
            (("tenant-a",), ("tenant-b",)),
        )
        connection.executemany(
            "INSERT INTO tenant_state VALUES (?, ?, ?)",
            (
                ("tenant-a", "portfolio", "flat"),
                ("tenant-a", "risk", "blocked"),
                ("tenant-b", "portfolio", "flat"),
            ),
        )
        connection.executemany(
            "INSERT INTO outbox_events VALUES (?, ?, ?, ?)",
            (
                ("event-a1", "tenant-a", "PENDING", 1),
                ("event-a2", "tenant-a", "DELIVERED", 1),
                ("event-b1", "tenant-b", "DEAD_LETTER", 3),
            ),
        )
    return path.read_bytes()


def _audit_continuity():
    previous = "0" * 64
    entries = []
    for sequence, tenant_id, event in (
        (1, "tenant-a", "STATE_SNAPSHOT"),
        (2, "tenant-b", "OUTBOX_CHECKPOINT"),
    ):
        evidence = {
            "event": event,
            "previous_hash": previous,
            "sequence": sequence,
            "tenant_id": tenant_id,
        }
        current = hashlib.sha256(_canonical(evidence)).hexdigest()
        entries.append({**evidence, "hash": current})
        previous = current
    return _canonical({"entries": entries, "tip": previous})


def _verify_audit_chain(payload):
    document = json.loads(payload)
    previous = "0" * 64
    for entry in document["entries"]:
        evidence = {key: entry[key] for key in (
            "event",
            "previous_hash",
            "sequence",
            "tenant_id",
        )}
        assert evidence["previous_hash"] == previous
        assert entry["hash"] == hashlib.sha256(_canonical(evidence)).hexdigest()
        previous = entry["hash"]
    assert document["tip"] == previous


def test_encrypted_backup_restores_to_separate_destination_with_all_evidence(tmp_path):
    source_directory = tmp_path / "source"
    archive_directory = tmp_path / "archive"
    restore_directory = tmp_path / "restore"
    source_directory.mkdir()
    archive_directory.mkdir()
    restore_directory.mkdir()
    source_database = source_directory / "staging.sqlite3"
    source_bytes = _create_database(source_database)
    audit = _audit_continuity()
    research = _canonical({
        "dataset_sha256": "a" * 64,
        "evaluation_id": "phase5-r56b-evaluation",
        "strategy_sha256": "b" * 64,
    })
    payload = StagingBackupPayload(
        database=source_bytes,
        database_schema_version=7,
        audit_continuity=audit,
        research_provenance=research,
        created_at=NOW,
    )
    key = EphemeralStagingBackupKey(KEY_MATERIAL, local_test_enabled=True)
    cipher = LocalEphemeralBackupCipher(
        key,
        local_test_enabled=True,
        nonce_factory=lambda size: NONCE,
    )
    archive = archive_directory / "phase5-r56b.encrypted.json"
    archive.write_bytes(create_encrypted_staging_backup(payload, cipher))

    restored_payload = open_encrypted_staging_backup(archive.read_bytes(), cipher)
    restored_database = restore_directory / "restored.sqlite3"
    with restored_database.open("xb") as handle:
        handle.write(restored_payload.database)

    assert source_database.resolve() != restored_database.resolve()
    assert source_database.read_bytes() == source_bytes
    assert restored_database.read_bytes() == source_bytes
    assert dict(restored_payload.hash_manifest) == {
        "audit_continuity_sha256": hashlib.sha256(audit).hexdigest(),
        "database_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "research_provenance_sha256": hashlib.sha256(research).hexdigest(),
    }

    with sqlite3.connect(f"file:{restored_database}?mode=ro", uri=True) as restored:
        restored.execute("PRAGMA query_only = ON")
        assert restored.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        assert restored.execute("PRAGMA user_version").fetchone()[0] == 7
        assert restored.execute("SELECT COUNT(*) FROM tenant_state").fetchone()[0] == 3
        assert restored.execute("SELECT COUNT(*) FROM outbox_events").fetchone()[0] == 3
        assert restored.execute(
            "SELECT state_key, state_value FROM tenant_state "
            "WHERE tenant_id = ? ORDER BY state_key",
            ("tenant-a",),
        ).fetchall() == [("portfolio", "flat"), ("risk", "blocked")]
        assert restored.execute(
            "SELECT state_key, state_value FROM tenant_state "
            "WHERE tenant_id = ? ORDER BY state_key",
            ("tenant-b",),
        ).fetchall() == [("portfolio", "flat")]
        assert restored.execute(
            "SELECT event_id, status, attempt_count FROM outbox_events "
            "ORDER BY event_id"
        ).fetchall() == [
            ("event-a1", "PENDING", 1),
            ("event-a2", "DELIVERED", 1),
            ("event-b1", "DEAD_LETTER", 3),
        ]

    _verify_audit_chain(restored_payload.audit_continuity)
    assert json.loads(restored_payload.research_provenance) == {
        "dataset_sha256": "a" * 64,
        "evaluation_id": "phase5-r56b-evaluation",
        "strategy_sha256": "b" * 64,
    }
    assert restored_payload.execution_authorized is False
    assert restored_payload.production_mutation_authorized is False
    assert restored_payload.production_backup_authorized is False
