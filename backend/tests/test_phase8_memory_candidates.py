"""R105A explicit, proposal-only memory candidate extraction."""

import pytest

from backend.medar.durable_memory_record import DurableMemoryDomain, DurableSensitivity
from backend.medar.memory_candidates import (
    CandidateImportance, CandidateSource, CandidateSourceType,
    MemoryCandidateExtractor,
)


def _source(text, *, domain=DurableMemoryDomain.TECHNICAL, source_type=CandidateSourceType.USER_STATEMENT):
    return CandidateSource("tenant-a", "owner-a", "synthetic-source", source_type, domain, text)


def test_explicit_preference_yields_scoped_candidate_without_persistence():
    result = MemoryCandidateExtractor().extract(_source("I prefer concise explanations", domain=DurableMemoryDomain.PREFERENCES))
    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.content == "I prefer concise explanations"
    assert candidate.domain is DurableMemoryDomain.PREFERENCES
    assert candidate.sensitivity is DurableSensitivity.PERSONAL
    assert candidate.importance is CandidateImportance.MEDIUM
    assert candidate.confidence == 0.9
    assert candidate.reason_to_remember == "EXPLICIT_USER_PREFERENCE"
    assert candidate.persistence_authorized is False
    assert result.persistence_performed is False


def test_labeled_task_outcome_yields_candidate_without_treating_it_as_fact():
    result = MemoryCandidateExtractor().extract(_source(
        "Lesson learned: Check migration checksum on startup",
        source_type=CandidateSourceType.TASK_OUTCOME,
    ))
    candidate = result.candidates[0]
    assert candidate.content == "Check migration checksum on startup"
    assert candidate.confidence == 0.7
    assert candidate.reason_to_remember == "LABELED_TASK_LESSON"
    assert candidate.sensitivity is DurableSensitivity.INTERNAL


def test_ordinary_conversation_is_not_saved_or_proposed():
    result = MemoryCandidateExtractor().extract(_source("What is the next step?"))
    assert result.candidates == ()
    assert result.rejection_reasons == ("NO_EXPLICIT_MEMORY_SIGNAL",)
    assert result.persistence_performed is False


@pytest.mark.parametrize("text", [
    "Remember that password=synthetic-secret",
    "I prefer bearer synthetic-token",
    "Remember that my account is 123456789",
])
def test_secret_like_content_does_not_become_candidate(text):
    result = MemoryCandidateExtractor().extract(_source(text))
    assert result.candidates == ()
    assert result.rejection_reasons == ("SECRET_LIKE_CONTENT",)


def test_financial_and_rosita_candidates_default_to_conservative_sensitivity():
    financial = MemoryCandidateExtractor().extract(_source("Remember that NQ and MNQ are distinct", domain=DurableMemoryDomain.NQ)).candidates[0]
    rosita = MemoryCandidateExtractor().extract(_source("Remember that this is a synthetic family note", domain=DurableMemoryDomain.ROSITA)).candidates[0]
    assert financial.sensitivity is DurableSensitivity.SENSITIVE
    assert rosita.sensitivity is DurableSensitivity.HIGHLY_SENSITIVE


def test_unlabeled_task_outcome_and_oversize_text_are_not_extracted():
    engine = MemoryCandidateExtractor()
    assert engine.extract(_source("The build failed", source_type=CandidateSourceType.TASK_OUTCOME)).candidates == ()
    assert engine.extract(_source("Remember that " + "x" * 1100)).rejection_reasons == ("SOURCE_TOO_LONG",)
