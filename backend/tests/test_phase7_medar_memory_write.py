"""R86C MEDAR proposal-only memory write tests."""

import pytest

from backend.medar.memory_types import MemoryDomain, MemorySensitivity
from backend.medar.memory_write import (
    MemoryApprovalPolicy,
    MemoryImportance,
    MemoryRetention,
    MemoryWriteProposal,
)


def _proposal(**overrides):
    values = dict(
        proposal_id="proposal-1", tenant_id="tenant-1", user_id="user-1",
        candidate="User prefers concise reports", domain=MemoryDomain.PERSONAL,
        importance=MemoryImportance.NORMAL, sensitivity=MemorySensitivity.INTERNAL,
        confidence=0.9, retention=MemoryRetention.LONG_TERM,
        source="conversation:req-1", approval_policy=MemoryApprovalPolicy.POLICY_REVIEW,
    )
    values.update(overrides)
    return MemoryWriteProposal(**values)


def test_memory_candidate_is_a_non_authorizing_proposal():
    proposal = _proposal()
    assert proposal.candidate == "User prefers concise reports"
    assert proposal.persistence_authorized is False


def test_proposal_cannot_claim_persistence_authority():
    with pytest.raises(ValueError, match="cannot authorize"):
        _proposal(persistence_authorized=True)


def test_sensitive_and_permanent_memory_require_explicit_user_approval():
    with pytest.raises(ValueError, match="explicit user"):
        _proposal(sensitivity=MemorySensitivity.SENSITIVE)
    with pytest.raises(ValueError, match="explicit user"):
        _proposal(retention=MemoryRetention.PERMANENT)
    assert _proposal(
        sensitivity=MemorySensitivity.RESTRICTED,
        approval_policy=MemoryApprovalPolicy.EXPLICIT_USER,
    ).persistence_authorized is False


def test_working_memory_cannot_be_proposed_for_durable_retention():
    with pytest.raises(ValueError, match="outlive"):
        _proposal(domain=MemoryDomain.WORKING)
