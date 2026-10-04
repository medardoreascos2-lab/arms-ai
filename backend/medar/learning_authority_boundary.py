"""Invariant guard proving learning decisions cannot change runtime authority."""

from dataclasses import dataclass

from backend.medar.learning_gate import LearningGateDecision
from backend.medar.learning_proposal import LearningProposal


@dataclass(frozen=True)
class RuntimeAuthoritySnapshot:
    tenant_id: str
    owner_id: str
    broker_authority: bool
    paper_authority: bool
    live_authority: bool
    production_autonomy: bool
    computer_permission_level: str
    secret_access: bool

    def __post_init__(self) -> None:
        for name in ("tenant_id", "owner_id", "computer_permission_level"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} is required")


@dataclass(frozen=True)
class LearningAuthorityBoundaryResult:
    proposal_id: str
    before: RuntimeAuthoritySnapshot
    after: RuntimeAuthoritySnapshot
    authority_changed: bool
    applied_changes: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.authority_changed or self.applied_changes or self.after != self.before:
            raise ValueError("learning authority boundary cannot apply authority changes")


def enforce_learning_authority_boundary(
    proposal: LearningProposal,
    decision: LearningGateDecision,
    authority: RuntimeAuthoritySnapshot,
) -> LearningAuthorityBoundaryResult:
    if not isinstance(proposal, LearningProposal) or not isinstance(decision, LearningGateDecision):
        raise TypeError("learning proposal and gate decision are required")
    if not isinstance(authority, RuntimeAuthoritySnapshot):
        raise TypeError("runtime authority snapshot is required")
    if proposal.proposal_id != decision.proposal_id:
        raise PermissionError("learning decision does not match proposal")
    if proposal.tenant_id != authority.tenant_id or proposal.owner_id != authority.owner_id:
        raise PermissionError("learning proposal cannot cross authority scope")
    return LearningAuthorityBoundaryResult(
        proposal.proposal_id, authority, authority, False, (),
    )
