"""Proposal-only memory write flow; this module performs no persistence."""

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from backend.medar.memory_types import MemoryDomain, MemorySensitivity


class MemoryImportance(str, Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class MemoryRetention(str, Enum):
    SESSION = "SESSION"
    SHORT_TERM = "SHORT_TERM"
    LONG_TERM = "LONG_TERM"
    PERMANENT = "PERMANENT"


class MemoryApprovalPolicy(str, Enum):
    EXPLICIT_USER = "EXPLICIT_USER"
    POLICY_REVIEW = "POLICY_REVIEW"
    DO_NOT_STORE = "DO_NOT_STORE"


@dataclass(frozen=True)
class MemoryWriteProposal:
    proposal_id: str
    tenant_id: str
    user_id: str
    candidate: str
    domain: MemoryDomain
    importance: MemoryImportance
    sensitivity: MemorySensitivity
    confidence: float
    retention: MemoryRetention
    source: str
    approval_policy: MemoryApprovalPolicy
    persistence_authorized: bool = False

    def __post_init__(self) -> None:
        for name in ("proposal_id", "tenant_id", "user_id", "candidate", "source"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be non-empty text")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between zero and one")
        if self.persistence_authorized:
            raise ValueError("a memory proposal cannot authorize persistence")
        if self.domain is MemoryDomain.WORKING and self.retention is not MemoryRetention.SESSION:
            raise ValueError("working memory cannot outlive the session")
        if (
            self.sensitivity in (MemorySensitivity.SENSITIVE, MemorySensitivity.RESTRICTED)
            or self.retention is MemoryRetention.PERMANENT
        ) and self.approval_policy is not MemoryApprovalPolicy.EXPLICIT_USER:
            raise ValueError("sensitive or permanent memory requires explicit user approval")


class MemoryProposalSink(Protocol):
    def propose(self, proposal: MemoryWriteProposal) -> str: ...
