"""Isolated SQLite store for synthetic encrypted MEDAR envelopes only."""

import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from backend.medar.encrypted_memory_envelope import EncryptedMemoryEnvelope
from backend.medar.sqlite_memory_store import MemoryScope


_SCHEMA_SQL = (
    "CREATE TABLE envelope_migrations (version INTEGER PRIMARY KEY, checksum TEXT NOT NULL)",
    "CREATE TABLE encrypted_envelopes (tenant_id TEXT NOT NULL, owner_id TEXT NOT NULL, memory_id TEXT NOT NULL, memory_version INTEGER NOT NULL, envelope BLOB NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY (tenant_id, owner_id, memory_id, memory_version))",
)
_SCHEMA_CHECKSUM = hashlib.sha256("\n".join(_SCHEMA_SQL).encode("utf-8")).hexdigest()


class SQLiteEncryptedMemoryStore:
    def __init__(self, path: Path, *, read_only: bool = True):
        if not isinstance(path, Path):
            raise TypeError("path must be pathlib.Path")
        self._read_only = read_only
        resolved = path.resolve()
        if read_only:
            self._connection = sqlite3.connect("file:" + quote(resolved.as_posix(), safe="/:") + "?mode=ro", uri=True)
        else:
            resolved.parent.mkdir(parents=True, exist_ok=True)
            self._connection = sqlite3.connect(str(resolved))
        try:
            self._connection.execute("PRAGMA trusted_schema = OFF")
            if not read_only:
                self._connection.execute("PRAGMA journal_mode = WAL")
            self._verify_or_initialize()
        except Exception:
            self._connection.close()
            raise

    def _verify_or_initialize(self) -> None:
        version = self._connection.execute("PRAGMA user_version").fetchone()[0]
        if version == 0 and not self._read_only:
            try:
                self._connection.execute("BEGIN IMMEDIATE")
                for statement in _SCHEMA_SQL:
                    self._connection.execute(statement)
                self._connection.execute("INSERT INTO envelope_migrations VALUES (1, ?)", (_SCHEMA_CHECKSUM,))
                self._connection.execute("PRAGMA user_version = 1")
                self._connection.commit()
            except Exception:
                self._connection.rollback()
                raise
        elif version != 1:
            raise ValueError("encrypted memory schema version mismatch")
        migration = self._connection.execute("SELECT checksum FROM envelope_migrations WHERE version = 1").fetchone()
        if migration is None or migration[0] != _SCHEMA_CHECKSUM:
            raise ValueError("encrypted memory schema checksum mismatch")
        integrity = self._connection.execute("PRAGMA integrity_check").fetchone()
        if integrity is None or integrity[0] != "ok":
            raise ValueError("encrypted memory integrity check failed")

    def write(self, scope: MemoryScope, envelope: EncryptedMemoryEnvelope) -> None:
        if self._read_only:
            raise PermissionError("encrypted memory store is read-only")
        if not isinstance(scope, MemoryScope) or not isinstance(envelope, EncryptedMemoryEnvelope):
            raise TypeError("scope and encrypted envelope are required")
        if scope.tenant_id != envelope.tenant_id or scope.owner_id != envelope.owner_id:
            raise PermissionError("encrypted memory scope mismatch")
        if not envelope.payload.local_test_only:
            raise PermissionError("only local-test encrypted envelope is supported")
        encoded = envelope.to_bytes()
        with self._connection:
            self._connection.execute(
                "INSERT INTO encrypted_envelopes VALUES (?, ?, ?, ?, ?, ?)",
                (scope.tenant_id, scope.owner_id, envelope.memory_id, envelope.version,
                 encoded, datetime.now(timezone.utc).isoformat()),
            )

    def get(self, scope: MemoryScope, memory_id: str, version: int) -> EncryptedMemoryEnvelope | None:
        if not isinstance(scope, MemoryScope) or not isinstance(memory_id, str) or not memory_id.strip():
            raise ValueError("scope and memory_id are required")
        if isinstance(version, bool) or not isinstance(version, int) or version < 1:
            raise ValueError("memory version must be positive")
        row = self._connection.execute(
            "SELECT envelope FROM encrypted_envelopes WHERE tenant_id = ? AND owner_id = ? AND memory_id = ? AND memory_version = ?",
            (scope.tenant_id, scope.owner_id, memory_id, version),
        ).fetchone()
        if row is None:
            return None
        envelope = EncryptedMemoryEnvelope.from_bytes(row[0])
        if (envelope.tenant_id, envelope.owner_id, envelope.memory_id, envelope.version) != (
            scope.tenant_id, scope.owner_id, memory_id, version
        ):
            raise ValueError("encrypted memory row scope mismatch")
        return envelope

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> "SQLiteEncryptedMemoryStore":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
