"""Scoped, append-only SQLite storage for non-sensitive MEDAR memory.

Write mode is explicit. No production encryption is available, so personal or
sensitive records are rejected rather than persisted in plaintext.
"""

import hashlib
import json
import sqlite3
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Protocol
from urllib.parse import quote

from backend.medar.durable_memory_record import (
    DurableMemoryDomain, DurableMemoryRecord, DurableMemoryType,
    DurableSensitivity, MemoryLifecycle, ProvenanceClass, RetentionPolicy,
)
from backend.medar.memory_provenance import MemoryOrigin, MemoryProvenance


_SCHEMA_VERSION = 1
_SCHEMA_SQL = (
    "CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, checksum TEXT NOT NULL, applied_at TEXT NOT NULL)",
    "CREATE TABLE memory_versions (tenant_id TEXT NOT NULL, owner_id TEXT NOT NULL, memory_id TEXT NOT NULL, version INTEGER NOT NULL, status TEXT NOT NULL, domain TEXT NOT NULL, sensitivity TEXT NOT NULL, expires_at TEXT, content TEXT NOT NULL, record_json TEXT NOT NULL, written_at TEXT NOT NULL, PRIMARY KEY (tenant_id, owner_id, memory_id, version))",
    "CREATE INDEX memory_scope_status_idx ON memory_versions (tenant_id, owner_id, status, domain, written_at)",
)
_SCHEMA_CHECKSUM = hashlib.sha256("\n".join(_SCHEMA_SQL).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class MemoryScope:
    tenant_id: str
    owner_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.tenant_id, str) or not self.tenant_id.strip():
            raise ValueError("tenant_id is required")
        if not isinstance(self.owner_id, str) or not self.owner_id.strip():
            raise ValueError("owner_id is required")


class MemoryStore(Protocol):
    def write(self, scope: MemoryScope, record: DurableMemoryRecord) -> None: ...
    def get(self, scope: MemoryScope, memory_id: str) -> DurableMemoryRecord | None: ...
    def search(self, scope: MemoryScope, query: str, domains: tuple[DurableMemoryDomain, ...], limit: int = 10) -> tuple[DurableMemoryRecord, ...]: ...
    def history(self, scope: MemoryScope, memory_id: str) -> tuple[DurableMemoryRecord, ...]: ...
    def supersede(self, scope: MemoryScope, memory_id: str) -> DurableMemoryRecord: ...
    def expire(self, scope: MemoryScope, memory_id: str) -> DurableMemoryRecord: ...
    def retract(self, scope: MemoryScope, memory_id: str) -> DurableMemoryRecord: ...


