"""Evidence-linked MEDAR improvement proposals with no self authority."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from backend.medar.memory_candidates import has_secret_like_content


class LearningProposalType(str, Enum):
    MEMORY_UPDATE = "MEMORY_UPDATE"
    TOOL_PREFERENCE = "TOOL_PREFERENCE"
    MODEL_PREFERENCE = "MODEL_PREFERENCE"
    WORKFLOW_RECOMMENDATION = "WORKFLOW_RECOMMENDATION"
    STRATEGY_RESEARCH_RECOMMENDATION = "STRATEGY_RESEARCH_RECOMMENDATION"


@dataclass(frozen=True)
class LearningProposal:
    proposal_id: str
    tenant_id: str
    owner_id: str
    proposal_type: LearningProposalType
    summary: str = field(repr=False)
    evidence_references: tuple[str, ...]
    created_at: datetime
    execution_authority: bool = False
    deployment_authority: bool = False
    routing_authority: bool = False
    memory_mutation_authority: bool = False

    def __post_init__(self) -> None:
        for name in ("proposal_id", "tenant_id", "owner_id", "summary"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or len(value) > 1024:
                raise ValueError(f"{name} must be bounded non-empty text")
            if has_secret_like_content(value):
                raise PermissionError("secret-like learning proposal content is not retained")
        if not isinstance(self.proposal_type, LearningProposalType):
            raise TypeError("learning proposal type must be typed")
        if not self.evidence_references or len(self.evidence_references) > 20 or any(
            not isinstance(reference, str) or not reference.startswith("synthetic-test:")
            or len(reference) > 240 or has_secret_like_content(reference)
            for reference in self.evidence_references
        ):
            raise ValueError("learning proposal requires bounded synthetic evidence")
        if not isinstance(self.created_at, datetime) or self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("learning proposal time must be timezone-aware")
        if any((
            self.execution_authority, self.deployment_authority,
            self.routing_authority, self.memory_mutation_authority,
        )):
            raise ValueError("learning proposal cannot grant authority")
