"""R117C verified facts supersede atomically while retaining history."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from backend.medar.durable_memory_record import (
    DurableMemoryDomain, DurableMemoryRecord, DurableMemoryType,
    DurableSensitivity, MemoryLifecycle, ProvenanceClass, RetentionPolicy,
    content_digest,
)
from backend.medar.memory_provenance import MemoryOrigin, MemoryProvenance
from backend.medar.memory_supersession import VerifiedFactEvidence, supersede_with_verified_fact
from backend.medar.sqlite_memory_store import MemoryScope, SQLiteMemoryStore


NOW = datetime(2026, 10, 4, 23, tzinfo=timezone.utc)
SCOPE = MemoryScope("tenant-a", "owner-a")


def _fact(memory_id, content, observed_at, *, domain=DurableMemoryDomain.TECHNICAL):
    source = f"synthetic-test:{memory_id}"
    provenance = MemoryProvenance(source, MemoryOrigin.OBSERVED, observed_at, "tenant-a", "owner-a", "session-a", 1.0)
    return DurableMemoryRecord(
        memory_id, "owner-a", "tenant-a", domain, DurableMemoryType.FACT,
        content, content_digest(content), "synthetic_test", source, provenance,
        ProvenanceClass.DIRECT_OBSERVATION, 1.0, 0.8,
        DurableSensitivity.INTERNAL, observed_at, observed_at, None,
        RetentionPolicy.LONG_TERM, MemoryLifecycle.ACTIVE, 1,
    )


def test_verified_replacement_is_atomic_and_old_history_is_preserved(tmp_path):
    old = _fact("old", "old fact", NOW - timedelta(days=1))
    new = _fact("new", "verified new fact", NOW)
    evidence = VerifiedFactEvidence(("synthetic-test:new",), 0.9, True)
    path = tmp_path / "memory.db"
    with SQLiteMemoryStore(path, read_only=False, clock=lambda: NOW) as store:
        store.write(SCOPE, old)
        receipt = supersede_with_verified_fact(store, SCOPE, "old", new, evidence)
        old_latest = store.get(SCOPE, "old")
        new_latest = store.get(SCOPE, "new")
        history = store.history(SCOPE, "old")
    assert receipt.history_preserved and not receipt.deletion_performed
    assert old_latest is not None and old_latest.status is MemoryLifecycle.SUPERSEDED
    assert new_latest is not None and new_latest.status is MemoryLifecycle.ACTIVE
    assert tuple(item.status for item in history) == (
        MemoryLifecycle.ACTIVE, MemoryLifecycle.SUPERSEDED,
    )
    assert tuple(item.content for item in history) == ("old fact", "old fact")


def test_rejected_evidence_or_classification_leaves_store_unchanged(tmp_path):
    old = _fact("old", "old fact", NOW - timedelta(days=1))
    new = _fact("new", "new fact", NOW)
    path = tmp_path / "memory.db"
    with SQLiteMemoryStore(path, read_only=False, clock=lambda: NOW) as store:
        store.write(SCOPE, old)
        with pytest.raises(PermissionError):
            supersede_with_verified_fact(
                store, SCOPE, "old", new,
                VerifiedFactEvidence(("synthetic-test:new",), 0.5, True),
            )
        with pytest.raises(PermissionError):
            supersede_with_verified_fact(
                store, SCOPE, "old",
                replace(new, domain=DurableMemoryDomain.CODING),
                VerifiedFactEvidence(("synthetic-test:new",), 0.9, True),
            )
        assert store.get(SCOPE, "old").status is MemoryLifecycle.ACTIVE
        assert store.get(SCOPE, "new") is None
        assert len(store.history(SCOPE, "old")) == 1


def test_unverified_or_inferred_replacement_is_denied_before_store_call():
    new = _fact("new", "new fact", NOW)

    class SpyStore:
        def __init__(self):
            self.calls = []

        def supersede_with(self, *args):
            self.calls.append(args)
            raise AssertionError("store must not be called")

    spy = SpyStore()
    with pytest.raises(PermissionError):
        supersede_with_verified_fact(
            spy, MemoryScope("tenant-a", "other"), "old", new,
            VerifiedFactEvidence(("synthetic-test:new",), 0.9, True),
        )
    with pytest.raises(PermissionError):
        supersede_with_verified_fact(
            spy, SCOPE, "old", new,
            VerifiedFactEvidence(("synthetic-test:new",), 0.9, False),
        )
    inferred = replace(new, provenance_class=ProvenanceClass.DERIVED_ANALYSIS,
                       provenance=replace(new.provenance, origin=MemoryOrigin.INFERRED))
    with pytest.raises(PermissionError):
        supersede_with_verified_fact(
            spy, SCOPE, "old", inferred,
            VerifiedFactEvidence(("synthetic-test:new",), 0.9, True),
        )
    assert spy.calls == []
