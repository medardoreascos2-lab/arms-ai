"""R112C encrypted decision journal and zero-write rejection boundaries."""

from dataclasses import replace
from datetime import datetime, timezone
import json

import pytest

from backend.medar.bound_memory_access import BoundMemoryRequest
from backend.medar.decision_journal import DecisionJournalEntry
from backend.medar.decision_journal_memory import (
    DecisionJournalMemory, DecisionJournalWriteAuthority, persist_decision_journal,
)
from backend.medar.durable_memory_encryption import AESGCMEphemeralMemoryEncryption
from backend.medar.durable_memory_record import (
    DurableMemoryDomain, DurableSensitivity, RetentionPolicy,
)
from backend.medar.encrypted_memory_envelope import open_memory_content
from backend.medar.memory_access import MemoryPurpose
from backend.medar.sqlite_encrypted_memory_store import SQLiteEncryptedMemoryStore
from backend.medar.sqlite_memory_store import MemoryScope
from backend.medar.trusted_runtime_identity import (
    LocalAdminIdentityAuthority, LocalIdentityAssignment, RuntimeMemoryPermission,
)
from backend.security.admin_authorization_v2 import AdminAuthorizationV2


NOW = datetime(2026, 10, 4, 12, tzinfo=timezone.utc)


def _memory(**changes):
    entry = DecisionJournalEntry(
        entry_id="synthetic-decision-1", decision="choose synthetic option",
        options=("A", "B"), recommendation="A", chosen_option="A",
        expected_outcome="synthetic lower risk", observed_outcome="synthetic no change",
        recorded_at=NOW,
    )
    values = dict(
        tenant_id="tenant-a", owner_id="owner-a", session_id="session-a",
        source_reference="synthetic-test:decision-source-1", entry=entry,
        lesson="no demonstrated benefit", recorded_at=NOW,
    )
    values.update(changes)
    return DecisionJournalMemory(**values)


def _setup(*, permissions=None):
    identity_authority = LocalAdminIdentityAuthority(
        AdminAuthorizationV2(token="synthetic-test-token"),
        LocalIdentityAssignment(
            "owner-a", "tenant-a", "session-a", "medar-local",
            MemoryPurpose.BUSINESS_ANALYSIS,
            permissions or frozenset({RuntimeMemoryPermission.READ, RuntimeMemoryPermission.WRITE}),
        ),
        clock=lambda: NOW,
    )
    identity = identity_authority.issue("synthetic-test-token")
    request = BoundMemoryRequest(
        "owner-a", "tenant-a", "session-a", "medar-local",
        DurableMemoryDomain.DECISION_JOURNAL, DurableSensitivity.SENSITIVE,
        MemoryPurpose.BUSINESS_ANALYSIS,
    )
    provider = AESGCMEphemeralMemoryEncryption(local_development_enabled=True)
    authority = DecisionJournalWriteAuthority(
        identity_authority, provider, local_development_enabled=True,
    )
    return authority, identity, request, provider


class SpyWriter:
    def __init__(self):
        self.writes = []

    def write(self, scope, envelope):
        self.writes.append((scope, envelope))


def test_journal_tracks_required_fields_without_self_authority():
    memory = _memory()
    document = json.loads(memory.content())
    assert document == {
        "actual_outcome": "synthetic no change",
        "chosen_option": "A",
        "decision": "choose synthetic option",
        "expected_outcome": "synthetic lower risk",
        "lesson": "no demonstrated benefit",
        "options": ["A", "B"],
        "recommendation": "A",
    }
    assert memory.domain is DurableMemoryDomain.DECISION_JOURNAL
    assert memory.sensitivity is DurableSensitivity.SENSITIVE
    assert memory.local_development_only and not memory.persistence_authorized
    assert not memory.execution_authority
    assert memory.entry.decision not in repr(memory)