def _encode(record: DurableMemoryRecord) -> str:
    values = dict(record.__dict__)
    for key in ("domain", "memory_type", "provenance_class", "sensitivity", "retention_policy", "status"):
        values[key] = values[key].value
    for key in ("created_at", "observed_at", "expires_at"):
        values[key] = values[key].isoformat() if values[key] is not None else None
    source = dict(record.provenance.__dict__)
    source["origin"] = source["origin"].value
    source["recorded_at"] = source["recorded_at"].isoformat()
    values["provenance"] = source
    return json.dumps(values, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _decode(raw: str) -> DurableMemoryRecord:
    try:
        values = json.loads(raw)
        source = values["provenance"]
        values["provenance"] = MemoryProvenance(
            source["source_id"], MemoryOrigin(source["origin"]),
            datetime.fromisoformat(source["recorded_at"]), source["tenant_id"],
            source["user_id"], source["context_id"], source["confidence"],
        )
        for key, kind in (
            ("domain", DurableMemoryDomain), ("memory_type", DurableMemoryType),
            ("provenance_class", ProvenanceClass), ("sensitivity", DurableSensitivity),
            ("retention_policy", RetentionPolicy), ("status", MemoryLifecycle),
        ):
            values[key] = kind(values[key])
        for key in ("created_at", "observed_at", "expires_at"):
            values[key] = datetime.fromisoformat(values[key]) if values[key] is not None else None
        return DurableMemoryRecord(**values)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("corrupt durable memory record") from exc


class SQLiteMemoryStore:
    def __init__(self, path: Path, *, read_only: bool = True, clock: Callable[[], datetime] | None = None):
        if not isinstance(path, Path):
            raise TypeError("path must be pathlib.Path")
        self._read_only = read_only
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        resolved = path.resolve()
        if read_only:
            self._connection = sqlite3.connect("file:" + quote(resolved.as_posix(), safe="/:" ) + "?mode=ro", uri=True)
        else:
            resolved.parent.mkdir(parents=True, exist_ok=True)
            self._connection = sqlite3.connect(str(resolved))
        self._connection.row_factory = sqlite3.Row
        try:
            self._connection.execute("PRAGMA foreign_keys = ON")
            self._connection.execute("PRAGMA trusted_schema = OFF")
            if not read_only:
                self._connection.execute("PRAGMA journal_mode = WAL")
            self._verify_or_migrate()
        except Exception:
            self._connection.close()
            raise

    def _now(self) -> datetime:
        value = self._clock()
        if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("memory clock must return an aware datetime")
        return value.astimezone(timezone.utc)

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> "SQLiteMemoryStore":
        return self

    def __exit__(self, _type, _value, _traceback) -> None:
        self.close()

    def _verify_or_migrate(self) -> None:
        version = self._connection.execute("PRAGMA user_version").fetchone()[0]
        if version == 0 and not self._read_only:
            try:
                self._connection.execute("BEGIN IMMEDIATE")
                for statement in _SCHEMA_SQL:
                    self._connection.execute(statement)
                self._connection.execute(
                    "INSERT INTO schema_migrations VALUES (?, ?, ?)",
                    (_SCHEMA_VERSION, _SCHEMA_CHECKSUM, self._now().isoformat()),
                )
                self._connection.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")
                self._connection.commit()
            except Exception:
                self._connection.rollback()
                raise
        elif version != _SCHEMA_VERSION:
            raise ValueError("memory schema version mismatch")
        migration = self._connection.execute(
            "SELECT checksum FROM schema_migrations WHERE version = ?", (_SCHEMA_VERSION,)
        ).fetchone()
        if migration is None or migration[0] != _SCHEMA_CHECKSUM:
            raise ValueError("memory migration checksum mismatch")
        integrity = self._connection.execute("PRAGMA integrity_check").fetchone()
        if integrity is None or integrity[0] != "ok":
            raise ValueError("memory database integrity check failed")
        last_versions: dict[tuple[str, str, str], int] = {}
        for row in self._connection.execute(
            "SELECT * FROM memory_versions ORDER BY tenant_id, owner_id, memory_id, version"
        ):
            record = self._decode_row(row)
            key = (record.tenant_id, record.owner_id, record.memory_id)
            expected = last_versions.get(key, 0) + 1
            if record.version != expected:
                raise ValueError("memory version history is incomplete")
            last_versions[key] = record.version

    @staticmethod
    def _decode_row(row: sqlite3.Row) -> DurableMemoryRecord:
        record = _decode(row["record_json"])
        expected = (
            record.tenant_id, record.owner_id, record.memory_id, record.version,
            record.status.value, record.domain.value, record.sensitivity.value,
            record.expires_at.astimezone(timezone.utc).isoformat() if record.expires_at else None,
            record.content,
        )
        actual = tuple(row[key] for key in (
            "tenant_id", "owner_id", "memory_id", "version", "status", "domain",
            "sensitivity", "expires_at", "content",
        ))
        if actual != expected:
            raise ValueError("memory row metadata does not match record")
        return record

    def _ensure_writable(self) -> None:
        if self._read_only:
            raise PermissionError("memory store is read-only")

    @staticmethod
    def _ensure_scope(scope: MemoryScope, record: DurableMemoryRecord) -> None:
        if record.tenant_id != scope.tenant_id or record.owner_id != scope.owner_id:
            raise PermissionError("memory scope mismatch")

    def _insert(self, record: DurableMemoryRecord) -> None:
        self._connection.execute(
            "INSERT INTO memory_versions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                record.tenant_id, record.owner_id, record.memory_id, record.version,
                record.status.value, record.domain.value, record.sensitivity.value,
                record.expires_at.astimezone(timezone.utc).isoformat() if record.expires_at else None,
                record.content, _encode(record), self._now().isoformat(),
            ),
        )

    def write(self, scope: MemoryScope, record: DurableMemoryRecord) -> None:
        self._ensure_writable()
        self._ensure_scope(scope, record)
        if record.domain is DurableMemoryDomain.WORKING or record.retention_policy is RetentionPolicy.SESSION:
            raise PermissionError("session memory cannot be durably stored")
        if record.sensitivity not in (DurableSensitivity.PUBLIC, DurableSensitivity.INTERNAL):
            raise PermissionError("production memory encryption unavailable for sensitive records")
        if record.version != 1:
            raise ValueError("initial memory version must be one")
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            if self.get(scope, record.memory_id) is not None:
                raise ValueError("memory_id already exists")
            self._insert(record)
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raise

    def get(self, scope: MemoryScope, memory_id: str) -> DurableMemoryRecord | None:
        row = self._connection.execute(
            "SELECT * FROM memory_versions WHERE tenant_id = ? AND owner_id = ? AND memory_id = ? ORDER BY version DESC LIMIT 1",
            (scope.tenant_id, scope.owner_id, memory_id),
        ).fetchone()
        if row is None:
            return None
        record = self._decode_row(row)
        self._ensure_scope(scope, record)
        return record

    def history(self, scope: MemoryScope, memory_id: str) -> tuple[DurableMemoryRecord, ...]:
        rows = self._connection.execute(
            "SELECT * FROM memory_versions WHERE tenant_id = ? AND owner_id = ? AND memory_id = ? ORDER BY version",
            (scope.tenant_id, scope.owner_id, memory_id),
        ).fetchall()
        records = tuple(self._decode_row(row) for row in rows)
        for record in records:
            self._ensure_scope(scope, record)
        return records

    def search(self, scope: MemoryScope, query: str, domains: tuple[DurableMemoryDomain, ...], limit: int = 10) -> tuple[DurableMemoryRecord, ...]:
        if not isinstance(query, str) or not query.strip() or not domains or any(not isinstance(d, DurableMemoryDomain) for d in domains):
            raise ValueError("search requires query and typed domains")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("search limit must be 1 to 100")
        escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        placeholders = ",".join("?" for _ in domains)
        sql = (
            "SELECT m.* FROM memory_versions m WHERE m.tenant_id = ? AND m.owner_id = ? "
            "AND m.version = (SELECT MAX(v.version) FROM memory_versions v WHERE v.tenant_id = m.tenant_id AND v.owner_id = m.owner_id AND v.memory_id = m.memory_id) "
            f"AND m.status = 'ACTIVE' AND m.domain IN ({placeholders}) "
            "AND (m.expires_at IS NULL OR m.expires_at > ?) "
            "AND m.content LIKE ? ESCAPE '\\' ORDER BY m.written_at DESC, m.memory_id LIMIT ?"
        )
        rows = self._connection.execute(
            sql,
            (scope.tenant_id, scope.owner_id, *(domain.value for domain in domains), self._now().isoformat(), f"%{escaped}%", limit),
        ).fetchall()
        records = tuple(self._decode_row(row) for row in rows)
        for record in records:
            self._ensure_scope(scope, record)
        return records

    def _transition(self, scope: MemoryScope, memory_id: str, status: MemoryLifecycle) -> DurableMemoryRecord:
        self._ensure_writable()
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            current = self.get(scope, memory_id)
            if current is None or current.status is not MemoryLifecycle.ACTIVE:
                raise ValueError("only active scoped memory can transition")
            updated = replace(current, version=current.version + 1, status=status)
            self._insert(updated)
            self._connection.commit()
            return updated
        except Exception:
            self._connection.rollback()
            raise

    def supersede(self, scope: MemoryScope, memory_id: str) -> DurableMemoryRecord:
        return self._transition(scope, memory_id, MemoryLifecycle.SUPERSEDED)

    def expire(self, scope: MemoryScope, memory_id: str) -> DurableMemoryRecord:
        return self._transition(scope, memory_id, MemoryLifecycle.EXPIRED)

    def retract(self, scope: MemoryScope, memory_id: str) -> DurableMemoryRecord:
        return self._transition(scope, memory_id, MemoryLifecycle.RETRACTED)
