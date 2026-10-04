"""Canonical, immutable Phase 8 MEDAR durable memory record.

Records carry source classification and scope; no write authority is implied.
"""

import hashlib
import math
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from backend.medar.memory_provenance import MemoryOrigin, MemoryProvenance


class DurableMemoryDomain(str, Enum):
    WORKING = "WORKING"
    EPISODIC = "EPISODIC"
    SEMANTIC = "SEMANTIC"
    PERSONAL = "PERSONAL"
    PREFERENCES = "PREFERENCES"
    TECHNICAL = "TECHNICAL"
    CODING = "CODING"
    TRADING = "TRADING"
    NQ = "NQ"
    MNQ = "MNQ"
    FINANCIAL = "FINANCIAL"
    PORTFOLIO = "PORTFOLIO"
    CRYPTO = "CRYPTO"
    CRYPTO_ARBITRAGE = "CRYPTO_ARBITRAGE"
    BUSINESS = "BUSINESS"
    MARKETING = "MARKETING"
    LIFE = "LIFE"
    CAREER = "CAREER"
    TOOL = "TOOL"
    MODEL_PERFORMANCE = "MODEL_PERFORMANCE"
    RESEARCH = "RESEARCH"
    ROSITA = "ROSITA"
    DECISION_JOURNAL = "DECISION_JOURNAL"


class DurableMemoryType(str, Enum):
    FACT = "FACT"
    PREFERENCE = "PREFERENCE"
    DECISION = "DECISION"
    OUTCOME = "OUTCOME"
    LESSON = "LESSON"
    SUMMARY = "SUMMARY"


class MemoryLifecycle(str, Enum):
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    EXPIRED = "EXPIRED"
    RETRACTED = "RETRACTED"
    QUARANTINED = "QUARANTINED"


class DurableSensitivity(str, Enum):
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    PERSONAL = "PERSONAL"
    SENSITIVE = "SENSITIVE"
    HIGHLY_SENSITIVE = "HIGHLY_SENSITIVE"


class ProvenanceClass(str, Enum):
    USER_STATED = "USER_STATED"
    DIRECT_OBSERVATION = "DIRECT_OBSERVATION"
    TOOL_RESULT = "TOOL_RESULT"
    SOURCE_DOCUMENT = "SOURCE_DOCUMENT"
    WEB_SOURCE = "WEB_SOURCE"
    MODEL_INFERENCE = "MODEL_INFERENCE"
    DERIVED_ANALYSIS = "DERIVED_ANALYSIS"
    IMPORTED = "IMPORTED"
    UNKNOWN = "UNKNOWN"


class RetentionPolicy(str, Enum):
    SESSION = "SESSION"
    SHORT_TERM = "SHORT_TERM"
    LONG_TERM = "LONG_TERM"
    ARCHIVE = "ARCHIVE"
    UNTIL_DATE = "UNTIL_DATE"
    MANUAL_REVIEW = "MANUAL_REVIEW"


def content_digest(content: str) -> str:
    if not isinstance(content, str) or not content.strip():
        raise ValueError("memory content must be non-empty text")
    return hashlib.sha256(content.encode("utf-8", errors="strict")).hexdigest()


@dataclass(frozen=True)
class DurableMemoryRecord:
    memory_id: str
    owner_id: str
    tenant_id: str
    domain: DurableMemoryDomain
    memory_type: DurableMemoryType
    content: str
    content_hash: str
    source_type: str
    source_reference: str
    provenance: MemoryProvenance
    provenance_class: ProvenanceClass
    confidence: float
    importance: float
    sensitivity: DurableSensitivity
    created_at: datetime
    observed_at: datetime
    expires_at: datetime | None
    retention_policy: RetentionPolicy
    status: MemoryLifecycle
    version: int

    def __post_init__(self) -> None:
        for field in ("memory_id", "owner_id", "tenant_id", "source_type", "source_reference"):
            value = getattr(self, field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field} must be non-empty text")
        if self.content_hash != content_digest(self.content):
            raise ValueError("content hash does not match content")
        typed = (
            (self.domain, DurableMemoryDomain),
            (self.memory_type, DurableMemoryType),
            (self.provenance_class, ProvenanceClass),
            (self.sensitivity, DurableSensitivity),
            (self.retention_policy, RetentionPolicy),
            (self.status, MemoryLifecycle),
        )
        if any(not isinstance(value, expected) for value, expected in typed):
            raise TypeError("memory classification must use typed enums")
        if not isinstance(self.provenance, MemoryProvenance):
            raise TypeError("provenance must be MemoryProvenance")
        if not math.isfinite(self.provenance.confidence):
            raise ValueError("provenance confidence must be finite")
        if self.provenance.tenant_id != self.tenant_id or self.provenance.user_id != self.owner_id:
            raise ValueError("memory provenance must match owner and tenant")
        for name in ("confidence", "importance"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError(f"{name} must be a finite score between zero and one")
        for name in ("created_at", "observed_at"):
            value = getattr(self, name)
            if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{name} must be timezone-aware")
        if self.expires_at is not None:
            if not isinstance(self.expires_at, datetime) or self.expires_at.tzinfo is None or self.expires_at.utcoffset() is None:
                raise ValueError("expires_at must be timezone-aware")
            if self.expires_at <= self.created_at:
                raise ValueError("expires_at must follow creation")
        if self.retention_policy is RetentionPolicy.UNTIL_DATE and self.expires_at is None:
            raise ValueError("UNTIL_DATE memory requires expires_at")
        if self.domain is DurableMemoryDomain.WORKING and self.retention_policy is not RetentionPolicy.SESSION:
            raise ValueError("working memory cannot be durable")
        if self.provenance_class is ProvenanceClass.UNKNOWN and self.status is not MemoryLifecycle.QUARANTINED:
            raise ValueError("unknown provenance must be quarantined")
        if self.provenance_class in (ProvenanceClass.MODEL_INFERENCE, ProvenanceClass.DERIVED_ANALYSIS):
            if self.provenance.origin is not MemoryOrigin.INFERRED:
                raise ValueError("inferred memory must retain inferred origin")
        elif self.provenance_class is ProvenanceClass.IMPORTED:
            if self.provenance.origin is not MemoryOrigin.IMPORTED:
                raise ValueError("imported memory must retain imported origin")
        elif self.provenance_class is not ProvenanceClass.UNKNOWN and self.provenance.origin is not MemoryOrigin.OBSERVED:
            raise ValueError("observed memory must retain observed origin")
        if isinstance(self.version, bool) or not isinstance(self.version, int) or self.version < 1:
            raise ValueError("version must be positive")
