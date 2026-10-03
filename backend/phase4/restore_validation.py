"""Restore completed local backups into isolated test destinations and validate them."""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
from uuid import uuid4

from .backup_manifest import BackupArtifactKind
from .local_backup import (
    BACKUP_COMPLETION_FILENAME,
    BACKUP_MANIFEST_FILENAME,
    LocalBackupResult,
    _sqlite_schema_version,
    load_completed_local_backup,
)


_SQL_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_CHUNK_SIZE = 1024 * 1024


class RestoreDestinationMode(str, Enum):
    ISOLATED_TEST = "ISOLATED_TEST"


@dataclass(frozen=True)
class RestoreTableExpectation:
    table_name: str
    expected_row_count: int
    tenant_column: str | None = None
    expected_tenants: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.table_name, str) or _SQL_IDENTIFIER.fullmatch(
            self.table_name
        ) is None:
            raise ValueError("table_name must be a safe SQL identifier")
        if type(self.expected_row_count) is not int or self.expected_row_count < 0:
            raise ValueError("expected_row_count must be nonnegative")
        if self.tenant_column is None:
            if self.expected_tenants:
                raise ValueError("expected_tenants require a tenant_column")
            return
        if not isinstance(self.tenant_column, str) or _SQL_IDENTIFIER.fullmatch(
            self.tenant_column
        ) is None:
            raise ValueError("tenant_column must be a safe SQL identifier")
        if (
            not isinstance(self.expected_tenants, tuple)
            or not self.expected_tenants
            or any(not isinstance(item, str) or not item or len(item) > 128 for item in self.expected_tenants)
            or tuple(sorted(set(self.expected_tenants))) != self.expected_tenants
        ):
            raise ValueError("expected_tenants must be a sorted unique nonempty tuple")


@dataclass(frozen=True)
class RestoreValidationPlan:
    expected_database_schema_version: int
    tables: tuple[RestoreTableExpectation, ...]

    def __post_init__(self) -> None:
        if (
            type(self.expected_database_schema_version) is not int
            or self.expected_database_schema_version < 1
        ):
            raise ValueError("expected_database_schema_version must be positive")
        if not isinstance(self.tables, tuple) or not self.tables or any(
            not isinstance(item, RestoreTableExpectation) for item in self.tables
        ):
            raise ValueError("tables must be a nonempty immutable expectation tuple")
        names = tuple(item.table_name for item in self.tables)
        if len(set(names)) != len(names):
            raise ValueError("table expectations must be unique")
        if not any(item.tenant_column is not None for item in self.tables):
            raise ValueError("at least one tenant isolation expectation is required")


@dataclass(frozen=True)
class RestoreTableEvidence:
    table_name: str
    row_count: int
    tenants: tuple[str, ...]


@dataclass(frozen=True)
class RestoreValidationReport:
    backup_id: str
    restore_directory: Path
    database_schema_version: int
    tables: tuple[RestoreTableEvidence, ...]
    audit_event_count: int
    research_record_count: int
    checksums_verified: bool
    tenant_isolation_verified: bool
    audit_continuity_verified: bool
    research_provenance_verified: bool
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)
    live_store_overwrite_authorized: bool = field(default=False, init=False)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json_object(path: Path, maximum_bytes: int) -> dict[str, object]:
    if path.stat().st_size > maximum_bytes:
        raise ValueError("restore metadata exceeds size limit")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("restore metadata is not valid JSON") from exc
    if not isinstance(value, dict):
        raise ValueError("restore metadata must be a JSON object")
    return value


def _linked_hash_count(
    path: Path,
    *,
    list_name: str,
    hash_name: str,
    previous_name: str,
    source_name: str | None,
    maximum_bytes: int,
) -> int:
    document = _read_json_object(path, maximum_bytes)
    if set(document) != {list_name} or not isinstance(document[list_name], list):
        raise ValueError(f"{list_name} metadata does not match the restore contract")
    previous = None
    seen = set()
    for index, item in enumerate(document[list_name]):
        required = {hash_name, previous_name}
        if source_name is not None:
            required.add(source_name)
        if not isinstance(item, dict) or set(item) != required:
            raise ValueError(f"{list_name} entry does not match the restore contract")
        current_hash = item[hash_name]
        previous_hash = item[previous_name]
        if not isinstance(current_hash, str) or _SHA256.fullmatch(current_hash) is None:
            raise ValueError(f"{list_name} entry hash is invalid")
        if current_hash in seen:
            raise ValueError(f"{list_name} entry hash is duplicated")
        if index == 0:
            if previous_hash is not None:
                raise ValueError(f"{list_name} initial continuity is invalid")
        elif previous_hash != previous:
            raise ValueError(f"{list_name} continuity is invalid")
        if source_name is not None:
            source_hash = item[source_name]
            if not isinstance(source_hash, str) or _SHA256.fullmatch(source_hash) is None:
                raise ValueError(f"{list_name} source provenance is invalid")
        seen.add(current_hash)
        previous = current_hash
    return len(seen)


