"""R44A tests for the canonical backup manifest contract."""

from datetime import datetime, timezone
import json

import pytest

from backend.phase4.backup_manifest import (
    BACKUP_MANIFEST_FORMAT,
    BackupArtifact,
    BackupArtifactKind,
    BackupManifest,
    deserialize_backup_manifest,
    serialize_backup_manifest,
)


CREATED = datetime(2026, 10, 3, 23, 30, tzinfo=timezone.utc)


def artifacts():
    return tuple(
        BackupArtifact(kind, f"artifacts/{kind.value.lower()}.bin", f"{index:064x}", index)
        for index, kind in enumerate(BackupArtifactKind, start=1)
    )


def manifest():
    return BackupManifest(3, CREATED, artifacts())


def test_manifest_requires_every_backup_domain_and_hash():
    item = manifest()
    assert tuple(artifact.kind for artifact in item.artifacts) == tuple(BackupArtifactKind)
    assert item.database_schema_version == 3
    assert len(item.backup_id) == 64
    assert item.production_backup_authorized is False
    assert item.execution_authorized is False


def test_manifest_round_trip_is_canonical_and_deterministic():
    first = manifest()
    encoded = serialize_backup_manifest(first)
    restored = deserialize_backup_manifest(encoded)
    assert restored == first
    assert restored.backup_id == first.backup_id
    assert serialize_backup_manifest(restored) == encoded
    assert json.loads(encoded)["format"] == BACKUP_MANIFEST_FORMAT


def test_content_or_timestamp_changes_manifest_identity():
    first = manifest()
    changed = list(artifacts())
    changed[0] = BackupArtifact(
        BackupArtifactKind.DATABASE_SNAPSHOT,
        changed[0].relative_path,
        "f" * 64,
        changed[0].size_bytes,
    )
    assert BackupManifest(3, CREATED, tuple(changed)).backup_id != first.backup_id
    assert BackupManifest(
        3,
        datetime(2026, 10, 3, 23, 31, tzinfo=timezone.utc),
        artifacts(),
    ).backup_id != first.backup_id


def test_missing_reordered_or_duplicate_artifact_paths_fail_closed():
    with pytest.raises(ValueError, match="every artifact"):
        BackupManifest(3, CREATED, artifacts()[:-1])
    with pytest.raises(ValueError, match="canonical order"):
        BackupManifest(3, CREATED, tuple(reversed(artifacts())))
    repeated = list(artifacts())
    repeated[1] = BackupArtifact(
        repeated[1].kind,
        repeated[0].relative_path,
        repeated[1].sha256,
        repeated[1].size_bytes,
    )
    with pytest.raises(ValueError, match="paths must be unique"):
        BackupManifest(3, CREATED, tuple(repeated))


@pytest.mark.parametrize(
    "path",
    ("../escape.bin", "/absolute.bin", "artifacts\\windows.bin", "artifacts//double.bin"),
)
def test_artifact_paths_must_be_safe_and_relative(path):
    with pytest.raises(ValueError, match="safe POSIX"):
        BackupArtifact(BackupArtifactKind.DATABASE_SNAPSHOT, path, "a" * 64, 1)


def test_invalid_schema_hash_size_and_timestamp_fail_closed():
    with pytest.raises(ValueError, match="positive"):
        BackupManifest(0, CREATED, artifacts())
    with pytest.raises(ValueError, match="SHA-256"):
        BackupArtifact(BackupArtifactKind.DATABASE_SNAPSHOT, "db.bin", "A" * 64, 1)
    with pytest.raises(ValueError, match="nonnegative"):
        BackupArtifact(BackupArtifactKind.DATABASE_SNAPSHOT, "db.bin", "a" * 64, -1)
    with pytest.raises(ValueError, match="timezone-aware"):
        BackupManifest(3, CREATED.replace(tzinfo=None), artifacts())


def test_tampered_or_noncanonical_serialized_manifest_is_rejected():
    document = json.loads(serialize_backup_manifest(manifest()))
    document["artifacts"][0]["size_bytes"] += 1
    tampered = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    with pytest.raises(ValueError, match="identity"):
        deserialize_backup_manifest(tampered)
    pretty = json.dumps(json.loads(serialize_backup_manifest(manifest())), indent=2)
    with pytest.raises(ValueError, match="canonical"):
        deserialize_backup_manifest(pretty)
