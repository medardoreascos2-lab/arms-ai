"""R105C conservative memory save-policy tests."""

from dataclasses import replace

import pytest

from backend.medar.durable_memory_record import DurableMemoryDomain, DurableSensitivity
from backend.medar.memory_candidates import CandidateImportance, CandidateSource, CandidateSourceType, MemoryCandidateExtractor
from backend.medar.memory_importance import ImportanceAssessment
from backend.medar.memory_save_policy import MemorySaveDisposition, evaluate_memory_save


def _candidate(domain=DurableMemoryDomain.TECHNICAL, text="Lesson learned: verify schema", source_type=CandidateSourceType.TASK_OUTCOME):
    source = CandidateSource("tenant-a", "owner-a", "synthetic-source", source_type, domain, text)
    return MemoryCandidateExtractor().extract(source).candidates[0]


def _assessment(grade=CandidateImportance.MEDIUM):
    return ImportanceAssessment(grade, ("SYNTHETIC_TEST",))


def test_personal_financial_and_rosita_default_to_no_durable_save():
    for domain in (DurableMemoryDomain.PERSONAL, DurableMemoryDomain.NQ, DurableMemoryDomain.ROSITA):
        candidate = _candidate(domain)
        decision = evaluate_memory_save(candidate, _assessment(CandidateImportance.CRITICAL))
        assert decision.disposition is MemorySaveDisposition.DO_NOT_SAVE
        assert decision.reason_codes == ("ENCRYPTION_UNAVAILABLE",)
        assert decision.persistence_authorized is False


def test_sensitive_memory_still_requires_review_if_encryption_becomes_available():
    decision = evaluate_memory_save(_candidate(DurableMemoryDomain.NQ), _assessment(), encryption_ready=True)
    assert decision.disposition is MemorySaveDisposition.REVIEW_REQUIRED
    assert decision.persistence_authorized is False


def test_working_memory_is_session_only():
    decision = evaluate_memory_save(_candidate(DurableMemoryDomain.WORKING), _assessment())
    assert decision.disposition is MemorySaveDisposition.SESSION_ONLY


def test_secret_like_text_is_never_eligible_even_if_candidate_is_constructed_directly():
    candidate = replace(_candidate(), content="password=synthetic-secret")
    decision = evaluate_memory_save(candidate, _assessment(CandidateImportance.CRITICAL), encryption_ready=True)
    assert decision.disposition is MemorySaveDisposition.DO_NOT_SAVE
    assert decision.reason_codes == ("SECRET_LIKE_CONTENT",)


def test_default_non_sensitive_candidate_requires_review():
    decision = evaluate_memory_save(_candidate(), _assessment())
    assert decision.disposition is MemorySaveDisposition.REVIEW_REQUIRED
    assert decision.persistence_authorized is False


def test_only_high_confidence_high_importance_non_sensitive_outcome_is_auto_eligible():
    candidate = replace(_candidate(), confidence=0.9)
    decision = evaluate_memory_save(candidate, _assessment(CandidateImportance.HIGH))
    assert decision.disposition is MemorySaveDisposition.AUTO_SAVE_ALLOWED
    assert decision.persistence_authorized is False
    assert evaluate_memory_save(_candidate(), _assessment(CandidateImportance.HIGH)).disposition is MemorySaveDisposition.REVIEW_REQUIRED


def test_untyped_encryption_status_is_rejected():
    with pytest.raises(TypeError):
        evaluate_memory_save(_candidate(), _assessment(), encryption_ready="yes")
