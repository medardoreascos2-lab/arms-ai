"""R104C/D disabled encryption and content-free memory event tests."""

from dataclasses import asdict
from datetime import datetime, timezone

import pytest

from backend.medar.durable_memory_record import (
    DurableMemoryDomain, DurableMemoryRecord, DurableMemoryType,
    DurableSensitivity, MemoryLifecycle, ProvenanceClass, RetentionPolicy,
    content_digest,
)
from backend.medar.memory_encryption import DisabledMemoryEncryption
from backend.medar.memory_provenance import MemoryOrigin, MemoryProvenance
from backend.medar.memory_redaction import redacted_memory_event


def _secret_record():
    now = datetime(2026, 10, 3, tzinfo=timezone.utc)
    content = "password=synthetic-secret Authorization: Bearer synthetic-token account=123456789"
    return DurableMemoryRecord(
        "memory-secret", "owner-secret", "tenant-secret",
        DurableMemoryDomain.TECHNICAL, DurableMemoryType.FACT,
        content, content_digest(content), "synthetic_test", "source-secret",
        MemoryProvenance("source-secret", MemoryOrigin.OBSERVED, now, "tenant-secret", "owner-secret", "context-secret", 1.0),
        ProvenanceClass.DIRECT_OBSERVATION, 1.0, 1.0, DurableSensitivity.SENSITIVE,
        now, now, None, RetentionPolicy.LONG_TERM, MemoryLifecycle.ACTIVE, 1,
    )


def test_disabled_encryption_never_returns_plaintext_or_ciphertext():
    provider = DisabledMemoryEncryption()
    assert provider.is_available() is False
    with pytest.raises(PermissionError, match="unavailable"):
        provider.encrypt(b"private", tenant_id="tenant", owner_id="owner")
    with pytest.raises(PermissionError, match="unavailable"):
        provider.decrypt(b"private", tenant_id="tenant", owner_id="owner")


def test_memory_event_omits_sensitive_content_and_raw_identifiers():
    record = _secret_record()
    event = redacted_memory_event(record, "DENY")
    text = str(asdict(event))
    for secret in (record.content, "synthetic-secret", "synthetic-token", "123456789", record.owner_id, record.tenant_id, record.memory_id):
        assert secret not in text
    assert event.raw_content_stored is False
    assert event.event_type == "DENY"


def test_memory_event_rejects_arbitrary_strings_and_raw_content_flag():
    with pytest.raises(ValueError):
        redacted_memory_event(_secret_record(), "password=secret")
