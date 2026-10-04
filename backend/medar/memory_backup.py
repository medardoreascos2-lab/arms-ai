"""Scoped, local Phase 8 memory backup format with fail-closed validation."""

import base64
import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from backend.medar.sqlite_memory_store import MemoryScope


BACKUP_FORMAT = "ARMS_MEDAR_MEMORY_BACKUP_V1"
_ARTIFACT_NAMES = ("memory_database", "vector_index")


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _require_aware(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("backup timestamp must be timezone-aware")
    return value.astimezone(timezone.utc)


def _open_read_only(path: Path) -> sqlite3.Connection:
    if not isinstance(path, Path):
        raise TypeError("database path must be pathlib.Path")
    resolved = path.resolve(strict=True)
    connection = sqlite3.connect(f"file:{resolved.as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        connection.close()
        raise ValueError("source database integrity check failed")
    return connection


def _scoped_snapshot(path: Path, scope: MemoryScope, *, vector: bool) -> bytes:
    table = "vectors" if vector else "memory_versions"
    migration = "vector_migrations" if vector else "schema_migrations"
    with _open_read_only(path) as source:
        version = source.execute("PRAGMA user_version").fetchone()[0]
        if version != 1:
            raise ValueError("unsupported memory backup schema version")
        schema_rows = source.execute(
            "SELECT type, name, sql FROM sqlite_master WHERE sql IS NOT NULL "
            "AND (name IN (?, ?) OR (type = 'index' AND tbl_name = ?)) ORDER BY type DESC, name",
            (migration, table, table),
        ).fetchall()
        tables = {row["name"] for row in schema_rows if row["type"] == "table"}
        if tables != {migration, table}:
            raise ValueError("required memory backup schema is missing")
        destination = sqlite3.connect(":memory:")
        try:
            for row in schema_rows:
                if row["type"] == "table":
                    destination.execute(row["sql"])
            migration_rows = source.execute(f"SELECT * FROM {migration} ORDER BY version").fetchall()
            for row in migration_rows:
                placeholders = ",".join("?" for _ in row.keys())
                destination.execute(f"INSERT INTO {migration} VALUES ({placeholders})", tuple(row))
            scoped_rows = source.execute(
                f"SELECT * FROM {table} WHERE tenant_id = ? AND owner_id = ? ORDER BY memory_id, "
                + ("memory_version, embedding_model_id, embedding_version" if vector else "version"),
                (scope.tenant_id, scope.owner_id),
            ).fetchall()
            for row in scoped_rows:
                placeholders = ",".join("?" for _ in row.keys())
                destination.execute(f"INSERT INTO {table} VALUES ({placeholders})", tuple(row))
            for row in schema_rows:
                if row["type"] == "index":
                    destination.execute(row["sql"])
            destination.execute(f"PRAGMA user_version = {version}")
            destination.commit()
            if destination.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("scoped backup snapshot integrity check failed")
            return destination.serialize()
        finally:
            destination.close()


def _inspect_snapshots(memory_bytes: bytes, vector_bytes: bytes, scope: MemoryScope) -> tuple[dict, tuple[dict, ...], dict]:
    memory = sqlite3.connect(":memory:")
    vector = sqlite3.connect(":memory:")
    memory.row_factory = sqlite3.Row
    vector.row_factory = sqlite3.Row
    try:
        memory.deserialize(memory_bytes)
        vector.deserialize(vector_bytes)
        if memory.execute("PRAGMA integrity_check").fetchone()[0] != "ok" or vector.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("backup database integrity check failed")
        memory_version = memory.execute("PRAGMA user_version").fetchone()[0]
        vector_version = vector.execute("PRAGMA user_version").fetchone()[0]
        if (memory_version, vector_version) != (1, 1):
            raise ValueError("backup schema version mismatch")
        memory_checksum = memory.execute("SELECT checksum FROM schema_migrations WHERE version = 1").fetchone()
        vector_checksum = vector.execute("SELECT checksum FROM vector_migrations WHERE version = 1").fetchone()
        if memory_checksum is None or vector_checksum is None:
            raise ValueError("backup migration metadata is missing")
        records: dict[tuple[str, int], str] = {}
        provenance: list[dict] = []
        memory_rows = memory.execute("SELECT * FROM memory_versions ORDER BY memory_id, version").fetchall()
        for row in memory_rows:
            if (row["tenant_id"], row["owner_id"]) != (scope.tenant_id, scope.owner_id):
                raise PermissionError("backup contains memory outside requested scope")
            try:
                record = json.loads(row["record_json"])
                source = record["provenance"]
            except (KeyError, TypeError, json.JSONDecodeError) as exc:
                raise ValueError("backup memory provenance is corrupt") from exc
            if (record.get("tenant_id"), record.get("owner_id")) != (scope.tenant_id, scope.owner_id):
                raise PermissionError("backup record identity mismatch")
            if (source.get("tenant_id"), source.get("user_id")) != (scope.tenant_id, scope.owner_id):
                raise PermissionError("backup provenance identity mismatch")
            if _digest(record["content"].encode("utf-8")) != record.get("content_hash"):
                raise ValueError("backup memory content hash mismatch")
            key = (row["memory_id"], row["version"])
            records[key] = record["content_hash"]
            provenance.append({
                "memory_id": row["memory_id"], "version": row["version"],
                "source_id": source["source_id"], "origin": source["origin"],
                "recorded_at": source["recorded_at"], "context_id": source["context_id"],
                "confidence": source["confidence"],
            })
        models: dict[tuple[str, str, int], int] = {}
        vector_rows = vector.execute("SELECT * FROM vectors ORDER BY memory_id, memory_version").fetchall()
        for row in vector_rows:
            if (row["tenant_id"], row["owner_id"]) != (scope.tenant_id, scope.owner_id):
                raise PermissionError("backup contains vector outside requested scope")
            if records.get((row["memory_id"], row["memory_version"])) != row["content_hash"]:
                raise ValueError("backup vector mapping has no matching memory version")
            try:
                values = json.loads(row["vector_json"])
            except json.JSONDecodeError as exc:
                raise ValueError("backup vector mapping is corrupt") from exc
            if not isinstance(values, list) or len(values) != row["dimensions"] or _digest(row["vector_json"].encode("utf-8")) != row["vector_hash"]:
                raise ValueError("backup vector metadata mismatch")
            key = (row["embedding_model_id"], row["embedding_version"], row["dimensions"])
            models[key] = models.get(key, 0) + 1
        schema = {
            "memory_user_version": memory_version,
            "memory_migration_checksum": memory_checksum[0],
            "vector_user_version": vector_version,
            "vector_migration_checksum": vector_checksum[0],
        }
        index_metadata = {
            "mapping_count": len(vector_rows),
            "models": [
                {"model_id": key[0], "version": key[1], "dimensions": key[2], "mapping_count": count}
                for key, count in sorted(models.items())
            ],
        }
        return schema, tuple(provenance), index_metadata
    except sqlite3.DatabaseError as exc:
        raise ValueError("backup database is corrupt") from exc
    finally:
        memory.close()
        vector.close()


@dataclass(frozen=True)
class MemoryBackupBundle:
    backup_id: str
    created_at: datetime
    scope: MemoryScope
    memory_database: bytes
    vector_index: bytes
    schema: dict
    provenance: tuple[dict, ...]
    index_metadata: dict
    hashes: dict
    execution_authorized: bool = False
    production_restore_authorized: bool = False

    def __post_init__(self) -> None:
        _require_aware(self.created_at)
        if self.execution_authorized or self.production_restore_authorized:
            raise ValueError("memory backup grants no execution or production restore authority")


def create_memory_backup(memory_path: Path, vector_path: Path, scope: MemoryScope, *, created_at: datetime) -> bytes:
    if not isinstance(scope, MemoryScope):
        raise TypeError("memory backup requires a typed scope")
    created = _require_aware(created_at)
    memory_bytes = _scoped_snapshot(memory_path, scope, vector=False)
    vector_bytes = _scoped_snapshot(vector_path, scope, vector=True)
    schema, provenance, index_metadata = _inspect_snapshots(memory_bytes, vector_bytes, scope)
    metadata = {
        "schema": schema,
        "provenance": provenance,
        "index_metadata": index_metadata,
    }
    hashes = {
        "memory_database_sha256": _digest(memory_bytes),
        "vector_index_sha256": _digest(vector_bytes),
        "metadata_sha256": _digest(_canonical(metadata)),
    }
    core = {
        "format": BACKUP_FORMAT,
        "created_at": created.isoformat(),
        "scope": {"tenant_id": scope.tenant_id, "owner_id": scope.owner_id},
        **metadata,
        "hashes": hashes,
        "artifacts": {
            "memory_database": base64.b64encode(memory_bytes).decode("ascii"),
            "vector_index": base64.b64encode(vector_bytes).decode("ascii"),
        },
        "execution_authorized": False,
        "production_restore_authorized": False,
    }
    document = {**core, "backup_id": _digest(_canonical(core))}
    return _canonical(document)


def open_memory_backup(payload: bytes) -> MemoryBackupBundle:
    if not isinstance(payload, bytes) or not payload:
        raise TypeError("memory backup payload must be non-empty bytes")
    try:
        document = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("memory backup is not valid JSON") from exc
    if _canonical(document) != payload:
        raise ValueError("memory backup must use canonical encoding")
    backup_id = document.pop("backup_id", None)
    if backup_id != _digest(_canonical(document)):
        raise ValueError("memory backup identity mismatch")
    if document.get("format") != BACKUP_FORMAT:
        raise ValueError("memory backup format mismatch")
    if document.get("execution_authorized") or document.get("production_restore_authorized"):
        raise ValueError("memory backup authority flags must remain false")
    try:
        scope = MemoryScope(document["scope"]["tenant_id"], document["scope"]["owner_id"])
        memory_bytes = base64.b64decode(document["artifacts"]["memory_database"], validate=True)
        vector_bytes = base64.b64decode(document["artifacts"]["vector_index"], validate=True)
        created_at = datetime.fromisoformat(document["created_at"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("memory backup structure is invalid") from exc
    schema, provenance, index_metadata = _inspect_snapshots(memory_bytes, vector_bytes, scope)
    metadata = {"schema": schema, "provenance": provenance, "index_metadata": index_metadata}
    expected_hashes = {
        "memory_database_sha256": _digest(memory_bytes),
        "vector_index_sha256": _digest(vector_bytes),
        "metadata_sha256": _digest(_canonical(metadata)),
    }
    if document.get("hashes") != expected_hashes or document.get("schema") != schema or tuple(document.get("provenance", ())) != provenance or document.get("index_metadata") != index_metadata:
        raise ValueError("memory backup metadata or hash mismatch")
    return MemoryBackupBundle(
        backup_id, created_at, scope, memory_bytes, vector_bytes,
        schema, provenance, index_metadata, expected_hashes,
    )
