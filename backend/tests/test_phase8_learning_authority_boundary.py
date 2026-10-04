"""R119C learning cannot escalate any protected authority dimension."""

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from backend.medar.learning_authority_boundary import (
    RuntimeAuthoritySnapshot, enforce_learning_authority_boundary,
)
from backend.medar.learning_gate import evaluate_learning_proposal
from backend.medar.learning_proposal import LearningProposal, LearningProposalType


NOW = datetime(2026, 10, 5, 6, tzinfo=timezone.utc)
AUTHORITY = RuntimeAuthoritySnapshot(
    "tenant-a", "owner-a", False, False, False, False, "READ_ONLY", False,
)


def _proposal(kind):
    return LearningProposal(
        f"proposal-{kind.value}", "tenant-a", "owner-a", kind,
        "bounded proposal", ("synthetic-test:evidence",), NOW,
    )


def test_every_learning_type_leaves_all_protected_authority_unchanged():
    for kind in LearningProposalType:
        proposal = _proposal(kind)
        decision = evaluate_learning_proposal(
            proposal, evidence_validated=True, human_approved=True,
        )
        result = enforce_learning_authority_boundary(proposal, decision, AUTHORITY)
        assert result.before == result.after == AUTHORITY
        assert not result.authority_changed
        assert result.applied_changes == ()
        assert not result.after.broker_authority
        assert not result.after.paper_authority
        assert not result.after.live_authority
        assert not result.after.production_autonomy
        assert result.after.computer_permission_level == "READ_ONLY"
        assert not result.after.secret_access
        assert result.after.tenant_id == "tenant-a"


def test_cross_tenant_owner_or_mismatched_decision_is_denied():
    proposal = _proposal(LearningProposalType.MEMORY_UPDATE)
    decision = evaluate_learning_proposal(
        proposal, evidence_validated=True, human_approved=True,
    )
    for changed in (
        replace(proposal, tenant_id="other"),
        replace(proposal, owner_id="other"),
    ):
        with pytest.raises(PermissionError):
            enforce_learning_authority_boundary(changed, decision, AUTHORITY)
    other = replace(decision, proposal_id="other")
    with pytest.raises(PermissionError):
        enforce_learning_authority_boundary(proposal, other, AUTHORITY)