def test_approved_journal_persists_ciphertext_only_and_round_trips(tmp_path):
    authority, identity, request, provider = _setup()
    memory = _memory()
    approval = authority.approve(identity, request, memory, RetentionPolicy.LONG_TERM)
    path = tmp_path / "decision-journal.db"
    try:
        with SQLiteEncryptedMemoryStore(path, read_only=False) as store:
            receipt = persist_decision_journal(
                authority, identity, request, memory, RetentionPolicy.LONG_TERM,
                approval, store,
            )
        assert receipt.algorithm_identifier == "AES-256-GCM"
        assert receipt.local_development_only and not receipt.production_deployment_authorized
        assert memory.content().encode() not in path.read_bytes()
        with SQLiteEncryptedMemoryStore(path) as store:
            envelope = store.get(MemoryScope("tenant-a", "owner-a"), memory.entry.entry_id, 1)
        assert envelope is not None
        plaintext = open_memory_content(
            envelope, provider, memory_id=memory.entry.entry_id,
            owner_id="owner-a", tenant_id="tenant-a",
            domain=DurableMemoryDomain.DECISION_JOURNAL,
            sensitivity=DurableSensitivity.SENSITIVE, version=1,
        )
        assert json.loads(plaintext) == json.loads(memory.content())
    finally:
        provider.close()


def test_rejected_scope_retention_approval_and_policy_make_zero_store_calls():
    authority, identity, request, provider = _setup()
    memory = _memory()
    approval = authority.approve(identity, request, memory, RetentionPolicy.LONG_TERM)
    writer = SpyWriter()
    try:
        rejected = (
            (replace(request, owner_id="other"), memory, RetentionPolicy.LONG_TERM, approval),
            (replace(request, tenant_id="other"), memory, RetentionPolicy.LONG_TERM, approval),
            (replace(request, claimed_role="admin"), memory, RetentionPolicy.LONG_TERM, approval),
            (request, memory, RetentionPolicy.SESSION, approval),
            (request, replace(memory, lesson="changed after approval"), RetentionPolicy.LONG_TERM, approval),
            (request, memory, RetentionPolicy.LONG_TERM, None),
        )
        for changed_request, changed_memory, retention, changed_approval in rejected:
            with pytest.raises(PermissionError):
                persist_decision_journal(
                    authority, identity, changed_request, changed_memory,
                    retention, changed_approval, writer,
                )
        assert writer.writes == []
    finally:
        provider.close()


def test_read_only_identity_and_non_synthetic_source_cannot_approve():
    authority, identity, request, provider = _setup(
        permissions=frozenset({RuntimeMemoryPermission.READ}),
    )
    try:
        with pytest.raises(PermissionError):
            authority.approve(identity, request, _memory(), RetentionPolicy.LONG_TERM)
        assert not authority._approvals
    finally:
        provider.close()
    authority, identity, request, provider = _setup()
    try:
        with pytest.raises(PermissionError):
            authority.approve(
                identity, request, _memory(source_reference="real-source"),
                RetentionPolicy.LONG_TERM,
            )
        assert not authority._approvals
    finally:
        provider.close()


@pytest.mark.parametrize("change", [
    {"source_reference": ""}, {"local_development_only": False},
    {"persistence_authorized": True}, {"execution_authority": True},
    {"domain": DurableMemoryDomain.BUSINESS},
    {"sensitivity": DurableSensitivity.PUBLIC},
    {"recorded_at": datetime(2026, 10, 4)},
])
def test_journal_rejects_weakened_scope_or_authority(change):
    with pytest.raises(ValueError):
        _memory(**change)


def test_journal_rejects_secret_like_lesson_and_unbounded_entry():
    with pytest.raises(PermissionError):
        _memory(lesson="api_key: synthetic")
    original = _memory().entry
    unbounded = DecisionJournalEntry(
        original.entry_id, "x" * 1025, original.options, original.recommendation,
        original.chosen_option, original.expected_outcome, original.observed_outcome,
        original.recorded_at,
    )
    with pytest.raises(ValueError):
        _memory(entry=unbounded)
