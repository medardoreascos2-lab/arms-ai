"""AES-GCM authentication, scope binding, corruption, and rotation tests."""

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from backend.medar.aead_memory_key_rotation import AESGCMEphemeralKeyRegistry
from backend.medar.durable_memory_encryption import AESGCMEphemeralMemoryEncryption
from backend.medar.durable_memory_record import (
    DurableMemoryDomain, DurableMemoryRecord, DurableMemoryType,
    DurableSensitivity, MemoryLifecycle, ProvenanceClass, RetentionPolicy,
    content_digest,
)
from backend.medar.encrypted_memory_envelope import (
    EncryptedMemoryEnvelope, open_memory_content, seal_memory_content,
)
from backend.medar.memory_key_rotation import MemoryKeyState
from backend.medar.memory_provenance import MemoryOrigin, MemoryProvenance


NOW = datetime(2026, 10, 4, 12, tzinfo=timezone.utc)


def _record():
    content = "synthetic sensitive decision journal"
    return DurableMemoryRecord(
        "journal-1", "owner-a", "tenant-a", DurableMemoryDomain.DECISION_JOURNAL,
        DurableMemoryType.DECISION, content, content_digest(content), "synthetic_test",
        "synthetic-test:journal-1",
        MemoryProvenance(
            "synthetic-test:journal-1", MemoryOrigin.OBSERVED, NOW,
            "tenant-a", "owner-a", "session-a", 1.0,
        ),
        ProvenanceClass.DIRECT_OBSERVATION, 1.0, 0.8,
        DurableSensitivity.SENSITIVE, NOW, NOW, None,
        RetentionPolicy.LONG_TERM, MemoryLifecycle.ACTIVE, 1,
    )


def _open(envelope, provider, **changes):
    values = dict(
        memory_id="journal-1", owner_id="owner-a", tenant_id="tenant-a",
        domain=DurableMemoryDomain.DECISION_JOURNAL,
        sensitivity=DurableSensitivity.SENSITIVE, version=1,
    )
    values.update(changes)
    return open_memory_content(envelope, provider, **values)


def test_aesgcm_round_trip_uses_unique_nonces_and_hides_plaintext():
    with AESGCMEphemeralMemoryEncryption(local_development_enabled=True) as provider:
        envelopes = [seal_memory_content(_record(), provider) for _ in range(64)]
        nonces = {item.payload.nonce_metadata for item in envelopes}
        assert len(nonces) == len(envelopes)
        for envelope in envelopes:
            assert envelope.payload.algorithm_identifier == "AES-256-GCM"
            assert envelope.content_hash is None
            assert _record().content.encode() not in envelope.to_bytes()
            assert _open(envelope, provider) == _record().content


def test_ciphertext_aad_version_truncation_and_corrupt_envelope_fail_closed():
    with AESGCMEphemeralMemoryEncryption(local_development_enabled=True) as provider:
        envelope = seal_memory_content(_record(), provider)
        payload = envelope.payload
        tampered = bytes([payload.ciphertext[0] ^ 1]) + payload.ciphertext[1:]
        for changed in (
            replace(envelope, payload=replace(payload, ciphertext=tampered)),
            replace(envelope, payload=replace(payload, ciphertext=payload.ciphertext[:-1])),
            replace(envelope, payload=replace(payload, key_version="wrong-version")),
        ):
            with pytest.raises(PermissionError):
                _open(changed, provider)
        with pytest.raises(PermissionError):
            _open(replace(envelope, owner_id="owner-b"), provider, owner_id="owner-b")
        with pytest.raises(PermissionError):
            _open(replace(envelope, tenant_id="tenant-b"), provider, tenant_id="tenant-b")
        wire = envelope.to_bytes()
        with pytest.raises(ValueError):
            EncryptedMemoryEnvelope.from_bytes(wire[:-1])
        with pytest.raises(ValueError):
            EncryptedMemoryEnvelope.from_bytes(wire.replace(b'"version":1', b'"version":2,"version":1'))


def test_wrong_key_cannot_decrypt_even_when_payload_metadata_is_rebound():
    with AESGCMEphemeralMemoryEncryption(
        local_development_enabled=True, key_version="v1",
    ) as first, AESGCMEphemeralMemoryEncryption(
        local_development_enabled=True, key_version="v1",
    ) as second:
        envelope = seal_memory_content(_record(), first)
        rebound = replace(
            envelope,
            payload=replace(envelope.payload, key_reference=second.key_reference),
        )
        with pytest.raises(PermissionError):
            _open(rebound, second)


def test_rotation_uses_new_active_key_and_revocation_blocks_old_key():
    with AESGCMEphemeralKeyRegistry() as registry:
        first = AESGCMEphemeralMemoryEncryption(
            local_development_enabled=True, key_version="v1",
        )
        registry.register(first)
        old_envelope = registry.encrypt(_record())
        registry.transition("v1", MemoryKeyState.DECRYPT_ONLY)
        second = AESGCMEphemeralMemoryEncryption(
            local_development_enabled=True, key_version="v2",
        )
        registry.register(second)
        new_envelope = registry.encrypt(_record())
        assert new_envelope.payload.key_version == "v2"
        assert registry.decrypt(old_envelope) == _record().content
        assert registry.decrypt(new_envelope) == _record().content
        registry.transition("v1", MemoryKeyState.REVOKED)
        with pytest.raises(PermissionError):
            registry.decrypt(old_envelope)
