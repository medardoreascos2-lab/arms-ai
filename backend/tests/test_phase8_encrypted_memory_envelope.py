"""R108J synthetic encrypted memory envelope and metadata binding tests."""

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from backend.medar.durable_memory_encryption import EphemeralTestMemoryEncryption
from backend.medar.durable_memory_record import (
    DurableMemoryDomain, DurableMemoryRecord, DurableMemoryType,
    DurableSensitivity, MemoryLifecycle, ProvenanceClass, RetentionPolicy,
    content_digest,
)
from backend.medar.encrypted_memory_envelope import (
    EncryptedMemoryEnvelope, open_memory_content, seal_memory_content,
)
from backend.medar.memory_provenance import MemoryOrigin, MemoryProvenance


NOW = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)


def _record(sensitivity=DurableSensitivity.INTERNAL):
    content = "synthetic schema migration lesson"
    return DurableMemoryRecord(
        "memory-1", "owner-a", "tenant-a", DurableMemoryDomain.TECHNICAL,
        DurableMemoryType.FACT, content, content_digest(content), "synthetic_test",
        "source-1", MemoryProvenance("source-1", MemoryOrigin.OBSERVED, NOW, "tenant-a", "owner-a", "context", 0.9),
        ProvenanceClass.DIRECT_OBSERVATION, 0.9, 0.8, sensitivity,
        NOW, NOW, None, RetentionPolicy.LONG_TERM, MemoryLifecycle.ACTIVE, 1,
    )


def _open(envelope, provider, **changes):
    values = dict(
        memory_id="memory-1", owner_id="owner-a", tenant_id="tenant-a",
        domain=DurableMemoryDomain.TECHNICAL, sensitivity=DurableSensitivity.INTERNAL,
        version=1,
    )
    values.update(changes)
    return open_memory_content(envelope, provider, **values)


def test_envelope_round_trip_has_no_plaintext_and_binds_scope_metadata():
    record = _record()
    with EphemeralTestMemoryEncryption(local_test_enabled=True) as provider:
        envelope = seal_memory_content(record, provider)
        wire = envelope.to_bytes()
        assert record.content.encode() not in wire
        assert record.content not in repr(envelope)
        assert envelope.payload.local_test_only
        loaded = EncryptedMemoryEnvelope.from_bytes(wire)
        assert _open(loaded, provider) == record.content
        for change in (
            {"memory_id": "other"}, {"owner_id": "other"},
            {"tenant_id": "other"}, {"domain": DurableMemoryDomain.RESEARCH},
            {"sensitivity": DurableSensitivity.PUBLIC}, {"version": 2},
        ):
            with pytest.raises(PermissionError):
                _open(loaded, provider, **change)


def test_corrupt_envelope_or_ciphertext_returns_no_plaintext():
    with EphemeralTestMemoryEncryption(local_test_enabled=True) as provider:
        envelope = seal_memory_content(_record(), provider)
        with pytest.raises(ValueError):
            EncryptedMemoryEnvelope.from_bytes(envelope.to_bytes()[:-1])
        with pytest.raises(ValueError):
            EncryptedMemoryEnvelope.from_bytes(envelope.to_bytes().replace(b'"version":1', b'"version":2,"version":1'))
        tampered = replace(envelope, payload=replace(envelope.payload, ciphertext=envelope.payload.ciphertext[:-1]))
        with pytest.raises(PermissionError):
            _open(tampered, provider)
        with pytest.raises(PermissionError):
            _open(replace(envelope, owner_id="other"), provider, owner_id="other")


def test_sensitive_record_and_forged_provider_are_denied():
    with EphemeralTestMemoryEncryption(local_test_enabled=True) as provider:
        with pytest.raises(PermissionError):
            seal_memory_content(_record(DurableSensitivity.PERSONAL), provider)
        class ForgedProvider:
            production_ready = False
            local_test_only = True
            def encrypt(self, *args, **kwargs):
                raise AssertionError("forged provider must not receive plaintext")
        with pytest.raises(PermissionError):
            seal_memory_content(_record(), ForgedProvider())
