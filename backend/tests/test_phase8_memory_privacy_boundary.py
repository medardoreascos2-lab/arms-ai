"""R108M explicit zero-side-effect and content-free privacy regression."""

from dataclasses import replace
import sqlite3

import pytest

from backend.medar.bound_memory_access import BoundMemoryAccess
from backend.medar.durable_memory_encryption import EphemeralTestMemoryEncryption
from backend.medar.durable_memory_record import DurableSensitivity, RetentionPolicy
from backend.medar.durable_write_authority import DurableWriteStatus, DurableMemoryWriteAuthority
from backend.medar.gated_memory_promotion import promote_synthetic_memory
from backend.medar.memory_redaction import redacted_memory_event
from backend.medar.sqlite_encrypted_memory_store import SQLiteEncryptedMemoryStore
from backend.medar.sqlite_memory_store import MemoryScope
from backend.tests.test_phase8_gated_memory_promotion import _setup, EVIDENCE, NOW, SpyEncryptedStore
from backend.tests.test_phase8_encrypted_memory_envelope import _record


class ReadSpy:
    def __init__(self):
        self.calls = []

    def get(self, scope, memory_id):
        self.calls.append((scope, memory_id))
        return None


def test_forged_identity_cross_owner_and_tenant_have_zero_reads_and_writes():
    with EphemeralTestMemoryEncryption(local_test_enabled=True) as provider:
        gate, identity, request, snapshot, candidate, approval = _setup(provider)
        store = ReadSpy()
        reader = BoundMemoryAccess(gate._identity_authority, store)
        writer = SpyEncryptedStore()
        for bad_identity, bad_request in (
            (replace(identity, owner_id="other"), request),
            (identity, replace(request, owner_id="other")),
            (identity, replace(request, tenant_id="other")),
        ):
            with pytest.raises(PermissionError):
                reader.get(bad_identity, bad_request, candidate.candidate_id)
            with pytest.raises(PermissionError):
                promote_synthetic_memory(gate, bad_identity, bad_request, snapshot, candidate.candidate_id,
                                         EVIDENCE, RetentionPolicy.LONG_TERM, approval, writer, clock=lambda: NOW)
        assert store.calls == []
        assert writer.calls == []


def test_missing_encryption_or_sensitive_classification_never_writes():
    gate, identity, request, snapshot, candidate, approval = _setup()
    writer = SpyEncryptedStore()
    with pytest.raises(PermissionError):
        promote_synthetic_memory(gate, identity, request, snapshot, candidate.candidate_id,
                                 EVIDENCE, RetentionPolicy.LONG_TERM, approval, writer, clock=lambda: NOW)
    assert writer.calls == []
    sensitive_snapshot = replace(snapshot, candidate_durable=(replace(candidate, sensitivity=DurableSensitivity.PERSONAL),))
    sensitive_request = replace(request, sensitivity=DurableSensitivity.PERSONAL)
    assert gate.evaluate(identity, sensitive_request, sensitive_snapshot, candidate.candidate_id,
                         EVIDENCE, RetentionPolicy.LONG_TERM, approval).status is DurableWriteStatus.BLOCKED_SENSITIVITY
    assert writer.calls == []


def test_corrupt_ciphertext_returns_no_plaintext_after_restart(tmp_path):
    path = tmp_path / "synthetic-envelopes.db"
    with EphemeralTestMemoryEncryption(local_test_enabled=True) as provider:
        gate, identity, request, snapshot, candidate, approval = _setup(provider)
        with SQLiteEncryptedMemoryStore(path, read_only=False) as store:
            promote_synthetic_memory(gate, identity, request, snapshot, candidate.candidate_id,
                                     EVIDENCE, RetentionPolicy.LONG_TERM, approval, store, clock=lambda: NOW)
        with sqlite3.connect(path) as connection:
            connection.execute("UPDATE encrypted_envelopes SET envelope = ?", (b"corrupt",))
        with SQLiteEncryptedMemoryStore(path) as recovered:
            with pytest.raises(ValueError):
                recovered.get(MemoryScope("tenant-a", "owner-a"), candidate.candidate_id, 1)


def test_denial_logs_events_and_model_claim_do_not_expose_or_authorize_content(caplog, capsys):
    with EphemeralTestMemoryEncryption(local_test_enabled=True) as provider:
        gate, identity, request, snapshot, candidate, approval = _setup(provider)
        fabricated = replace(approval, approval_id="model-output-claims-approval")
        decision = gate.evaluate(identity, request, snapshot, candidate.candidate_id,
                                 EVIDENCE, RetentionPolicy.LONG_TERM, fabricated)
        assert decision.status is DurableWriteStatus.REVIEW_REQUIRED
        writer = SpyEncryptedStore()
        with pytest.raises(PermissionError):
            promote_synthetic_memory(gate, identity, request, snapshot, candidate.candidate_id,
                                     EVIDENCE, RetentionPolicy.LONG_TERM, fabricated, writer, clock=lambda: NOW)
        event = redacted_memory_event(_record(), "DENY")
        captured = capsys.readouterr()
        observed = repr(decision) + repr(event) + captured.out + captured.err
        observed += " ".join(item.getMessage() for item in caplog.records)
        assert candidate.content not in observed
        assert _record().content not in observed
        assert writer.calls == []
