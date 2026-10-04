"""R108K ephemeral key rotation and revoked-key regression tests."""

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from backend.medar.durable_memory_encryption import EphemeralTestMemoryEncryption
from backend.medar.durable_memory_record import (
    DurableMemoryDomain, DurableMemoryRecord, DurableMemoryType,
    DurableSensitivity, MemoryLifecycle, ProvenanceClass, RetentionPolicy,
    content_digest,
)
from backend.medar.memory_key_rotation import EphemeralMemoryKeyRegistry, MemoryKeyState
from backend.medar.memory_provenance import MemoryOrigin, MemoryProvenance


NOW = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)


def _record():
    content = "synthetic schema recovery lesson"
    return DurableMemoryRecord(
        "memory-1", "owner-a", "tenant-a", DurableMemoryDomain.TECHNICAL,
        DurableMemoryType.FACT, content, content_digest(content), "synthetic_test",
        "source-1", MemoryProvenance("source-1", MemoryOrigin.OBSERVED, NOW, "tenant-a", "owner-a", "context", 0.9),
        ProvenanceClass.DIRECT_OBSERVATION, 0.9, 0.8, DurableSensitivity.INTERNAL,
        NOW, NOW, None, RetentionPolicy.LONG_TERM, MemoryLifecycle.ACTIVE, 1,
    )


def test_rotation_uses_active_for_new_writes_and_decrypt_only_for_old_records():
    with EphemeralMemoryKeyRegistry() as registry:
        first = EphemeralTestMemoryEncryption(local_test_enabled=True, key_version="v1")
        registry.register(first)
        old_envelope = registry.encrypt(_record())
        assert registry.decrypt(old_envelope) == _record().content
        registry.transition("v1", MemoryKeyState.DECRYPT_ONLY)
        with pytest.raises(PermissionError):
            registry.encrypt(_record())
        second = EphemeralTestMemoryEncryption(local_test_enabled=True, key_version="v2")
        registry.register(second)
        new_envelope = registry.encrypt(_record())
        assert new_envelope.payload.key_version == "v2"
        assert registry.decrypt(old_envelope) == _record().content
        assert registry.decrypt(new_envelope) == _record().content
        assert [item.state for item in registry.metadata()] == [MemoryKeyState.DECRYPT_ONLY, MemoryKeyState.ACTIVE]
        registry.transition("v1", MemoryKeyState.RETIRED)
        with pytest.raises(PermissionError):
            registry.decrypt(old_envelope)
        registry.transition("v1", MemoryKeyState.REVOKED)
        with pytest.raises(PermissionError):
            registry.decrypt(old_envelope)


def test_reuse_wrong_version_and_illegal_transition_fail_closed():
    with EphemeralMemoryKeyRegistry() as registry:
        first = EphemeralTestMemoryEncryption(local_test_enabled=True, key_version="v1")
        registry.register(first)
        envelope = registry.encrypt(_record())
        duplicate = EphemeralTestMemoryEncryption(local_test_enabled=True, key_version="v1")
        try:
            with pytest.raises(ValueError):
                registry.register(duplicate)
        finally:
            duplicate.close()
        with pytest.raises(PermissionError):
            registry.decrypt(replace(envelope, payload=replace(envelope.payload, key_version="unknown")))
        with pytest.raises(PermissionError):
            registry.transition("v1", MemoryKeyState.RETIRED)
        registry.transition("v1", MemoryKeyState.REVOKED)
        with pytest.raises(PermissionError):
            registry.decrypt(envelope)
        with pytest.raises(PermissionError):
            registry.transition("v1", MemoryKeyState.ACTIVE)
