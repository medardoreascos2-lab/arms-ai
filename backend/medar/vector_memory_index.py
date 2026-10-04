"""Local SQLite vector mapping for public MEDAR memory only.

Vectors are append-oriented, tenant/user scoped, and kept separate from the
memory database. No semantic quality is claimed by this index.
"""

import hashlib
import json
import math
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol
from urllib.parse import quote

from backend.medar.durable_memory_record import DurableMemoryDomain, DurableMemoryRecord, DurableSensitivity, MemoryLifecycle
from backend.medar.embedding_provider import EmbeddingRequest, EmbeddingResult
from backend.medar.sqlite_memory_store import MemoryScope


_SCHEMA_VERSION = 1
_SCHEMA_SQL = (
    "CREATE TABLE vector_migrations (version INTEGER PRIMARY KEY, checksum TEXT NOT NULL, applied_at TEXT NOT NULL)",
    "CREATE TABLE vectors (tenant_id TEXT NOT NULL, owner_id TEXT NOT NULL, memory_id TEXT NOT NULL, memory_version INTEGER NOT NULL, content_hash TEXT NOT NULL, embedding_model_id TEXT NOT NULL, embedding_version TEXT NOT NULL, dimensions INTEGER NOT NULL, vector_json TEXT NOT NULL, vector_hash TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY (tenant_id, owner_id, memory_id, memory_version, embedding_model_id, embedding_version))",
    "CREATE INDEX vector_scope_model_idx ON vectors (tenant_id, owner_id, embedding_model_id, embedding_version)",
)
_SCHEMA_CHECKSUM = hashlib.sha256("\n".join(_SCHEMA_SQL).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class VectorMemoryHit:
    memory_id: str
    memory_version: int
    content_hash: str
    embedding_model_id: str
    embedding_version: str
    cosine_score: float
    semantic_quality_validated: bool = False

    def __post_init__(self) -> None:
        if self.semantic_quality_validated:
            raise ValueError("vector index cannot claim semantic quality")
        if not math.isfinite(self.cosine_score) or not -1.0 <= self.cosine_score <= 1.0:
            raise ValueError("cosine score must be finite between -1 and 1")


class VectorMemoryIndex(Protocol):
    def write(self, scope: MemoryScope, record: DurableMemoryRecord, request: EmbeddingRequest, embedding: EmbeddingResult) -> None: ...
    def search(self, scope: MemoryScope, query: EmbeddingResult, limit: int = 10) -> tuple[VectorMemoryHit, ...]: ...


def _vector_payload(vector: tuple[float, ...]) -> str:
    return json.dumps(vector, separators=(",", ":"), allow_nan=False)


def _vector_norm(vector: tuple[float, ...]) -> float:
    return math.sqrt(sum(value * value for value in vector))


class SQLiteVectorMemoryIndex:
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
        self._connection.row_factory = sqlite3.Row
        try:
            self._connection.execute("PRAGMA trusted_schema = OFF")
            if not read_only:
                self._connection.execute("PRAGMA journal_mode = WAL")
            self._verify_or_initialize()
        except Exception:
            self._connection.close()
            raise

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> "SQLiteVectorMemoryIndex":
        return self

    def __exit__(self, _type, _value, _traceback) -> None:
        self.close()

    def _verify_or_initialize(self) -> None:
        version = self._connection.execute("PRAGMA user_version").fetchone()[0]
        if version == 0 and not self._read_only:
            try:
                self._connection.execute("BEGIN IMMEDIATE")
                for statement in _SCHEMA_SQL:
                    self._connection.execute(statement)
                self._connection.execute(
                    "INSERT INTO vector_migrations VALUES (?, ?, ?)",
                    (_SCHEMA_VERSION, _SCHEMA_CHECKSUM, datetime.now(timezone.utc).isoformat()),
                )
                self._connection.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")
                self._connection.commit()
            except Exception:
                self._connection.rollback()
                raise
        elif version != _SCHEMA_VERSION:
            raise ValueError("vector index schema mismatch")
        migration = self._connection.execute(
            "SELECT checksum FROM vector_migrations WHERE version = ?", (_SCHEMA_VERSION,)
        ).fetchone()
        if migration is None or migration[0] != _SCHEMA_CHECKSUM:
            raise ValueError("vector index migration checksum mismatch")
        integrity = self._connection.execute("PRAGMA integrity_check").fetchone()
        if integrity is None or integrity[0] != "ok":
            raise ValueError("vector index integrity check failed")
        for row in self._connection.execute("SELECT * FROM vectors"):
            self._decode_vector(row)

    @staticmethod
    def _decode_vector(row: sqlite3.Row) -> tuple[float, ...]:
        try:
            values = json.loads(row["vector_json"])
            if not isinstance(values, list) or len(values) != row["dimensions"] or not values:
                raise ValueError("invalid vector dimensions")
            if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in values):
                raise ValueError("invalid vector value types")
            vector = tuple(float(value) for value in values)
            norm = _vector_norm(vector)
            if any(not math.isfinite(value) for value in vector) or not math.isfinite(norm) or norm <= 0:
                raise ValueError("invalid vector values")
            digest = hashlib.sha256(row["vector_json"].encode("utf-8")).hexdigest()
            if digest != row["vector_hash"]:
                raise ValueError("vector hash mismatch")
            return vector
        except (TypeError, ValueError, OverflowError, json.JSONDecodeError) as exc:
            raise ValueError("corrupt vector mapping") from exc

    def write(self, scope: MemoryScope, record: DurableMemoryRecord, request: EmbeddingRequest, embedding: EmbeddingResult) -> None:
        if self._read_only:
            raise PermissionError("vector index is read-only")
        if record.tenant_id != scope.tenant_id or record.owner_id != scope.owner_id:
            raise PermissionError("vector scope mismatch")
        if record.sensitivity is not DurableSensitivity.PUBLIC or record.domain is DurableMemoryDomain.WORKING:
            raise PermissionError("durable vectors require public non-session memory")
        if record.status is not MemoryLifecycle.ACTIVE:
            raise ValueError("only active memory may be indexed")
        if not isinstance(request, EmbeddingRequest) or not isinstance(embedding, EmbeddingResult):
            raise TypeError("embedding request and result are required")
        if request.text != record.content or request.sensitivity is not record.sensitivity:
            raise ValueError("embedding input does not match memory record")
        norm = _vector_norm(embedding.vector)
        if request.model_id != embedding.model_id or not math.isfinite(norm) or norm <= 0:
            raise ValueError("embedding identity or vector is invalid")
        payload = _vector_payload(embedding.vector)
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            self._connection.execute(
                "INSERT INTO vectors VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    scope.tenant_id, scope.owner_id, record.memory_id, record.version,
                    record.content_hash, embedding.model_id, embedding.version,
                    len(embedding.vector), payload, digest,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raise

    def search(self, scope: MemoryScope, query: EmbeddingResult, limit: int = 10) -> tuple[VectorMemoryHit, ...]:
        if not isinstance(query, EmbeddingResult):
            raise TypeError("query must be EmbeddingResult")
        query_norm = _vector_norm(query.vector)
        if not math.isfinite(query_norm) or query_norm <= 0:
            raise ValueError("valid nonzero query embedding required")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("vector result limit must be 1 to 100")
        rows = self._connection.execute(
            "SELECT * FROM vectors WHERE tenant_id = ? AND owner_id = ? AND embedding_model_id = ? AND embedding_version = ?",
            (scope.tenant_id, scope.owner_id, query.model_id, query.version),
        ).fetchall()
        if len(rows) > 100_000:
            raise ValueError("vector search exceeds safe scan budget")
        hits: list[VectorMemoryHit] = []
        for row in rows:
            vector = self._decode_vector(row)
            if len(vector) != len(query.vector):
                raise ValueError("vector dimension mismatch")
            score = sum(a * b for a, b in zip(vector, query.vector)) / (_vector_norm(vector) * query_norm)
            score = max(-1.0, min(1.0, score))
            hits.append(VectorMemoryHit(
                row["memory_id"], row["memory_version"], row["content_hash"],
                row["embedding_model_id"], row["embedding_version"], score,
            ))
        hits.sort(key=lambda hit: (-hit.cosine_score, hit.memory_id, hit.memory_version))
        return tuple(hits[:limit])
