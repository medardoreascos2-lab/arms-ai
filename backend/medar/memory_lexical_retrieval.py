"""Scoped lexical retrieval using ephemeral local SQLite FTS5 when available.

The index is built from authorized active records for each query. No persistent
schema change, external service, or semantic-quality claim is involved.
"""

import math
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime

from backend.medar.durable_memory_record import DurableMemoryRecord
from backend.medar.memory_access import AuthorizedMemoryStore, MemoryAccessContext


@dataclass(frozen=True)
class LexicalMemoryHit:
    record: DurableMemoryRecord
    bm25_rank: float | None
    engine: str

    @property
    def memory_id(self) -> str:
        return self.record.memory_id

    @property
    def source_reference(self) -> str:
        return self.record.source_reference


@dataclass(frozen=True)
class LexicalRetrievalResult:
    hits: tuple[LexicalMemoryHit, ...]
    query_terms: tuple[str, ...]
    engine: str
    semantic_quality_validated: bool = False

    def __post_init__(self) -> None:
        if self.semantic_quality_validated:
            raise ValueError("lexical retrieval cannot claim semantic quality")


class LexicalMemoryRetriever:
    def __init__(self, store: AuthorizedMemoryStore):
        self._store = store

    def retrieve(
        self,
        context: MemoryAccessContext,
        query: str,
        *,
        observed_from: datetime | None = None,
        observed_to: datetime | None = None,
        minimum_importance: float = 0.0,
        source_type: str | None = None,
        limit: int = 10,
    ) -> LexicalRetrievalResult:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("lexical query must be non-empty")
        terms = tuple(token.casefold() for token in re.findall(r"\w+", query, flags=re.UNICODE))
        if not terms or len(terms) > 32:
            raise ValueError("lexical query must contain 1 to 32 word tokens")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("lexical result limit must be 1 to 100")
        if isinstance(minimum_importance, bool) or not isinstance(minimum_importance, (int, float)) or not math.isfinite(minimum_importance) or not 0 <= minimum_importance <= 1:
            raise ValueError("minimum_importance must be finite between zero and one")
        for value in (observed_from, observed_to):
            if value is not None and (
                not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None
            ):
                raise ValueError("date filters must be timezone-aware")
        if observed_from is not None and observed_to is not None and observed_from > observed_to:
            raise ValueError("observed_from must not follow observed_to")
        if source_type is not None and (not isinstance(source_type, str) or not source_type.strip()):
            raise ValueError("source_type must be non-empty text")

        records = tuple(record for record in self._store.list_active(context) if (
            (observed_from is None or record.observed_at >= observed_from)
            and (observed_to is None or record.observed_at <= observed_to)
            and record.importance >= minimum_importance
            and (source_type is None or record.source_type == source_type)
        ))
        if not records:
            return LexicalRetrievalResult((), terms, "NO_MATCHABLE_RECORDS")
        connection = sqlite3.connect(":memory:")
        try:
            try:
                connection.execute("CREATE VIRTUAL TABLE scoped_memory_fts USING fts5(content)")
            except sqlite3.OperationalError:
                matches = tuple(
                    record for record in records
                    if all(term in tuple(re.findall(r"\w+", record.content.casefold(), flags=re.UNICODE)) for term in terms)
                )
                return LexicalRetrievalResult(
                    tuple(LexicalMemoryHit(record, None, "LEXICAL_FALLBACK") for record in matches[:limit]),
                    terms, "LEXICAL_FALLBACK",
                )
            connection.executemany(
                "INSERT INTO scoped_memory_fts(rowid, content) VALUES (?, ?)",
                ((index, record.content) for index, record in enumerate(records, 1)),
            )
            expression = " ".join('"' + token.replace('"', '""') + '"' for token in terms)
            rows = connection.execute(
                "SELECT rowid, bm25(scoped_memory_fts) AS rank FROM scoped_memory_fts "
                "WHERE scoped_memory_fts MATCH ? ORDER BY rank, rowid LIMIT ?",
                (expression, limit),
            ).fetchall()
            hits = tuple(
                LexicalMemoryHit(records[rowid - 1], float(rank), "SQLITE_FTS5")
                for rowid, rank in rows
            )
            return LexicalRetrievalResult(hits, terms, "SQLITE_FTS5")
        finally:
            connection.close()
