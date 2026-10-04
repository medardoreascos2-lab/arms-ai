"""R108F separate durable-write authority remains fail-closed."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from backend.medar.bound_memory_access import BoundMemoryRequest
from backend.medar.durable_memory_record import DurableMemoryDomain, DurableSensitivity, RetentionPolicy
from backend.medar.durable_write_authority import (
    CandidateApproval, DurableMemoryWriteAuthority, DurableWriteStatus,
)
from backend.medar.memory_access import MemoryPurpose
from backend.medar.memory_candidates import CandidateSource, CandidateSourceType, MemoryCandidateExtractor
from backend.medar.memory_importance import ImportanceEvidence
from backend.medar.session_working_memory import SessionWorkingMemory
from backend.medar.trusted_runtime_identity import LocalAdminIdentityAuthority, LocalIdentityAssignment, RuntimeMemoryPermission
from backend.security.admin_authorization_v2 import AdminAuthorizationV2


NOW = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)
EVIDENCE = ImportanceEvidence(technical_solution=True, observed_outcome=True)


def _setup(*, verified=True, clock=lambda: NOW, permissions=None):
    authority = LocalAdminIdentityAuthority(
        AdminAuthorizationV2(token="synthetic-test-token"),
        LocalIdentityAssignment(
            "owner-a", "tenant-a", "session-a", "medar-local",
            MemoryPurpose.TECHNICAL_ASSISTANCE,
            permissions or frozenset({RuntimeMemoryPermission.READ, RuntimeMemoryPermission.WRITE}),
        ), clock=clock,
    )
    identity = authority.issue("synthetic-test-token")
    source = CandidateSource(
        "tenant-a", "owner-a", "conversation-1/turn-4", CandidateSourceType.TASK_OUTCOME,
        DurableMemoryDomain.TECHNICAL, "Outcome: schema recovery passed",
    )
    candidate = MemoryCandidateExtractor().extract(source).candidates[0]
    if verified:
        candidate = replace(candidate, confidence=0.9)
    session = SessionWorkingMemory("session-a", "tenant-a", "owner-a")
    session.add_candidate(candidate)
    request = BoundMemoryRequest(
        "owner-a", "tenant-a", "session-a", "medar-local",
        DurableMemoryDomain.TECHNICAL, DurableSensitivity.INTERNAL,
        MemoryPurpose.TECHNICAL_ASSISTANCE,
    )
    return authority, identity, session.snapshot(), request, candidate


def test_policy_review_and_candidate_approval_are_distinct_from_read_authority():
    authority, identity, snapshot, request, candidate = _setup(verified=False)
    writes = DurableMemoryWriteAuthority(authority)
    approval = writes.approve_candidate(identity, snapshot, candidate.candidate_id)
    decision = writes.evaluate(identity, request, snapshot, candidate.candidate_id, EVIDENCE, RetentionPolicy.LONG_TERM, approval)
    assert decision.status is DurableWriteStatus.REVIEW_REQUIRED
    assert not decision.persistence_performed
    read_authority, read_identity, read_snapshot, read_request, read_candidate = _setup(
        permissions=frozenset({RuntimeMemoryPermission.READ}),
    )
    read_writes = DurableMemoryWriteAuthority(read_authority)
    with pytest.raises(PermissionError):
        read_writes.approve_candidate(read_identity, read_snapshot, read_candidate.candidate_id)
    assert read_writes.evaluate(read_identity, read_request, read_snapshot, read_candidate.candidate_id, EVIDENCE, RetentionPolicy.LONG_TERM).status is DurableWriteStatus.BLOCKED_IDENTITY


def test_approved_non_sensitive_candidate_still_fails_without_validated_encryption():
    authority, identity, snapshot, request, candidate = _setup()
    writes = DurableMemoryWriteAuthority(authority)
    no_approval = writes.evaluate(identity, request, snapshot, candidate.candidate_id, EVIDENCE, RetentionPolicy.LONG_TERM)
    assert no_approval.status is DurableWriteStatus.REVIEW_REQUIRED
    approval = writes.approve_candidate(identity, snapshot, candidate.candidate_id)
    ready_except_crypto = writes.evaluate(identity, request, snapshot, candidate.candidate_id, EVIDENCE, RetentionPolicy.LONG_TERM, approval)
    assert ready_except_crypto.status is DurableWriteStatus.BLOCKED_ENCRYPTION
    assert ready_except_crypto.status is not DurableWriteStatus.AUTHORIZED
    forged = replace(approval, approval_id="model-output-claim")
    assert writes.evaluate(identity, request, snapshot, candidate.candidate_id, EVIDENCE, RetentionPolicy.LONG_TERM, forged).status is DurableWriteStatus.REVIEW_REQUIRED
    changed_candidate = replace(candidate, content="different synthetic outcome")
    changed_snapshot = replace(snapshot, candidate_durable=(changed_candidate,))
    assert writes.evaluate(identity, request, changed_snapshot, candidate.candidate_id, EVIDENCE, RetentionPolicy.LONG_TERM, approval).status is DurableWriteStatus.REVIEW_REQUIRED
    assert writes.evaluate(identity, request, snapshot, candidate.candidate_id, EVIDENCE, RetentionPolicy.SESSION, approval).status is DurableWriteStatus.BLOCKED_RETENTION


@pytest.mark.parametrize("change", [
    {"owner_id": "other"}, {"tenant_id": "other"}, {"session_id": "other"},
    {"service_id": "other"}, {"claimed_role": "admin"},
    {"claimed_permission": RuntimeMemoryPermission.READ},
])
def test_spoofed_write_scope_fails_before_approval(change):
    authority, identity, snapshot, request, candidate = _setup()
    writes = DurableMemoryWriteAuthority(authority)
    approval = writes.approve_candidate(identity, snapshot, candidate.candidate_id)
    result = writes.evaluate(identity, replace(request, **change), snapshot, candidate.candidate_id, EVIDENCE, RetentionPolicy.LONG_TERM, approval)
    assert result.status is DurableWriteStatus.BLOCKED_IDENTITY


def test_expired_identity_cannot_approve_or_evaluate():
    current = [NOW]
    authority, identity, snapshot, request, candidate = _setup(clock=lambda: current[0])
    writes = DurableMemoryWriteAuthority(authority)
    current[0] = NOW + timedelta(minutes=16)
    with pytest.raises(PermissionError):
        writes.approve_candidate(identity, snapshot, candidate.candidate_id)
    assert writes.evaluate(identity, request, snapshot, candidate.candidate_id, EVIDENCE, RetentionPolicy.LONG_TERM).status is DurableWriteStatus.BLOCKED_IDENTITY
