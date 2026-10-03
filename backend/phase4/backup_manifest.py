"""Canonical Phase 4 backup manifest contract without backup execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import hmac
import json
from pathlib import PurePosixPath
import re


BACKUP_MANIFEST_FORMAT = "arms.phase4.backup-manifest-json.v1"
MAX_BACKUP_MANIFEST_BYTES = 65_536
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class BackupArtifactKind(str, Enum):
    DATABASE_SNAPSHOT = "DATABASE_SNAPSHOT"
    CONFIG_IDENTITIES = "CONFIG_IDENTITIES"
    AUDIT_CHAIN = "AUDIT_CHAIN"
    RESEARCH_REGISTRY = "RESEARCH_REGISTRY"
    PROFILE_REGISTRY = "PROFILE_REGISTRY"


def _canonical_utc(value: datetime, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _timestamp(value: datetime) -> str:
    return _canonical_utc(value, "created_at").isoformat().replace("+00:00", "Z")


def _relative_path(value: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise ValueError("relative_path must be a safe POSIX relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or str(path) != value or any(
        part in ("", ".", "..") or _SAFE_SEGMENT.fullmatch(part) is None
        for part in path.parts
    ):
        raise ValueError("relative_path must be a safe POSIX relative path")
    return value


def _reject_float(value: str) -> object:
    raise ValueError("backup manifest cannot contain floating-point values")


def _reject_constant(value: str) -> object:
    raise ValueError("backup manifest cannot contain non-finite values")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("backup manifest contains duplicate fields")
        result[key] = value
    return result


@dataclass(frozen=True)
class BackupArtifact:
    kind: BackupArtifactKind
    relative_path: str
    sha256: str
    size_bytes: int
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.kind, BackupArtifactKind):
            raise ValueError("kind must be a BackupArtifactKind")
        object.__setattr__(self, "relative_path", _relative_path(self.relative_path))
        if not isinstance(self.sha256, str) or _SHA256.fullmatch(self.sha256) is None:
            raise ValueError("sha256 must be a lowercase SHA-256 digest")
        if type(self.size_bytes) is not int or self.size_bytes < 0:
            raise ValueError("size_bytes must be a nonnegative integer")


def _manifest_document(manifest: "BackupManifest", *, include_id: bool) -> dict[str, object]:
    document: dict[str, object] = {
        "artifacts": [
            {
                "kind": artifact.kind.value,
                "relative_path": artifact.relative_path,
                "sha256": artifact.sha256,
                "size_bytes": artifact.size_bytes,
            }
            for artifact in manifest.artifacts
        ],
        "created_at": _timestamp(manifest.created_at),
        "database_schema_version": manifest.database_schema_version,
        "format": BACKUP_MANIFEST_FORMAT,
    }
    if include_id:
        document["backup_id"] = manifest.backup_id
    return document


def _json_bytes(document: dict[str, object]) -> bytes:
    encoded = json.dumps(
        document,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    if len(encoded) > MAX_BACKUP_MANIFEST_BYTES:
        raise ValueError("backup manifest exceeds size limit")
    return encoded


@dataclass(frozen=True)
class BackupManifest:
    database_schema_version: int
    created_at: datetime
    artifacts: tuple[BackupArtifact, ...]
    backup_id: str = field(init=False)
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)
    production_backup_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if type(self.database_schema_version) is not int or self.database_schema_version < 1:
            raise ValueError("database_schema_version must be positive")
        object.__setattr__(self, "created_at", _canonical_utc(self.created_at, "created_at"))
        if not isinstance(self.artifacts, tuple) or any(
            not isinstance(item, BackupArtifact) for item in self.artifacts
        ):
            raise ValueError("artifacts must be an immutable artifact tuple")
        if tuple(item.kind for item in self.artifacts) != tuple(BackupArtifactKind):
            raise ValueError("manifest must contain every artifact in canonical order")
        paths = tuple(item.relative_path for item in self.artifacts)
        if len(set(paths)) != len(paths):
            raise ValueError("artifact paths must be unique")
        digest = hashlib.sha256(_json_bytes(_manifest_document(self, include_id=False))).hexdigest()
        object.__setattr__(self, "backup_id", digest)


def serialize_backup_manifest(manifest: BackupManifest) -> bytes:
    if not isinstance(manifest, BackupManifest):
        raise ValueError("manifest must be a BackupManifest")
    return _json_bytes(_manifest_document(manifest, include_id=True))


def deserialize_backup_manifest(payload: bytes | str) -> BackupManifest:
    if isinstance(payload, str):
        encoded = payload.encode("utf-8")
    elif isinstance(payload, bytes):
        encoded = payload
    else:
        raise ValueError("backup manifest payload must be bytes or text")
    if len(encoded) > MAX_BACKUP_MANIFEST_BYTES:
        raise ValueError("backup manifest exceeds size limit")
    try:
        raw = json.loads(
            encoded.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, UnicodeEncodeError, json.JSONDecodeError) as exc:
        raise ValueError("backup manifest is not valid canonical JSON") from exc
    required = {
        "artifacts",
        "backup_id",
        "created_at",
        "database_schema_version",
        "format",
    }
    if not isinstance(raw, dict) or set(raw) != required:
        raise ValueError("backup manifest fields do not match the contract")
    if raw["format"] != BACKUP_MANIFEST_FORMAT:
        raise ValueError("unsupported backup manifest format")
    if not isinstance(raw["artifacts"], list):
        raise ValueError("backup manifest artifacts must be a list")
    artifacts = []
    for item in raw["artifacts"]:
        if not isinstance(item, dict) or set(item) != {
            "kind", "relative_path", "sha256", "size_bytes"
        }:
            raise ValueError("backup artifact fields do not match the contract")
        try:
            kind = BackupArtifactKind(item["kind"])
        except (TypeError, ValueError) as exc:
            raise ValueError("backup artifact kind is invalid") from exc
        artifacts.append(BackupArtifact(
            kind,
            item["relative_path"],
            item["sha256"],
            item["size_bytes"],
        ))
    created_raw = raw["created_at"]
    if not isinstance(created_raw, str) or not created_raw.endswith("Z"):
        raise ValueError("created_at must be canonical UTC")
    try:
        created_at = datetime.fromisoformat(created_raw[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError("created_at must be canonical UTC") from exc
    manifest = BackupManifest(
        raw["database_schema_version"],
        created_at,
        tuple(artifacts),
    )
    supplied_id = raw["backup_id"]
    if (
        not isinstance(supplied_id, str)
        or _SHA256.fullmatch(supplied_id) is None
        or not hmac.compare_digest(manifest.backup_id, supplied_id)
        or serialize_backup_manifest(manifest) != encoded
    ):
        raise ValueError("backup manifest identity or canonical payload mismatch")
    return manifest
