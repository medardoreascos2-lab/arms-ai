"""Deterministic, proposal-only extraction of explicit MEDAR memory candidates.

The extractor has no store dependency and never authorizes persistence.
"""

import hashlib
import math
import re
from dataclasses import dataclass
from enum import Enum

from backend.medar.durable_memory_record import DurableMemoryDomain, DurableSensitivity


class CandidateSourceType(str, Enum):
    USER_STATEMENT = "USER_STATEMENT"
    TASK_OUTCOME = "TASK_OUTCOME"


class CandidateImportance(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


_SECRET_PATTERN = re.compile(
    r"(?i)(?:password|api[_-]?key|access[_-]?token|auth(?:orization)?|private[_-]?key|secret)\s*[:=]|bearer\s+\S+|\b\d{9,}\b"
)
def has_secret_like_content(text: str) -> bool:
    return bool(_SECRET_PATTERN.search(text))


_USER_MARKERS = (
    (re.compile(r"(?i)^remember that\s+(.+)$"), "EXPLICIT_REMEMBER_REQUEST"),
    (re.compile(r"(?i)^i prefer\s+(.+)$"), "EXPLICIT_USER_PREFERENCE"),
    (re.compile(r"(?i)^my preference is\s+(.+)$"), "EXPLICIT_USER_PREFERENCE"),
)
_OUTCOME_MARKERS = (
    (re.compile(r"(?i)^lesson learned:\s*(.+)$"), "LABELED_TASK_LESSON"),
    (re.compile(r"(?i)^outcome:\s*(.+)$"), "LABELED_TASK_OUTCOME"),
    (re.compile(r"(?i)^decision:\s*(.+)$"), "LABELED_DECISION"),
)
_PERSONAL_DOMAINS = frozenset({
    DurableMemoryDomain.PERSONAL, DurableMemoryDomain.PREFERENCES,
    DurableMemoryDomain.LIFE, DurableMemoryDomain.CAREER,
})
_FINANCIAL_DOMAINS = frozenset({
    DurableMemoryDomain.TRADING, DurableMemoryDomain.NQ, DurableMemoryDomain.MNQ,
    DurableMemoryDomain.FINANCIAL, DurableMemoryDomain.PORTFOLIO,
    DurableMemoryDomain.CRYPTO, DurableMemoryDomain.CRYPTO_ARBITRAGE,
})


@dataclass(frozen=True)
class CandidateSource:
    tenant_id: str
    owner_id: str
    source_reference: str
    source_type: CandidateSourceType
    domain: DurableMemoryDomain
    text: str

    def __post_init__(self) -> None:
        for name in ("tenant_id", "owner_id", "source_reference", "text"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be non-empty text")
        if not isinstance(self.source_type, CandidateSourceType):
            raise TypeError("source_type must be CandidateSourceType")
        if not isinstance(self.domain, DurableMemoryDomain):
            raise TypeError("domain must be DurableMemoryDomain")


@dataclass(frozen=True)
class MemoryCandidate:
    candidate_id: str
    tenant_id: str
    owner_id: str
    source_reference: str
    source_type: CandidateSourceType
    content: str
    domain: DurableMemoryDomain
    importance: CandidateImportance
    confidence: float
    sensitivity: DurableSensitivity
    reason_to_remember: str
    persistence_authorized: bool = False

    def __post_init__(self) -> None:
        for name in ("candidate_id", "tenant_id", "owner_id", "source_reference", "content", "reason_to_remember"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be non-empty text")
        if not isinstance(self.domain, DurableMemoryDomain) or not isinstance(self.sensitivity, DurableSensitivity):
            raise TypeError("candidate classification must be typed")
        if not isinstance(self.importance, CandidateImportance) or not isinstance(self.source_type, CandidateSourceType):
            raise TypeError("candidate importance and source type must be typed")
        if isinstance(self.confidence, bool) or not isinstance(self.confidence, (int, float)) or not math.isfinite(self.confidence) or not 0 <= self.confidence <= 1:
            raise ValueError("candidate confidence must be finite and between zero and one")
        if self.persistence_authorized:
            raise ValueError("candidate extraction cannot authorize persistence")


@dataclass(frozen=True)
class CandidateExtraction:
    candidates: tuple[MemoryCandidate, ...]
    rejection_reasons: tuple[str, ...]
    persistence_performed: bool = False

    def __post_init__(self) -> None:
        if self.persistence_performed:
            raise ValueError("candidate extraction cannot persist memory")


def _sensitivity(domain: DurableMemoryDomain) -> DurableSensitivity:
    if domain is DurableMemoryDomain.ROSITA:
        return DurableSensitivity.HIGHLY_SENSITIVE
    if domain in _FINANCIAL_DOMAINS:
        return DurableSensitivity.SENSITIVE
    if domain in _PERSONAL_DOMAINS:
        return DurableSensitivity.PERSONAL
    return DurableSensitivity.INTERNAL


class MemoryCandidateExtractor:
    def extract(self, source: CandidateSource) -> CandidateExtraction:
        normalized = " ".join(source.text.split())
        if len(normalized) > 1024:
            return CandidateExtraction((), ("SOURCE_TOO_LONG",))
        if has_secret_like_content(normalized):
            return CandidateExtraction((), ("SECRET_LIKE_CONTENT",))
        markers = _USER_MARKERS if source.source_type is CandidateSourceType.USER_STATEMENT else _OUTCOME_MARKERS
        for pattern, reason in markers:
            matched = pattern.fullmatch(normalized)
            if matched is None or not matched.group(1).strip():
                continue
            content = normalized if reason == "EXPLICIT_USER_PREFERENCE" else matched.group(1).strip()
            digest = hashlib.sha256(
                "\x1f".join((source.tenant_id, source.owner_id, source.source_reference, content)).encode("utf-8")
            ).hexdigest()
            candidate = MemoryCandidate(
                candidate_id=digest,
                tenant_id=source.tenant_id,
                owner_id=source.owner_id,
                source_reference=source.source_reference,
                source_type=source.source_type,
                content=content,
                domain=source.domain,
                importance=CandidateImportance.MEDIUM,
                confidence=0.9 if source.source_type is CandidateSourceType.USER_STATEMENT else 0.7,
                sensitivity=_sensitivity(source.domain),
                reason_to_remember=reason,
            )
            return CandidateExtraction((candidate,), ())
        return CandidateExtraction((), ("NO_EXPLICIT_MEMORY_SIGNAL",))
