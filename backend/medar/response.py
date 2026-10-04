"""Canonical response and evidence models for MEDAR."""

from dataclasses import dataclass
from enum import Enum


class ResponseStatus(str, Enum):
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    NEEDS_CONFIRMATION = "NEEDS_CONFIRMATION"


@dataclass(frozen=True)
class SourceReference:
    source_id: str
    title: str
    locator: str


@dataclass(frozen=True)
class EvidenceReference:
    evidence_id: str
    summary: str
    digest: str


@dataclass(frozen=True)
class ActionProposal:
    action_id: str
    description: str
    requires_confirmation: bool
    execution_authorized: bool = False


@dataclass(frozen=True)
class CognitiveResponse:
    response_id: str
    request_id: str
    status: ResponseStatus
    answer: str
    confidence: float
    reasoning_summary: str
    sources: tuple[SourceReference, ...] = ()
    tool_evidence: tuple[EvidenceReference, ...] = ()
    memory_evidence: tuple[EvidenceReference, ...] = ()
    warnings: tuple[str, ...] = ()
    follow_up_needed: bool = False
    action_proposals: tuple[ActionProposal, ...] = ()

    def __post_init__(self) -> None:
        for name in ("response_id", "request_id", "answer"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be non-empty text")
        if not isinstance(self.status, ResponseStatus):
            raise TypeError("status must be ResponseStatus")
        if isinstance(self.confidence, bool) or not isinstance(self.confidence, (int, float)):
            raise TypeError("confidence must be numeric")
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("confidence must be between zero and one")
        if not isinstance(self.reasoning_summary, str):
            raise TypeError("reasoning_summary must be text")
        if not isinstance(self.follow_up_needed, bool):
            raise TypeError("follow_up_needed must be bool")
        for proposal in self.action_proposals:
            if not isinstance(proposal, ActionProposal):
                raise TypeError("action proposals must use ActionProposal")
            if proposal.execution_authorized:
                raise ValueError("responses cannot authorize proposed actions")
