"""R117A consolidation retains source links and never mutates memory."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from backend.medar.durable_memory_record import (
    DurableMemoryDomain, DurableMemoryRecord, DurableMemoryType,
    DurableSensitivity, MemoryLifecycle, ProvenanceClass, RetentionPolicy,
    content_digest,
)
from backend.medar.memory_consolidation import propose_memory_consolidation
from backend.medar.memory_provenance import MemoryOrigin, MemoryProvenance


NOW = datetime(2026, 10, 4, 21, tzinfo=timezone.utc)


def _record(memory_id, content, *, owner="owner-a", domain=DurableMemoryDomain.TECHNICAL):
    source = f"synthetic-test:{memory_id}"
    provenance = MemoryProvenance(source, MemoryOrigin.OBSERVED, NOW - timedelta(days=2), "tenant-a", owner, "session-a", 1.0)
    return DurableMemoryRecord(
        memory_id, owner, "tenant-a", domain, DurableMemoryType.LESSON,
        content, content_digest(content), "synthetic_test", source, provenance,
        ProvenanceClass.DIRECT_OBSERVATION, 1.0, 0.8,
        DurableSensitivity.INTERNAL, NOW - timedelta(days=2),
        NOW - timedelta(days=2), None, RetentionPolicy.LONG_TERM,
        MemoryLifecycle.ACTIVE, 1,
    )


def test_consolidation_groups_related_records_and_retains_exact_source_links():
    records = (_record("m2", "second lesson"), _record("m1", "first lesson"))
    proposal = propose_memory_consolidation(
        records, proposal_id="proposal-1", summary="  combined   bounded lesson ",
        created_at=NOW, minimum_age=timedelta(days=1),
    )
    assert proposal.summary == "combined bounded lesson"
    assert tuple(source.memory_id for source in proposal.sources) == ("m1", "m2")
    assert tuple(source.source_reference for source in proposal.sources) == (
        "synthetic-test:m1", "synthetic-test:m2",
    )
    assert all(source.content_hash for source in proposal.sources)
    assert not proposal.persistence_authority
    assert not proposal.deletion_authority
    assert not proposal.supersession_authority


def test_cross_scope_domain_inactive_duplicate_and_too_new_records_are_rejected():
    first = _record("m1", "first")
    second = _record("m2", "second")
    variants = (
        (first, _record("m2", "second", owner="other")),
        (first, _record("m2", "second", domain=DurableMemoryDomain.CODING)),
        (first, replace(second, status=MemoryLifecycle.RETRACTED)),
    )
    for records in variants:
        with pytest.raises(PermissionError):
            propose_memory_consolidation(records, proposal_id="p", summary="summary", created_at=NOW)
    with pytest.raises(ValueError):
        propose_memory_consolidation((first, first), proposal_id="p", summary="summary", created_at=NOW)
    with pytest.raises(PermissionError):
        propose_memory_consolidation(
            (first, second), proposal_id="p", summary="summary", created_at=NOW,
            minimum_age=timedelta(days=3),
        )


def test_secret_shaped_summary_is_rejected_without_changing_sources():
    records = (_record("m1", "first"), _record("m2", "second"))
    with pytest.raises(PermissionError):
        propose_memory_consolidation(
            records, proposal_id="p", summary="api_key: synthetic",
            created_at=NOW,
        )
    assert all(record.status is MemoryLifecycle.ACTIVE for record in records)
