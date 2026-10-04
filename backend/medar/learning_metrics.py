"""Content-free metrics for scoped Phase 8 learning proposals and gate outcomes."""

from collections import Counter
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from backend.medar.learning_gate import LearningGateDecision, LearningGateStatus
from backend.medar.learning_proposal import LearningProposal
from backend.medar.sqlite_memory_store import MemoryScope


@dataclass(frozen=True)
class LearningMetricsSnapshot:
    tenant_id: str
    owner_id: str
    proposals: int
    evidence_references: int
    by_proposal_type: Mapping[str, int]
    by_gate_status: Mapping[str, int]
    human_review_required: int
    memory_approvals: int
    research_approvals: int
    rejected: int
    automatic_applications: int = 0
    deployment_authority: bool = False
    execution_authority: bool = False

    def __post_init__(self) -> None:
        if self.automatic_applications or self.deployment_authority or self.execution_authority:
            raise ValueError("learning metrics cannot report automatic application or authority")


def summarize_learning_metrics(
    evaluations: tuple[tuple[LearningProposal, LearningGateDecision], ...],
    scope: MemoryScope,
) -> LearningMetricsSnapshot:
    if not isinstance(evaluations, tuple) or any(
        not isinstance(item, tuple) or len(item) != 2
        or not isinstance(item[0], LearningProposal) or not isinstance(item[1], LearningGateDecision)
        for item in evaluations
    ):
        raise TypeError("learning metrics require typed proposal-decision pairs")
    if not isinstance(scope, MemoryScope):
        raise TypeError("learning metrics require a typed scope")
    types: Counter[str] = Counter()
    statuses: Counter[str] = Counter()
    evidence_count = 0
    seen: set[str] = set()
    for proposal, decision in evaluations:
        if proposal.proposal_id in seen:
            raise ValueError("duplicate learning proposal metric")
        seen.add(proposal.proposal_id)
        if proposal.proposal_id != decision.proposal_id:
            raise PermissionError("learning metric decision mismatch")
        if (proposal.tenant_id, proposal.owner_id) != (scope.tenant_id, scope.owner_id):
            raise PermissionError("learning metric scope mismatch")
        types[proposal.proposal_type.value] += 1
        statuses[decision.status.value] += 1
        evidence_count += len(proposal.evidence_references)
    return LearningMetricsSnapshot(
        scope.tenant_id, scope.owner_id, len(evaluations), evidence_count,
        MappingProxyType(dict(sorted(types.items()))),
        MappingProxyType(dict(sorted(statuses.items()))),
        statuses[LearningGateStatus.REQUIRES_HUMAN_REVIEW.value],
        statuses[LearningGateStatus.APPROVED_FOR_MEMORY.value],
        statuses[LearningGateStatus.APPROVED_FOR_RESEARCH.value],
        statuses[LearningGateStatus.REJECTED.value],
    )
