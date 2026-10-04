"""R122A audits scope, plaintext sensitivity, secrets, and runtime authority."""

from dataclasses import replace
from datetime import datetime, timezone

from backend.medar.durable_memory_record import DurableMemoryDomain, DurableMemoryRecord, DurableMemoryType, DurableSensitivity, MemoryLifecycle, ProvenanceClass, RetentionPolicy, content_digest
from backend.medar.memory_privacy_audit import audit_memory_privacy
from backend.medar.memory_provenance import MemoryOrigin, MemoryProvenance
from backend.medar.sqlite_memory_store import MemoryScope

NOW = datetime(2026, 10, 4, 23, tzinfo=timezone.utc)
SCOPE = MemoryScope("tenant-a", "owner-a")


def _record(memory_id="memory-1", content="Synthetic public evidence", sensitivity=DurableSensitivity.PUBLIC, tenant="tenant-a", owner="owner-a"):
    return DurableMemoryRecord(
        memory_id, owner, tenant, DurableMemoryDomain.TECHNICAL, DurableMemoryType.FACT,
        content, content_digest(content), "synthetic_test", "synthetic-source",
        MemoryProvenance("synthetic-source", MemoryOrigin.OBSERVED, NOW, tenant, owner, "context", 1.0),
        ProvenanceClass.DIRECT_OBSERVATION, 1.0, 0.5, sensitivity,
        NOW, NOW, None, RetentionPolicy.LONG_TERM, MemoryLifecycle.ACTIVE, 1,
    )


def test_clean_scoped_public_and_internal_records_pass_content_free_audit():
    result = audit_memory_privacy((_record(), _record("memory-2", sensitivity=DurableSensitivity.INTERNAL)), SCOPE)
    assert result.passed and result.findings == ()
    assert result.records_examined == 2 and not result.runtime_examined


def test_cross_scope_sensitive_secret_and_duplicate_records_are_reported_without_content():
    secret = "api_key: synthetic-value"
    records = (
        _record("foreign", tenant="tenant-b", owner="owner-b"),
        _record("sensitive", sensitivity=DurableSensitivity.SENSITIVE),
        _record("secret", content=secret),
        _record("duplicate"), _record("duplicate"),
    )
    result = audit_memory_privacy(records, SCOPE)
    assert not result.passed
    assert result.findings == (
        "CROSS_SCOPE_MEMORY", "DUPLICATE_MEMORY_VERSION",
        "SECRET_LIKE_MEMORY_CONTENT", "SENSITIVE_PLAINTEXT_MEMORY",
    )
    assert secret not in repr(result)
