"""R119B learning gate allows only memory or research review states."""

from datetime import datetime, timezone

from backend.medar.learning_gate import LearningGateStatus, evaluate_learning_proposal
from backend.medar.learning_proposal import LearningProposal, LearningProposalType


NOW = datetime(2026, 10, 5, 5, tzinfo=timezone.utc)


def _proposal(kind):
    return LearningProposal(
        f"proposal-{kind.value}", "tenant-a", "owner-a", kind,
        "bounded proposal", ("synthetic-test:evidence",), NOW,
    )


def test_invalid_evidence_is_rejected_without_authority():
    decision = evaluate_learning_proposal(
        _proposal(LearningProposalType.MODEL_PREFERENCE), evidence_validated=False,
    )
    assert decision.status is LearningGateStatus.REJECTED
    assert not decision.production_deployment_authorized
    assert not decision.execution_authorized
    assert not decision.automatic_application_authorized


def test_memory_update_requires_human_review_then_memory_only_approval():
    proposal = _proposal(LearningProposalType.MEMORY_UPDATE)
    review = evaluate_learning_proposal(proposal, evidence_validated=True)
    approved = evaluate_learning_proposal(
        proposal, evidence_validated=True, human_approved=True,
    )
    assert review.status is LearningGateStatus.REQUIRES_HUMAN_REVIEW
    assert approved.status is LearningGateStatus.APPROVED_FOR_MEMORY
    assert not approved.automatic_application_authorized


def test_non_memory_improvements_are_research_only():
    statuses = {
        evaluate_learning_proposal(_proposal(kind), evidence_validated=True).status
        for kind in LearningProposalType if kind is not LearningProposalType.MEMORY_UPDATE
    }
    assert statuses == {LearningGateStatus.APPROVED_FOR_RESEARCH}
    assert "AUTO_DEPLOY_TO_PRODUCTION" not in {status.value for status in LearningGateStatus}
