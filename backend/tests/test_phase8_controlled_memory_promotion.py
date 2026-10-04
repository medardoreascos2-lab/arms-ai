"""R108C proposal-only promotion policy and provenance tests."""

import pytest
from dataclasses import replace

from backend.medar.controlled_memory_promotion import PromotionDisposition, prepare_memory_promotion
from backend.medar.durable_memory_record import DurableMemoryDomain
from backend.medar.memory_candidates import CandidateSource, CandidateSourceType, MemoryCandidateExtractor
from backend.medar.memory_importance import ImportanceEvidence
from backend.medar.session_working_memory import SessionWorkingMemory, WorkingMemorySnapshot


def _candidate(text, source_type, domain=DurableMemoryDomain.TECHNICAL):
    source = CandidateSource("tenant-a", "owner-a", "conversation-1/turn-4", source_type, domain, text)
    result = MemoryCandidateExtractor().extract(source)
    assert len(result.candidates) == 1
    return result.candidates[0]


def _snapshot(candidate):
    session = SessionWorkingMemory("session-1", "tenant-a", "owner-a")
    session.add_candidate(candidate)
    return session.snapshot()


def test_high_importance_non_sensitive_outcome_is_only_ready_for_authorized_write():
    candidate = _candidate("Outcome: schema recovery passed", CandidateSourceType.TASK_OUTCOME)
    evidence = ImportanceEvidence(technical_solution=True, observed_outcome=True)
    unverified = prepare_memory_promotion(_snapshot(candidate), candidate.candidate_id, evidence)
    assert unverified.disposition is PromotionDisposition.REVIEW_REQUIRED
    verified = replace(candidate, confidence=0.9)
    proposal = prepare_memory_promotion(_snapshot(verified), verified.candidate_id, evidence)
    assert proposal.disposition is PromotionDisposition.READY_FOR_AUTHORIZED_WRITE
    assert proposal.session_id == "session-1"
    assert proposal.source_reference == "conversation-1/turn-4"
    assert proposal.candidate.candidate_id == candidate.candidate_id
    assert not proposal.persistence_authorized and not proposal.persistence_performed


def test_personal_candidate_is_blocked_without_encryption_and_default_requires_review():
    personal = _candidate("I prefer concise replies", CandidateSourceType.USER_STATEMENT, DurableMemoryDomain.PREFERENCES)
    blocked = prepare_memory_promotion(_snapshot(personal), personal.candidate_id, ImportanceEvidence())
    assert blocked.disposition is PromotionDisposition.BLOCKED
    assert "ENCRYPTION_UNAVAILABLE" in blocked.reason_codes
    ordinary = _candidate("Remember that the schema is stable", CandidateSourceType.USER_STATEMENT)
    review = prepare_memory_promotion(_snapshot(ordinary), ordinary.candidate_id, ImportanceEvidence())
    assert review.disposition is PromotionDisposition.REVIEW_REQUIRED


def test_candidate_must_be_in_session_and_match_owner_scope():
    candidate = _candidate("Outcome: schema recovery passed", CandidateSourceType.TASK_OUTCOME)
    snapshot = _snapshot(candidate)
    with pytest.raises(ValueError):
        prepare_memory_promotion(snapshot, "missing", ImportanceEvidence())
    forged = WorkingMemorySnapshot("session-2", "tenant-a", "owner-b", (), (candidate,), (), 0)
    with pytest.raises(PermissionError):
        prepare_memory_promotion(forged, candidate.candidate_id, ImportanceEvidence())
