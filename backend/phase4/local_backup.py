"""Local development backup runner for an isolated SQLite Phase 4 store."""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
from types import MappingProxyType
from typing import Callable
from uuid import uuid4

from .backup_manifest import (
    BackupArtifact,
    BackupArtifactKind,
    BackupManifest,
    deserialize_backup_manifest,
    serialize_backup_manifest,
)


BACKUP_COMPLETION_FORMAT = "arms.phase4.backup-completion-json.v1"
BACKUP_MANIFEST_FILENAME = "manifest.json"
BACKUP_COMPLETION_FILENAME = "COMPLETED.json"
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_CHUNK_SIZE = 1024 * 1024


BACKUP_ARTIFACT_PATHS = MappingProxyType({
    BackupArtifactKind.DATABASE_SNAPSHOT: "database/snapshot.sqlite3",
    BackupArtifactKind.CONFIG_IDENTITIES: "metadata/config-identities.json",
    BackupArtifactKind.AUDIT_CHAIN: "audit/audit-chain.json",
    BackupArtifactKind.RESEARCH_REGISTRY: "research/research-registry.json",
    BackupArtifactKind.PROFILE_REGISTRY: "profiles/profile-registry.json",
})


def _sqlite_schema_version(connection: sqlite3.Connection) -> int:
    """Read a declared SQLite schema version without guessing or downgrading."""

    pragma_version = connection.execute("PRAGMA user_version").fetchone()[0]
    if type(pragma_version) is not int or pragma_version < 0:
        raise ValueError("SQLite user_version is invalid")
    metadata_table = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' "
        "AND name = 'phase3_store_metadata'"
    ).fetchone()
    if metadata_table is None:
        return pragma_version
    row = connection.execute(
        "SELECT schema_version FROM phase3_store_metadata WHERE singleton = 1"
    ).fetchone()
    if row is None or len(row) != 1 or type(row[0]) is not int or row[0] < 1:
        raise ValueError("Phase 3 schema metadata is invalid")
    metadata_version = row[0]
    if pragma_version not in (0, metadata_version):
        raise ValueError("SQLite schema version declarations conflict")
    return metadata_version