class BackupRestoreValidator:
    """Local, test-only restore boundary. Existing destinations are never replaced."""

    execution_authorized = False
    production_mutation_authorized = False
    live_store_overwrite_authorized = False

    def __init__(
        self,
        destination_root: Path,
        *,
        mode: RestoreDestinationMode,
        maximum_metadata_bytes: int = 67_108_864,
    ):
        if not isinstance(destination_root, Path):
            raise ValueError("destination_root must be a Path")
        if mode is not RestoreDestinationMode.ISOLATED_TEST:
            raise ValueError("restore mode must be ISOLATED_TEST")
        if type(maximum_metadata_bytes) is not int or maximum_metadata_bytes < 1:
            raise ValueError("maximum_metadata_bytes must be positive")
        self._destination_root = destination_root
        self._maximum_metadata_bytes = maximum_metadata_bytes

    @staticmethod
    def _safe_artifact_path(backup: LocalBackupResult, relative_path: str) -> Path:
        source = backup.backup_directory / relative_path
        if source.is_symlink():
            raise ValueError("backup artifacts cannot be symbolic links")
        resolved = source.resolve(strict=True)
        if not resolved.is_file() or not resolved.is_relative_to(backup.backup_directory):
            raise ValueError("backup artifact escaped its package")
        return resolved

    def _verify_backup_artifacts(self, backup: LocalBackupResult) -> dict[BackupArtifactKind, Path]:
        verified = {}
        for artifact in backup.manifest.artifacts:
            source = self._safe_artifact_path(backup, artifact.relative_path)
            if source.stat().st_size != artifact.size_bytes:
                raise ValueError("backup artifact size mismatch")
            if _sha256_file(source) != artifact.sha256:
                raise ValueError("backup artifact checksum mismatch")
            verified[artifact.kind] = source
        return verified

    @staticmethod
    def _copy_new(source: Path, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with source.open("rb") as reader, destination.open("xb") as writer:
            shutil.copyfileobj(reader, writer, _CHUNK_SIZE)
            writer.flush()
            os.fsync(writer.fileno())

    @staticmethod
    def _cleanup_staging(path: Path, root: Path) -> None:
        resolved = path.resolve(strict=False)
        if resolved.parent != root or not resolved.name.startswith(".restore-"):
            raise RuntimeError("refusing to clean an unexpected restore path")
        if resolved.exists():
            shutil.rmtree(resolved)

    @staticmethod
    def _validate_database(
        database: Path,
        plan: RestoreValidationPlan,
    ) -> tuple[RestoreTableEvidence, ...]:
        evidence = []
        with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as connection:
            connection.execute("PRAGMA query_only = ON")
            if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("restored database integrity check failed")
            if connection.execute("PRAGMA foreign_key_check").fetchall():
                raise ValueError("restored database foreign key isolation failed")
            schema_version = _sqlite_schema_version(connection)
            if schema_version != plan.expected_database_schema_version:
                raise ValueError("restored database schema version mismatch")
            for item in plan.tables:
                count = connection.execute(
                    f'SELECT COUNT(*) FROM "{item.table_name}"'
                ).fetchone()[0]
                if count != item.expected_row_count:
                    raise ValueError(f"restored row count mismatch for {item.table_name}")
                tenants: tuple[str, ...] = ()
                if item.tenant_column is not None:
                    rows = connection.execute(
                        f'SELECT DISTINCT "{item.tenant_column}" '
                        f'FROM "{item.table_name}" ORDER BY "{item.tenant_column}"'
                    ).fetchall()
                    if any(
                        len(row) != 1 or not isinstance(row[0], str) or not row[0]
                        for row in rows
                    ):
                        raise ValueError("restored tenant identity is invalid")
                    tenants = tuple(row[0] for row in rows)
                    if tenants != item.expected_tenants:
                        raise ValueError(f"restored tenant isolation mismatch for {item.table_name}")
                evidence.append(RestoreTableEvidence(item.table_name, count, tenants))
        return tuple(evidence)

    def restore_and_validate(
        self,
        backup_directory: Path,
        plan: RestoreValidationPlan,
    ) -> RestoreValidationReport:
        if not isinstance(plan, RestoreValidationPlan):
            raise ValueError("plan must be a RestoreValidationPlan")
        if self._destination_root.is_symlink():
            raise ValueError("destination_root cannot be a symbolic link")
        self._destination_root.mkdir(parents=True, exist_ok=True)
        root = self._destination_root.resolve(strict=True)
        if not isinstance(backup_directory, Path) or backup_directory.is_symlink():
            raise ValueError("backup_directory must be a non-symlink Path")
        for filename in (BACKUP_MANIFEST_FILENAME, BACKUP_COMPLETION_FILENAME):
            if (backup_directory / filename).is_symlink():
                raise ValueError("backup control files cannot be symbolic links")
        backup = load_completed_local_backup(backup_directory)
        if backup.backup_directory == root or backup.backup_directory.is_relative_to(root):
            raise ValueError("backup source cannot reside under restore destination")
        if backup.manifest.database_schema_version != plan.expected_database_schema_version:
            raise ValueError("manifest schema version does not match restore plan")
        sources = self._verify_backup_artifacts(backup)
        staging = root / f".restore-{uuid4().hex}.incomplete"
        staging.mkdir()
        try:
            for artifact in backup.manifest.artifacts:
                self._copy_new(sources[artifact.kind], staging / artifact.relative_path)
                if _sha256_file(staging / artifact.relative_path) != artifact.sha256:
                    raise ValueError("restored artifact checksum mismatch")
            self._copy_new(
                backup.backup_directory / BACKUP_MANIFEST_FILENAME,
                staging / BACKUP_MANIFEST_FILENAME,
            )
            self._copy_new(
                backup.backup_directory / BACKUP_COMPLETION_FILENAME,
                staging / BACKUP_COMPLETION_FILENAME,
            )
            for filename in (BACKUP_MANIFEST_FILENAME, BACKUP_COMPLETION_FILENAME):
                if _sha256_file(staging / filename) != _sha256_file(
                    backup.backup_directory / filename
                ):
                    raise ValueError("restored control file checksum mismatch")
            database = staging / next(
                item.relative_path
                for item in backup.manifest.artifacts
                if item.kind is BackupArtifactKind.DATABASE_SNAPSHOT
            )
            tables = self._validate_database(database, plan)
            audit_count = _linked_hash_count(
                staging / next(
                    item.relative_path
                    for item in backup.manifest.artifacts
                    if item.kind is BackupArtifactKind.AUDIT_CHAIN
                ),
                list_name="events",
                hash_name="event_hash",
                previous_name="previous_event_hash",
                source_name=None,
                maximum_bytes=self._maximum_metadata_bytes,
            )
            research_count = _linked_hash_count(
                staging / next(
                    item.relative_path
                    for item in backup.manifest.artifacts
                    if item.kind is BackupArtifactKind.RESEARCH_REGISTRY
                ),
                list_name="records",
                hash_name="record_hash",
                previous_name="previous_record_hash",
                source_name="source_hash",
                maximum_bytes=self._maximum_metadata_bytes,
            )
            final = root / f"restore-{backup.manifest.backup_id}"
            if final.exists():
                raise FileExistsError("validated restore identity already exists")
            os.replace(staging, final)
            return RestoreValidationReport(
                backup_id=backup.manifest.backup_id,
                restore_directory=final,
                database_schema_version=plan.expected_database_schema_version,
                tables=tables,
                audit_event_count=audit_count,
                research_record_count=research_count,
                checksums_verified=True,
                tenant_isolation_verified=True,
                audit_continuity_verified=True,
                research_provenance_verified=True,
            )
        except Exception:
            self._cleanup_staging(staging, root)
            raise
