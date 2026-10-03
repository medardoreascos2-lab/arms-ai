"""R44B tests for local-only atomic backup creation."""

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sqlite3

import pytest

from backend.phase4.backup_manifest import BackupArtifactKind
from backend.phase4.local_backup import (
    BACKUP_ARTIFACT_PATHS,
    BACKUP_COMPLETION_FILENAME,
    BACKUP_MANIFEST_FILENAME,
    LocalBackupRunner,
    LocalBackupSources,
    load_completed_local_backup,
)


NOW = datetime(2026, 10, 4, 0, 0, tzinfo=timezone.utc)


def source_files(root: Path) -> LocalBackupSources:
    root.mkdir(parents=True)
    database = root / "phase4.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA user_version = 3")
        connection.execute("CREATE TABLE tenant_state (tenant_id TEXT PRIMARY KEY, value TEXT)")
        connection.execute("INSERT INTO tenant_state VALUES ('tenant-a', 'stable')")
    paths = {}
    for name in (
        "config_identities",
        "audit_chain",
        "research_registry",
        "profile_registry",
    ):
        path = root / f"{name}.json"
        path.write_text(json.dumps({"kind": name}), encoding="utf-8")
        paths[name] = path
    return LocalBackupSources(database=database, **paths)


def runner(destination: Path, clock=lambda: NOW) -> LocalBackupRunner:
    return LocalBackupRunner(
        destination,
        retention_policy="LOCAL_7_DAYS",
        retention_period=timedelta(days=7),
        clock=clock,
    )


def test_runner_creates_consistent_checksummed_completed_local_backup(tmp_path):
    sources = source_files(tmp_path / "source")
    result = runner(tmp_path / "backups").run(sources, database_schema_version=3)

    assert result.backup_directory.name == result.manifest.backup_id
    assert (result.backup_directory / BACKUP_MANIFEST_FILENAME).is_file()
    assert (result.backup_directory / BACKUP_COMPLETION_FILENAME).is_file()
    assert not any(path.name.endswith(".tmp") for path in result.backup_directory.iterdir())
    assert result.completion.retain_until == NOW + timedelta(days=7)
    assert result.cloud_upload_authorized is False

    for artifact in result.manifest.artifacts:
        payload = (result.backup_directory / artifact.relative_path).read_bytes()
        assert hashlib.sha256(payload).hexdigest() == artifact.sha256
        assert len(payload) == artifact.size_bytes

    snapshot = result.backup_directory / BACKUP_ARTIFACT_PATHS[
        BackupArtifactKind.DATABASE_SNAPSHOT
    ]
    with sqlite3.connect(snapshot) as restored:
        assert restored.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        assert restored.execute("PRAGMA user_version").fetchone()[0] == 3
        assert restored.execute("SELECT * FROM tenant_state").fetchall() == [
            ("tenant-a", "stable")
        ]


def test_completed_backup_loader_verifies_directory_manifest_and_marker(tmp_path):
    result = runner(tmp_path / "backups").run(
        source_files(tmp_path / "source"), database_schema_version=3
    )
    loaded = load_completed_local_backup(result.backup_directory)
    assert loaded.manifest == result.manifest
    assert loaded.completion == result.completion


def test_schema_mismatch_fails_without_completion_or_incomplete_directory(tmp_path):
    destination = tmp_path / "backups"
    with pytest.raises(ValueError, match="schema version"):
        runner(destination).run(source_files(tmp_path / "source"), database_schema_version=4)
    assert list(destination.iterdir()) == []


def test_missing_supporting_artifact_fails_before_staging(tmp_path):
    sources = source_files(tmp_path / "source")
    sources.audit_chain.unlink()
    destination = tmp_path / "backups"
    with pytest.raises(FileNotFoundError):
        runner(destination).run(sources, database_schema_version=3)
    assert list(destination.iterdir()) == []


def test_sources_under_destination_are_rejected(tmp_path):
    destination = tmp_path / "backups"
    sources = source_files(destination / "source")
    with pytest.raises(ValueError, match="under the destination"):
        runner(destination).run(sources, database_schema_version=3)


def test_tampered_manifest_or_missing_atomic_marker_is_not_loadable(tmp_path):
    result = runner(tmp_path / "backups").run(
        source_files(tmp_path / "source"), database_schema_version=3
    )
    marker = result.backup_directory / BACKUP_COMPLETION_FILENAME
    marker.unlink()
    with pytest.raises(FileNotFoundError):
        load_completed_local_backup(result.backup_directory)

    marker.write_bytes(b"{}")
    with pytest.raises(ValueError, match="fields"):
        load_completed_local_backup(result.backup_directory)


def test_duplicate_identity_never_overwrites_completed_backup(tmp_path):
    sources = source_files(tmp_path / "source")
    destination = tmp_path / "backups"
    first = runner(destination).run(sources, database_schema_version=3)
    manifest_before = (first.backup_directory / BACKUP_MANIFEST_FILENAME).read_bytes()
    with pytest.raises(FileExistsError, match="already exists"):
        runner(destination).run(sources, database_schema_version=3)
    assert (first.backup_directory / BACKUP_MANIFEST_FILENAME).read_bytes() == manifest_before
    assert not any(path.name.startswith(".backup-") for path in destination.iterdir())


def test_runner_exposes_no_cloud_or_production_authority(tmp_path):
    item = runner(tmp_path / "backups")
    assert item.cloud_upload_authorized is False
    assert item.production_mutation_authorized is False
    assert item.execution_authorized is False
