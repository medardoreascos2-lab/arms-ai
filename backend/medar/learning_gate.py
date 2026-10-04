"""Continuous learning gate that can approve memory or research only."""

from dataclasses import dataclass
from enum import Enum

from backend.medar.learning_proposal import LearningProposal, LearningProposalType


class LearningGateStatus(str, Enum):
    APPROVED_FOR_MEMORY = "APPROVED_FOR_MEMORY"
    APPROVED_FOR_RESEARCH = "APPROVED_FOR_RESEARCH"
    REQUIRES_HUMAN_REVIEW = "REQUIRES_HUMAN_REVIEW"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class LearningGateDecision:
    proposal_id: str
    status: LearningGateStatus
    reason_codes: tuple[str, ...]
    production_deployment_authorized: bool = False
    execution_authorized: bool = False
    automatic_application_authorized: bool = False

    def __post_init__(self) -> None:
        if any((
            self.production_deployment_authorized,
            self.execution_authorized,
            self.automatic_application_authorized,
        )):
            raise ValueError("learning gate cannot authorize deployment or execution")


def evaluate_learning_proposal(
    proposal: LearningProposal,
    *,
    evidence_validated: bool,
    human_approved: bool = False,
) -> LearningGateDecision:
    if not isinstance(proposal, LearningProposal):
        raise TypeError("learning proposal is required")
    if not isinstance(evidence_validated, bool) or not isinstance(human_approved, bool):
        raise TypeError("learning gate flags must be boolean")
    if not evidence_validated:
        return LearningGateDecision(
            proposal.proposal_id, LearningGateStatus.REJECTED,
            ("EVIDENCE_NOT_VALIDATED",),
        )
    if proposal.proposal_type is LearningProposalType.MEMORY_UPDATE:
        if not human_approved:
            return LearningGateDecision(
                proposal.proposal_id, LearningGateStatus.REQUIRES_HUMAN_REVIEW,
                ("MEMORY_UPDATE_REQUIRES_HUMAN_REVIEW",),
            )
        return LearningGateDecision(
            proposal.proposal_id, LearningGateStatus.APPROVED_FOR_MEMORY,
            ("EVIDENCE_VALIDATED", "HUMAN_APPROVED_MEMORY_ONLY"),
        )
    return LearningGateDecision(
        proposal.proposal_id, LearningGateStatus.APPROVED_FOR_RESEARCH,
        ("EVIDENCE_VALIDATED", "RESEARCH_ONLY"),
    )
