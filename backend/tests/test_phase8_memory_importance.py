"""R105B importance scoring from explicit evidence only."""

from dataclasses import replace

import pytest

from backend.medar.durable_memory_record import DurableMemoryDomain
from backend.medar.memory_candidates import CandidateImportance, CandidateSource, CandidateSourceType, MemoryCandidateExtractor
from backend.medar.memory_importance import ImportanceEvidence, apply_importance, score_memory_importance


def _candidate():
    source = CandidateSource(
        "tenant-a", "owner-a", "source-a", CandidateSourceType.USER_STATEMENT,
        DurableMemoryDomain.PREFERENCES, "I prefer concise explanations",
    )
    return MemoryCandidateExtractor().extract(source).candidates[0]


def test_explicit_preference_is_medium_without_more_evidence():
    assessment = score_memory_importance(_candidate(), ImportanceEvidence())
    assert assessment.importance is CandidateImportance.MEDIUM
    assert assessment.reason_codes == ("EXPLICIT_USER_PREFERENCE",)
    assert assessment.persistence_authorized is False


def test_repeated_evidence_and_long_term_goal_can_raise_importance():
    candidate = _candidate()
    repeated = score_memory_importance(candidate, ImportanceEvidence(repeated_source_ids=("source-a", "source-b")))
    goal = score_memory_importance(candidate, ImportanceEvidence(long_term_goal=True))
    assert repeated.importance is CandidateImportance.HIGH
    assert goal.importance is CandidateImportance.HIGH
    assert apply_importance(candidate, goal).importance is CandidateImportance.HIGH
    assert candidate.importance is CandidateImportance.MEDIUM


def test_verified_critical_rule_is_critical_but_not_authority():
    assessment = score_memory_importance(_candidate(), ImportanceEvidence(verified_critical_safety_rule=True))
    assert assessment.importance is CandidateImportance.CRITICAL
    assert assessment.persistence_authorized is False


def test_low_importance_requires_no_supported_signal():
    candidate = replace(_candidate(), reason_to_remember="UNLABELED")
    assessment = score_memory_importance(candidate, ImportanceEvidence())
    assert assessment.importance is CandidateImportance.LOW


def test_duplicate_repeat_sources_and_untyped_flags_are_rejected():
    with pytest.raises(ValueError):
        ImportanceEvidence(repeated_source_ids=("same", "same"))
    with pytest.raises(TypeError):
        ImportanceEvidence(long_term_goal="yes")
