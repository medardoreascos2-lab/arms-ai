"""Heuristic reranking of authorized Phase 8 memory evidence, without model calls."""

import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone

from backend.medar.durable_memory_record import DurableMemoryRecord, ProvenanceClass
from backend.medar.memory_access import AuthorizedMemoryStore, MemoryAccessContext, authorize_memory_access
from backend.medar.memory_hybrid_retrieval import HybridMemoryEvidence, HybridMemoryResult


_SOURCE_QUALITY = {
    ProvenanceClass.USER_STATED: 1.0,
    ProvenanceClass.DIRECT_OBSERVATION: 0.9,
    ProvenanceClass.TOOL_RESULT: 0.8,
    ProvenanceClass.SOURCE_DOCUMENT: 0.8,
    ProvenanceClass.WEB_SOURCE: 0.65,
    ProvenanceClass.IMPORTED: 0.5,
    ProvenanceClass.DERIVED_ANALYSIS: 0.3,
    ProvenanceClass.MODEL_INFERENCE: 0.2,
    ProvenanceClass.UNKNOWN: 0.0,
}


def _terms(value: str) -> set[str]:
    return set(re.findall(r"\w+", value.casefold(), flags=re.UNICODE))


@dataclass(frozen=True)
class RerankedMemoryEvidence:
    record: DurableMemoryRecord
    original_evidence: HybridMemoryEvidence
    total_score: float
    query_score: float
    domain_score: float
    recency_score: float
    importance_score: float
    confidence_score: float
    source_quality_score: float
    heuristic_only: bool = True

    def __post_init__(self) -> None:
        if not self.heuristic_only:
            raise ValueError("memory relevance has not been empirically validated")
        for score in (
            self.total_score, self.query_score, self.domain_score,
            self.recency_score, self.importance_score, self.confidence_score,
            self.source_quality_score,
        ):
            if not math.isfinite(score) or not 0 <= score <= 1:
                raise ValueError("reranking scores must be finite between zero and one")

    @property
    def memory_id(self) -> str:
        return self.record.memory_id

    @property
    def source_reference(self) -> str:
        return self.record.source_reference


@dataclass(frozen=True)
class RerankedMemoryResult:
    evidence: tuple[RerankedMemoryEvidence, ...]
    stale_records_skipped: int
    persistence_performed: bool = False
    external_call_performed: bool = False

    def __post_init__(self) -> None:
        if self.persistence_performed or self.external_call_performed:
            raise ValueError("reranking cannot persist memory or call external services")


class MemoryReranker:
    def __init__(self, store: AuthorizedMemoryStore, *, clock=None):
        self._store = store
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def rerank(
        self,
        contexts: tuple[MemoryAccessContext, ...],
        query: str,
        candidates: HybridMemoryResult,
        *,
        limit: int = 10,
    ) -> RerankedMemoryResult:
        if not isinstance(contexts, tuple) or not contexts:
            raise ValueError("at least one authorized context is required")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be non-empty")
        query_terms = _terms(query)
        if not query_terms or len(query_terms) > 32:
            raise ValueError("query must contain 1 to 32 word tokens")
        if not isinstance(candidates, HybridMemoryResult):
            raise TypeError("candidates must be hybrid memory evidence")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("rerank limit must be 1 to 100")
        now = self._clock()
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("rerank clock must be timezone-aware")
        owner = (contexts[0].tenant_id, contexts[0].owner_id)
        if any((context.tenant_id, context.owner_id) != owner for context in contexts):
            raise PermissionError("reranking cannot combine owner scopes")
        if len({context.domain for context in contexts}) != len(contexts):
            raise ValueError("rerank domains must be unique")
        for context in contexts:
            authorize_memory_access(context, "read")
        by_domain = {context.domain: (index, context) for index, context in enumerate(contexts)}
        ranked: list[RerankedMemoryEvidence] = []
        stale = 0
        seen: set[tuple[str, str]] = set()
        for candidate in candidates.evidence:
            context_info = by_domain.get(candidate.record.domain)
            if context_info is None:
                raise PermissionError("candidate domain is outside authorized contexts")
            position, context = context_info
            if candidate.record.sensitivity is not context.sensitivity:
                raise PermissionError("candidate sensitivity is outside authorized context")
            record = self._store.get(context, candidate.memory_id)
            if record is None or record.version != candidate.record.version or record.content_hash != candidate.record.content_hash:
                stale += 1
                continue
            identity = (record.domain.value, record.memory_id)
            if identity in seen:
                continue
            seen.add(identity)
            overlap = len(query_terms & _terms(record.content)) / len(query_terms)
            query_score = max(overlap, candidate.vector_score * 0.25)
            domain_score = 1.0 if position == 0 else 0.7
            age_days = max(0.0, (now - record.observed_at).total_seconds() / 86400)
            recency_score = 1.0 / (1.0 + age_days / 365.0)
            confidence_score = min(record.confidence, record.provenance.confidence)
            source_quality_score = _SOURCE_QUALITY[record.provenance_class]
            total_score = (
                0.35 * query_score + 0.15 * domain_score +
                0.12 * recency_score + 0.10 * record.importance +
                0.13 * confidence_score + 0.15 * source_quality_score
            )
            ranked.append(RerankedMemoryEvidence(
                record, candidate, total_score, query_score, domain_score,
                recency_score, record.importance, confidence_score, source_quality_score,
            ))
        ranked.sort(key=lambda item: (-item.total_score, item.record.domain.value, item.memory_id))
        return RerankedMemoryResult(tuple(ranked[:limit]), stale)
