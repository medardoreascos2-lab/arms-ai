"""R123C learning metrics count gates without proposal content or authority."""

from datetime import datetime, timezone

import pytest

from backend.medar.learning_gate import evaluate_learning_proposal
from backend.medar.learning_metrics import summarize_learning_metrics
from backend.medar.learning_proposal import LearningProposal, LearningProposalType
from backend.medar.sqlite_memory_store import MemoryScope

NOW = datetime(2026, 10, 5, 1, tzinfo=timezone.utc)
SCOPE = MemoryScope("tenant-a", "owner-a")


def _proposal(proposal_id, kind, owner="owner-a"):
    return LearningProposal(proposal_id, "tenant-a", owner, kind, "private synthetic proposal summary", (f"synthetic-test:{proposal_id}",), NOW)


def test_learning_metrics_aggregate_review_memory_research_and_rejection_without_content():
    memory = _proposal("p-memory", LearningProposalType.MEMORY_UPDATE)
    research = _proposal("p-research", LearningProposalType.MODEL_PREFERENCE)
    rejected = _proposal("p-rejected", LearningProposalType.TOOL_PREFERENCE)
    evaluations = (
        (memory, evaluate_learning_proposal(memory, evidence_validated=True)),
        (research, evaluate_learning_proposal(research, evidence_validated=True)),
        (rejected, evaluate_learning_proposal(rejected, evidence_validated=False)),
    )
    snapshot = summarize_learning_metrics(evaluations, SCOPE)
    assert snapshot.proposals == 3 and snapshot.evidence_references == 3
    assert snapshot.human_review_required == 1
    assert snapshot.memory_approvals == 0 and snapshot.research_approvals == 1 and snapshot.rejected == 1
    assert snapshot.by_proposal_type == {"MEMORY_UPDATE": 1, "MODEL_PREFERENCE": 1, "TOOL_PREFERENCE": 1}
    assert "private synthetic proposal summary" not in repr(snapshot)
    assert not snapshot.automatic_applications and not snapshot.deployment_authority and not snapshot.execution_authority


def test_learning_metrics_reject_cross_scope_mismatch_and_duplicates():
    proposal = _proposal("p1", LearningProposalType.WORKFLOW_RECOMMENDATION)
    decision = evaluate_learning_proposal(proposal, evidence_validated=True)
    with pytest.raises(PermissionError, match="scope"):
        other = _proposal("other", LearningProposalType.WORKFLOW_RECOMMENDATION, owner="other")
        summarize_learning_metrics(((other, evaluate_learning_proposal(other, evidence_validated=True)),), SCOPE)
    with pytest.raises(ValueError, match="duplicate"):
        summarize_learning_metrics(((proposal, decision), (proposal, decision)), SCOPE)