def _utc(value: datetime, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _timestamp(value: datetime) -> str:
    return _utc(value, "timestamp").isoformat().replace("+00:00", "Z")


def _parse_timestamp(value: object, name: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError(f"{name} must be canonical UTC")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError(f"{name} must be canonical UTC") from exc
    if _timestamp(parsed) != value:
        raise ValueError(f"{name} must be canonical UTC")
    return parsed


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class LocalBackupSources:
    database: Path
    config_identities: Path
    audit_chain: Path
    research_registry: Path
    profile_registry: Path

    def artifact_source(self, kind: BackupArtifactKind) -> Path:
        sources = {
            BackupArtifactKind.CONFIG_IDENTITIES: self.config_identities,
            BackupArtifactKind.AUDIT_CHAIN: self.audit_chain,
            BackupArtifactKind.RESEARCH_REGISTRY: self.research_registry,
            BackupArtifactKind.PROFILE_REGISTRY: self.profile_registry,
        }
        if kind not in sources:
            raise ValueError("database snapshots require the SQLite backup path")
        return sources[kind]


@dataclass(frozen=True)
class BackupCompletionMarker:
    backup_id: str
    manifest_sha256: str
    completed_at: datetime
    retain_until: datetime
    retention_policy: str
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)
    cloud_upload_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        for name in ("backup_id", "manifest_sha256"):
            value = getattr(self, name)
            if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
                raise ValueError(f"{name} must be a lowercase SHA-256 digest")
        completed = _utc(self.completed_at, "completed_at")
        retain = _utc(self.retain_until, "retain_until")
        if retain <= completed:
            raise ValueError("retain_until must follow completed_at")
        if not isinstance(self.retention_policy, str) or _IDENTIFIER.fullmatch(
            self.retention_policy
        ) is None:
            raise ValueError("retention_policy must be a safe identifier")
        object.__setattr__(self, "completed_at", completed)
        object.__setattr__(self, "retain_until", retain)


def serialize_backup_completion(marker: BackupCompletionMarker) -> bytes:
    if not isinstance(marker, BackupCompletionMarker):
        raise ValueError("marker must be a BackupCompletionMarker")
    return json.dumps(
        {
            "backup_id": marker.backup_id,
            "completed_at": _timestamp(marker.completed_at),
            "format": BACKUP_COMPLETION_FORMAT,
            "manifest_sha256": marker.manifest_sha256,
            "retain_until": _timestamp(marker.retain_until),
            "retention_policy": marker.retention_policy,
        },
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def deserialize_backup_completion(payload: bytes | str) -> BackupCompletionMarker:
    encoded = payload.encode("utf-8") if isinstance(payload, str) else payload
    if not isinstance(encoded, bytes) or len(encoded) > 16_384:
        raise ValueError("backup completion payload is invalid")
    try:
        raw = json.loads(encoded.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("backup completion payload is invalid") from exc
    required = {
        "backup_id", "completed_at", "format", "manifest_sha256",
        "retain_until", "retention_policy",
    }
    if not isinstance(raw, dict) or set(raw) != required:
        raise ValueError("backup completion fields do not match the contract")
    if raw["format"] != BACKUP_COMPLETION_FORMAT:
        raise ValueError("unsupported backup completion format")
    marker = BackupCompletionMarker(
        raw["backup_id"],
        raw["manifest_sha256"],
        _parse_timestamp(raw["completed_at"], "completed_at"),
        _parse_timestamp(raw["retain_until"], "retain_until"),
        raw["retention_policy"],
    )
    if serialize_backup_completion(marker) != encoded:
        raise ValueError("backup completion payload must be canonical")
    return marker


@dataclass(frozen=True)
class LocalBackupResult:
    backup_directory: Path
    manifest: BackupManifest
    completion: BackupCompletionMarker
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)
    cloud_upload_authorized: bool = field(default=False, init=False)


class LocalBackupRunner:
    """Create a complete local package; this class has no remote or production mode."""

    execution_authorized = False
    production_mutation_authorized = False
    cloud_upload_authorized = False

    def __init__(
        self,
        destination_root: Path,
        *,
        retention_policy: str,
        retention_period: timedelta,
        maximum_artifact_bytes: int = 1_073_741_824,
        clock: Callable[[], datetime] | None = None,
    ):
        if not isinstance(destination_root, Path):
            raise ValueError("destination_root must be a Path")
        if not isinstance(retention_policy, str) or _IDENTIFIER.fullmatch(retention_policy) is None:
            raise ValueError("retention_policy must be a safe identifier")
        if not isinstance(retention_period, timedelta) or retention_period <= timedelta(0):
            raise ValueError("retention_period must be positive")
        if type(maximum_artifact_bytes) is not int or maximum_artifact_bytes < 1:
            raise ValueError("maximum_artifact_bytes must be positive")
        self._destination_root = destination_root
        self._retention_policy = retention_policy
        self._retention_period = retention_period
        self._maximum_artifact_bytes = maximum_artifact_bytes
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def _validate_sources(self, sources: LocalBackupSources, root: Path) -> tuple[Path, ...]:
        if not isinstance(sources, LocalBackupSources):
            raise ValueError("sources must be LocalBackupSources")
        raw_paths = (
            sources.database,
            sources.config_identities,
            sources.audit_chain,
            sources.research_registry,
            sources.profile_registry,
        )
        if any(not isinstance(path, Path) for path in raw_paths):
            raise ValueError("all backup sources must be Paths")
        if any(path.is_symlink() for path in raw_paths):
            raise ValueError("backup sources cannot be symbolic links")
        resolved = tuple(path.resolve(strict=True) for path in raw_paths)
        if any(not path.is_file() for path in resolved):
            raise ValueError("every backup source must be a file")
        if len(set(resolved)) != len(resolved):
            raise ValueError("backup source paths must be unique")
        if any(path == root or path.is_relative_to(root) for path in resolved):
            raise ValueError("backup sources cannot reside under the destination root")
        return resolved

    def _sqlite_snapshot(self, source: Path, destination: Path, schema_version: int) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as source_db:
            source_db.execute("PRAGMA query_only = ON")
            actual_version = _sqlite_schema_version(source_db)
            if actual_version != schema_version:
                raise ValueError("source database schema version does not match")
            with closing(sqlite3.connect(str(destination))) as target_db:
                source_db.backup(target_db)
                target_db.commit()
                if target_db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                    raise RuntimeError("SQLite backup integrity check failed")
                if _sqlite_schema_version(target_db) != schema_version:
                    raise RuntimeError("SQLite backup schema version changed")
        if destination.stat().st_size > self._maximum_artifact_bytes:
            raise ValueError("database snapshot exceeds artifact size limit")

    def _copy_stable_file(self, source: Path, destination: Path) -> None:
        before = source.stat()
        if before.st_size > self._maximum_artifact_bytes:
            raise ValueError("backup source exceeds artifact size limit")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with source.open("rb") as reader, destination.open("xb") as writer:
            shutil.copyfileobj(reader, writer, _CHUNK_SIZE)
            writer.flush()
            os.fsync(writer.fileno())
        after = source.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise RuntimeError("backup source changed during capture")

    @staticmethod
    def _write_new(path: Path, payload: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())

    @staticmethod
    def _cleanup_staging(path: Path, root: Path) -> None:
        resolved = path.resolve(strict=False)
        if resolved.parent != root or not resolved.name.startswith(".backup-"):
            raise RuntimeError("refusing to clean an unexpected backup path")
        if resolved.exists():
            shutil.rmtree(resolved)

    def run(self, sources: LocalBackupSources, *, database_schema_version: int) -> LocalBackupResult:
        if type(database_schema_version) is not int or database_schema_version < 1:
            raise ValueError("database_schema_version must be positive")
        if self._destination_root.is_symlink():
            raise ValueError("destination_root cannot be a symbolic link")
        self._destination_root.mkdir(parents=True, exist_ok=True)
        root = self._destination_root.resolve(strict=True)
        source_paths = self._validate_sources(sources, root)
        created_at = _utc(self._clock(), "backup clock")
        staging = root / f".backup-{uuid4().hex}.incomplete"
        staging.mkdir()
        try:
            database_destination = staging / BACKUP_ARTIFACT_PATHS[
                BackupArtifactKind.DATABASE_SNAPSHOT
            ]
            self._sqlite_snapshot(source_paths[0], database_destination, database_schema_version)
            for index, kind in enumerate(tuple(BackupArtifactKind)[1:], start=1):
                self._copy_stable_file(
                    source_paths[index],
                    staging / BACKUP_ARTIFACT_PATHS[kind],
                )
            artifacts = tuple(
                BackupArtifact(
                    kind,
                    BACKUP_ARTIFACT_PATHS[kind],
                    _sha256_file(staging / BACKUP_ARTIFACT_PATHS[kind]),
                    (staging / BACKUP_ARTIFACT_PATHS[kind]).stat().st_size,
                )
                for kind in BackupArtifactKind
            )
            manifest = BackupManifest(database_schema_version, created_at, artifacts)
            manifest_payload = serialize_backup_manifest(manifest)
            self._write_new(staging / BACKUP_MANIFEST_FILENAME, manifest_payload)
            completed_at = _utc(self._clock(), "backup clock")
            if completed_at < created_at:
                raise ValueError("backup clock moved backwards")
            completion = BackupCompletionMarker(
                manifest.backup_id,
                _sha256_bytes(manifest_payload),
                completed_at,
                completed_at + self._retention_period,
                self._retention_policy,
            )
            temporary_marker = staging / f".{BACKUP_COMPLETION_FILENAME}.tmp"
            self._write_new(temporary_marker, serialize_backup_completion(completion))
            os.replace(temporary_marker, staging / BACKUP_COMPLETION_FILENAME)
            final = root / manifest.backup_id
            if final.exists():
                raise FileExistsError("backup identity already exists")
            os.replace(staging, final)
            return LocalBackupResult(final, manifest, completion)
        except Exception:
            self._cleanup_staging(staging, root)
            raise


def load_completed_local_backup(directory: Path) -> LocalBackupResult:
    if not isinstance(directory, Path) or directory.is_symlink():
        raise ValueError("backup directory must be a non-symlink Path")
    resolved = directory.resolve(strict=True)
    manifest_payload = (resolved / BACKUP_MANIFEST_FILENAME).read_bytes()
    completion_payload = (resolved / BACKUP_COMPLETION_FILENAME).read_bytes()
    manifest = deserialize_backup_manifest(manifest_payload)
    completion = deserialize_backup_completion(completion_payload)
    if resolved.name != manifest.backup_id or completion.backup_id != manifest.backup_id:
        raise ValueError("backup directory identity does not match manifest")
    if completion.manifest_sha256 != _sha256_bytes(manifest_payload):
        raise ValueError("backup completion manifest checksum mismatch")
    return LocalBackupResult(resolved, manifest, completion)
