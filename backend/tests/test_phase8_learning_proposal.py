"""R119A every improvement begins as an evidence-linked proposal."""

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from backend.medar.learning_proposal import LearningProposal, LearningProposalType


NOW = datetime(2026, 10, 5, 4, tzinfo=timezone.utc)


def _proposal(kind):
    return LearningProposal(
        f"proposal-{kind.value}", "tenant-a", "owner-a", kind,
        "bounded advisory improvement", ("synthetic-test:evidence-1",), NOW,
    )


def test_all_roadmap_learning_types_are_proposals_without_authority():
    proposals = tuple(_proposal(kind) for kind in LearningProposalType)
    assert {proposal.proposal_type for proposal in proposals} == set(LearningProposalType)
    assert all(not proposal.execution_authority for proposal in proposals)
    assert all(not proposal.deployment_authority for proposal in proposals)
    assert all(not proposal.routing_authority for proposal in proposals)
    assert all(not proposal.memory_mutation_authority for proposal in proposals)


@pytest.mark.parametrize("field", (
    "execution_authority", "deployment_authority",
    "routing_authority", "memory_mutation_authority",
))
def test_proposal_cannot_self_grant_authority(field):
    with pytest.raises(ValueError):
        replace(_proposal(LearningProposalType.MEMORY_UPDATE), **{field: True})


def test_proposal_requires_safe_synthetic_evidence():
    with pytest.raises(ValueError):
        replace(_proposal(LearningProposalType.MODEL_PREFERENCE), evidence_references=())
    with pytest.raises(ValueError):
        replace(
            _proposal(LearningProposalType.MODEL_PREFERENCE),
            evidence_references=("external:evidence",),
        )
    with pytest.raises(PermissionError):
        replace(_proposal(LearningProposalType.MODEL_PREFERENCE), summary="api_key: synthetic")
