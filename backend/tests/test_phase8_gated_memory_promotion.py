"""R108L synthetic-only encrypted durable promotion and zero-write denials."""

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from backend.medar.bound_memory_access import BoundMemoryRequest
from backend.medar.durable_memory_encryption import EphemeralTestMemoryEncryption
from backend.medar.durable_memory_record import DurableMemoryDomain, DurableSensitivity, RetentionPolicy
from backend.medar.durable_write_authority import DurableMemoryWriteAuthority, DurableWriteStatus
from backend.medar.gated_memory_promotion import promote_synthetic_memory
from backend.medar.memory_access import MemoryPurpose
from backend.medar.memory_candidates import CandidateSource, CandidateSourceType, MemoryCandidateExtractor
from backend.medar.memory_importance import ImportanceEvidence
from backend.medar.session_working_memory import SessionWorkingMemory
from backend.medar.sqlite_encrypted_memory_store import SQLiteEncryptedMemoryStore
from backend.medar.sqlite_memory_store import MemoryScope
from backend.medar.trusted_runtime_identity import LocalAdminIdentityAuthority, LocalIdentityAssignment, RuntimeMemoryPermission
from backend.security.admin_authorization_v2 import AdminAuthorizationV2


NOW = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)
EVIDENCE = ImportanceEvidence(technical_solution=True, observed_outcome=True)


def _setup(provider=None, *, synthetic=True):
    authority = LocalAdminIdentityAuthority(
        AdminAuthorizationV2(token="synthetic-test-token"),
        LocalIdentityAssignment("owner-a", "tenant-a", "session-a", "medar-local",
                                MemoryPurpose.TECHNICAL_ASSISTANCE,
                                frozenset({RuntimeMemoryPermission.READ, RuntimeMemoryPermission.WRITE})),
        clock=lambda: NOW,
    )
    identity = authority.issue("synthetic-test-token")
    reference = "synthetic-test:conversation-1/turn-4" if synthetic else "conversation-1/turn-4"
    candidate = MemoryCandidateExtractor().extract(CandidateSource(
        "tenant-a", "owner-a", reference, CandidateSourceType.TASK_OUTCOME,
        DurableMemoryDomain.TECHNICAL, "Outcome: schema recovery passed",
    )).candidates[0]
    candidate = replace(candidate, confidence=0.9)
    session = SessionWorkingMemory("session-a", "tenant-a", "owner-a")
    session.add_candidate(candidate)
    request = BoundMemoryRequest("owner-a", "tenant-a", "session-a", "medar-local",
                                 DurableMemoryDomain.TECHNICAL, DurableSensitivity.INTERNAL,
                                 MemoryPurpose.TECHNICAL_ASSISTANCE)
    gate = DurableMemoryWriteAuthority(authority, test_provider=provider, local_test_enabled=provider is not None)
    approval = gate.approve_candidate(identity, session.snapshot(), candidate.candidate_id)
    return gate, identity, request, session.snapshot(), candidate, approval


class SpyEncryptedStore:
    def __init__(self):
        self.calls = []

    def write(self, scope, envelope):
        self.calls.append((scope, envelope))


def test_synthetic_promotion_persists_only_ciphertext_with_session_source(tmp_path):
    path = tmp_path / "memory-envelopes.db"
    with EphemeralTestMemoryEncryption(local_test_enabled=True) as provider:
        gate, identity, request, snapshot, candidate, approval = _setup(provider)
        with SQLiteEncryptedMemoryStore(path, read_only=False) as store:
            receipt = promote_synthetic_memory(gate, identity, request, snapshot, candidate.candidate_id,
                                               EVIDENCE, RetentionPolicy.LONG_TERM, approval, store, clock=lambda: NOW)
        assert receipt.local_test_only and not receipt.production_promotion_authorized
        assert receipt.session_id == "session-a"
        assert receipt.source_reference == "synthetic-test:conversation-1/turn-4"
        with SQLiteEncryptedMemoryStore(path) as store:
            envelope = store.get(MemoryScope("tenant-a", "owner-a"), candidate.candidate_id, 1)
            assert envelope is not None
            assert provider.decrypt(envelope.payload, associated_data=envelope.associated_data()).decode() == candidate.content
            assert store.get(MemoryScope("tenant-b", "owner-a"), candidate.candidate_id, 1) is None
        assert candidate.content.encode() not in path.read_bytes()


def test_blocked_identity_policy_and_encryption_have_zero_store_writes():
    with EphemeralTestMemoryEncryption(local_test_enabled=True) as provider:
        gate, identity, request, snapshot, candidate, approval = _setup(provider)
        spy = SpyEncryptedStore()
        for changed_request in (replace(request, owner_id="other"), replace(request, tenant_id="other"), replace(request, session_id="other")):
            with pytest.raises(PermissionError):
                promote_synthetic_memory(gate, identity, changed_request, snapshot, candidate.candidate_id,
                                         EVIDENCE, RetentionPolicy.LONG_TERM, approval, spy, clock=lambda: NOW)
        assert spy.calls == []
        assert gate.evaluate(identity, request, snapshot, candidate.candidate_id, EVIDENCE, RetentionPolicy.LONG_TERM, approval).status is DurableWriteStatus.AUTHORIZED
    no_crypto, identity, request, snapshot, candidate, approval = _setup()
    spy = SpyEncryptedStore()
    with pytest.raises(PermissionError):
        promote_synthetic_memory(no_crypto, identity, request, snapshot, candidate.candidate_id,
                                 EVIDENCE, RetentionPolicy.LONG_TERM, approval, spy, clock=lambda: NOW)
    assert spy.calls == []


def test_unmarked_or_sensitive_candidate_cannot_get_test_write_authority():
    with EphemeralTestMemoryEncryption(local_test_enabled=True) as provider:
        gate, identity, request, snapshot, candidate, approval = _setup(provider, synthetic=False)
        result = gate.evaluate(identity, request, snapshot, candidate.candidate_id, EVIDENCE, RetentionPolicy.LONG_TERM, approval)
        assert result.status is DurableWriteStatus.BLOCKED_ENCRYPTION
        marked_gate, identity, request, snapshot, candidate, approval = _setup(provider)
        sensitive = replace(candidate, sensitivity=DurableSensitivity.PERSONAL)
        sensitive_snapshot = replace(snapshot, candidate_durable=(sensitive,))
        sensitive_request = replace(request, sensitivity=DurableSensitivity.PERSONAL)
        result = marked_gate.evaluate(identity, sensitive_request, sensitive_snapshot, candidate.candidate_id,
                                      EVIDENCE, RetentionPolicy.LONG_TERM, approval)
        assert result.status is DurableWriteStatus.BLOCKED_SENSITIVITY
