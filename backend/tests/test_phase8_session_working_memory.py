"""R108A session-only working memory bounds and compartment tests."""

from datetime import datetime, timezone

import pytest

from backend.medar.durable_memory_record import DurableMemoryDomain, DurableSensitivity
from backend.medar.memory_candidates import CandidateSource, CandidateSourceType, MemoryCandidateExtractor
from backend.medar.memory_evidence_references import CitedMemoryItem, MemoryEvidenceReference
from backend.medar.memory_provenance import MemoryOrigin, MemoryProvenance
from backend.medar.session_working_memory import SessionWorkingMemory, TemporarySessionItem


NOW = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)


def _candidate():
    source = CandidateSource(
        "tenant-a", "owner-a", "source-candidate", CandidateSourceType.USER_STATEMENT,
        DurableMemoryDomain.TECHNICAL, "Remember that the schema checksum is verified",
    )
    return MemoryCandidateExtractor().extract(source).candidates[0]


def _retrieved(owner_id="owner-a"):
    provenance = MemoryProvenance("source-retrieved", MemoryOrigin.OBSERVED, NOW, "tenant-a", owner_id, "context", 0.9)
    reference = MemoryEvidenceReference(
        "memory-1", 1, "digest", "tenant-a", owner_id, DurableMemoryDomain.TECHNICAL,
        DurableSensitivity.PUBLIC, "synthetic_test", "source-retrieved", provenance,
    )
    return CitedMemoryItem("schema checksum verified", reference, 0.8, 100)


def test_session_compartments_are_bounded_and_clearable():
    working = SessionWorkingMemory("session-1", "tenant-a", "owner-a", max_items=3, max_bytes=1000)
    working.add_temporary(TemporarySessionItem("current task", "turn-1"))
    working.add_candidate(_candidate())
    working.add_retrieved(_retrieved())
    snapshot = working.snapshot()
    assert len(snapshot.temporary) == len(snapshot.candidate_durable) == len(snapshot.durable_retrieved) == 1
    assert snapshot.candidate_durable[0].persistence_authorized is False
    assert snapshot.used_bytes > 0
    assert snapshot.persistence_performed is False
    with pytest.raises(ValueError, match="capacity"):
        working.add_temporary(TemporarySessionItem("extra", "turn-2"))
    assert working.snapshot() == snapshot
    working.clear()
    assert working.snapshot().used_bytes == 0
    assert working.snapshot().temporary == ()
    assert working.snapshot().candidate_durable == ()
    assert working.snapshot().durable_retrieved == ()


def test_session_rejects_cross_owner_retrieval_and_secret_like_text():
    working = SessionWorkingMemory("session-1", "tenant-a", "owner-a", max_bytes=50)
    with pytest.raises(PermissionError):
        working.add_retrieved(_retrieved("owner-b"))
    with pytest.raises(PermissionError):
        TemporarySessionItem("api_key: real-value", "turn-1")
    with pytest.raises(ValueError, match="capacity"):
        working.add_temporary(TemporarySessionItem("x" * 51, "turn-1"))
    assert working.snapshot().used_bytes == 0
