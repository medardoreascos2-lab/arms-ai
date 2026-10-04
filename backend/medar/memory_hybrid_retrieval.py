"""Evidence-scored hybrid MEDAR memory retrieval with scoped stale-vector checks."""

import math
from dataclasses import dataclass
from datetime import datetime, timezone

from backend.medar.durable_memory_record import DurableMemoryRecord, DurableSensitivity
from backend.medar.embedding_provider import EmbeddingResult
from backend.medar.memory_access import AuthorizedMemoryStore, MemoryAccessContext
from backend.medar.memory_lexical_retrieval import LexicalMemoryRetriever
from backend.medar.sqlite_memory_store import MemoryScope
from backend.medar.vector_memory_index import VectorMemoryIndex


@dataclass(frozen=True)
class HybridMemoryEvidence:
    record: DurableMemoryRecord
    total_score: float
    lexical_score: float
    vector_score: float
    recency_score: float
    importance_score: float
    domain_score: float
    vector_model_id: str | None
    semantic_quality_validated: bool = False

    def __post_init__(self) -> None:
        if self.semantic_quality_validated:
            raise ValueError("hybrid test retrieval cannot claim semantic quality")
        for value in (
            self.total_score, self.lexical_score, self.vector_score,
            self.recency_score, self.importance_score, self.domain_score,
        ):
            if not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError("hybrid evidence scores must be finite between zero and one")

    @property
    def memory_id(self) -> str:
        return self.record.memory_id

    @property
    def source_reference(self) -> str:
        return self.record.source_reference


@dataclass(frozen=True)
class HybridMemoryResult:
    evidence: tuple[HybridMemoryEvidence, ...]
    stale_vectors_skipped: int
    external_call_performed: bool = False
    persistence_performed: bool = False

    def __post_init__(self) -> None:
        if self.external_call_performed or self.persistence_performed:
            raise ValueError("hybrid retrieval cannot call external services or persist memory")


class HybridMemoryRetriever:
    def __init__(
        self,
        store: AuthorizedMemoryStore,
        *,
        vector_index: VectorMemoryIndex | None = None,
        clock=None,
        allow_test_embeddings: bool = False,
    ):
        if not isinstance(allow_test_embeddings, bool):
            raise TypeError("allow_test_embeddings must be boolean")
        self._allow_test_embeddings = allow_test_embeddings
        self._store = store
        self._lexical = LexicalMemoryRetriever(store)
        self._vector = vector_index
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def retrieve(
        self,
        contexts: tuple[MemoryAccessContext, ...],
        query: str,
        *,
        query_embedding: EmbeddingResult | None = None,
        limit: int = 10,
    ) -> HybridMemoryResult:
        if not isinstance(contexts, tuple) or not contexts:
            raise ValueError("at least one memory access context is required")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("hybrid result limit must be 1 to 100")
        if query_embedding is not None and not isinstance(query_embedding, EmbeddingResult):
            raise TypeError("query_embedding must be EmbeddingResult")
        now = self._clock()
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("hybrid clock must be timezone-aware")
        owner = (contexts[0].tenant_id, contexts[0].owner_id)
        if any((context.tenant_id, context.owner_id) != owner for context in contexts):
            raise PermissionError("hybrid query cannot combine owner scopes")
        if len({context.domain for context in contexts}) != len(contexts):
            raise ValueError("hybrid query domains must be unique")

        entries: dict[tuple[str, str], dict[str, object]] = {}
        stale = 0
        for position, context in enumerate(contexts):
            lexical = self._lexical.retrieve(context, query, limit=100)
            domain_weight = 1.0 if position == 0 else 0.7
            for rank, hit in enumerate(lexical.hits):
                key = (context.domain.value, hit.memory_id)
                entries[key] = {
                    "record": hit.record,
                    "lexical": 1.0 / (rank + 1),
                    "vector": 0.0,
                    "domain": domain_weight,
                    "vector_model": None,
                }
            if self._vector is None or query_embedding is None or context.sensitivity is not DurableSensitivity.PUBLIC:
                continue
            if query_embedding.provider_id == "deterministic-test-embedding" and not self._allow_test_embeddings:
                continue
            scope = MemoryScope(context.tenant_id, context.owner_id)
            for vector_hit in self._vector.search(scope, query_embedding, limit=100):
                try:
                    record = self._store.get(context, vector_hit.memory_id)
                except PermissionError:
                    continue
                if record is None or record.version != vector_hit.memory_version or record.content_hash != vector_hit.content_hash:
                    stale += 1
                    continue
                key = (context.domain.value, record.memory_id)
                entry = entries.setdefault(key, {
                    "record": record,
                    "lexical": 0.0,
                    "vector": 0.0,
                    "domain": domain_weight,
                    "vector_model": None,
                })
                entry["vector"] = max(entry["vector"], (vector_hit.cosine_score + 1.0) / 2.0)
                entry["vector_model"] = vector_hit.embedding_model_id

        evidence: list[HybridMemoryEvidence] = []
        for entry in entries.values():
            record = entry["record"]
            lexical_score = entry["lexical"]
            vector_score = entry["vector"]
            domain_score = entry["domain"]
            age_days = max(0.0, (now - record.observed_at).total_seconds() / 86400.0)
            recency_score = 1.0 / (1.0 + age_days / 365.0)
            importance_score = record.importance
            total = (
                0.4 * lexical_score + 0.2 * vector_score +
                0.15 * recency_score + 0.15 * importance_score +
                0.1 * domain_score
            )
            evidence.append(HybridMemoryEvidence(
                record, total, lexical_score, vector_score,
                recency_score, importance_score, domain_score,
                entry["vector_model"],
            ))
        evidence.sort(key=lambda item: (-item.total_score, item.record.domain.value, item.memory_id))
        return HybridMemoryResult(tuple(evidence[:limit]), stale)
