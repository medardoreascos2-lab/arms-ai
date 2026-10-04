"""R118B expired memory is excluded from retrieval while history remains."""

from datetime import datetime, timedelta, timezone

from backend.medar.durable_memory_record import (
    DurableMemoryDomain, DurableMemoryRecord, DurableMemoryType,
    DurableSensitivity, MemoryLifecycle, ProvenanceClass, RetentionPolicy,
    content_digest,
)
from backend.medar.memory_expiration import (
    MemoryExpirationStatus, assess_memory_expiration, filter_normal_retrieval,
)
from backend.medar.memory_provenance import MemoryOrigin, MemoryProvenance
from backend.medar.sqlite_memory_store import MemoryScope, SQLiteMemoryStore


NOW = datetime(2026, 10, 5, 2, tzinfo=timezone.utc)
SCOPE = MemoryScope("tenant-a", "owner-a")


def _record(memory_id, expires_at):
    source = f"synthetic-test:{memory_id}"
    provenance = MemoryProvenance(source, MemoryOrigin.OBSERVED, NOW, "tenant-a", "owner-a", "session-a", 1.0)
    return DurableMemoryRecord(
        memory_id, "owner-a", "tenant-a", DurableMemoryDomain.TECHNICAL,
        DurableMemoryType.FACT, f"fact {memory_id}", content_digest(f"fact {memory_id}"),
        "synthetic_test", source, provenance, ProvenanceClass.DIRECT_OBSERVATION,
        1.0, 0.8, DurableSensitivity.INTERNAL, NOW, NOW, expires_at,
        RetentionPolicy.UNTIL_DATE if expires_at else RetentionPolicy.LONG_TERM,
        MemoryLifecycle.ACTIVE, 1,
    )


def test_expired_memory_is_excluded_from_normal_retrieval_without_mutation():
    expired = _record("expired", NOW + timedelta(days=1))
    current = _record("current", NOW + timedelta(days=3))
    as_of = NOW + timedelta(days=2)
    assessment = assess_memory_expiration(expired, as_of=as_of)
    assert assessment.status is MemoryExpirationStatus.EXPIRED
    assert not assessment.normal_retrieval_allowed
    assert assessment.history_retained
    assert not assessment.deletion_performed
    assert not assessment.lifecycle_mutation_performed
    assert filter_normal_retrieval((expired, current), as_of=as_of) == (current,)
    assert expired.status is MemoryLifecycle.ACTIVE


def test_sqlite_normal_search_excludes_expired_but_get_and_history_remain_auditable(tmp_path):
    path = tmp_path / "memory.db"
    expired = _record("expired", NOW + timedelta(days=1))
    with SQLiteMemoryStore(path, read_only=False, clock=lambda: NOW) as store:
        store.write(SCOPE, expired)
    after_expiry = NOW + timedelta(days=2)
    with SQLiteMemoryStore(path, clock=lambda: after_expiry) as store:
        assert store.search(SCOPE, "fact", (DurableMemoryDomain.TECHNICAL,)) == ()
        assert store.list_active(
            SCOPE, DurableMemoryDomain.TECHNICAL, DurableSensitivity.INTERNAL,
        ) == ()
        assert store.get(SCOPE, "expired") == expired
        assert store.history(SCOPE, "expired") == (expired,)


def test_non_expiring_active_memory_remains_retrievable():
    record = _record("long", None)
    assessment = assess_memory_expiration(record, as_of=NOW + timedelta(days=5000))
    assert assessment.status is MemoryExpirationStatus.NO_EXPIRY
    assert assessment.normal_retrieval_allowed
