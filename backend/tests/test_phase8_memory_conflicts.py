"""R105D memory conflict detection without silent overwrite."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from backend.medar.durable_memory_record import DurableMemoryDomain, MemoryLifecycle
from backend.medar.memory_candidates import CandidateSource, CandidateSourceType, MemoryCandidateExtractor
from backend.medar.memory_conflicts import (
    MemoryConflictKind, MemoryConflictReference, compare_memory_candidate,
)


NOW = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)


def _candidate(content="deployment setting: enabled"):
    source = CandidateSource("tenant-a", "owner-a", "synthetic-source", CandidateSourceType.USER_STATEMENT, DurableMemoryDomain.TECHNICAL, "Remember that " + content)
    return MemoryCandidateExtractor().extract(source).candidates[0]


def _reference(content="deployment setting: enabled"):
    return MemoryConflictReference("existing-1", "tenant-a", "owner-a", DurableMemoryDomain.TECHNICAL, content, NOW, MemoryLifecycle.ACTIVE)


class FakeSimilarity:
    def __init__(self, score):
        self.value = score
        self.calls = 0

    def score(self, left, right):
        self.calls += 1
        return self.value


def test_exact_duplicate_is_deterministic_without_semantic_provider():
    provider = FakeSimilarity(0.1)
    result = compare_memory_candidate(_candidate(), _reference("Deployment  setting: ENABLED"), similarity=provider)
    assert result.kind is MemoryConflictKind.EXACT_DUPLICATE
    assert result.requires_review is False
    assert result.persistence_performed is False
    assert provider.calls == 0


def test_structured_conflict_requires_review_and_never_supersedes_itself():
    result = compare_memory_candidate(_candidate("deployment setting: disabled"), _reference())
    assert result.kind is MemoryConflictKind.CONTRADICTION
    assert result.requires_review is True
    assert result.persistence_performed is False


def test_newer_verified_fact_is_only_possible_supersession():
    result = compare_memory_candidate(
        _candidate("deployment setting: disabled"), _reference(),
        verified_new_fact=True, candidate_observed_at=NOW + timedelta(days=1),
    )
    assert result.kind is MemoryConflictKind.POSSIBLE_SUPERSESSION
    assert result.requires_review is True
    assert result.persistence_performed is False
    older = compare_memory_candidate(
        _candidate("deployment setting: disabled"), _reference(),
        verified_new_fact=True, candidate_observed_at=NOW - timedelta(days=1),
    )
    assert older.kind is MemoryConflictKind.CONTRADICTION


def test_semantic_near_duplicate_requires_injected_signal_and_review():
    provider = FakeSimilarity(0.95)
    result = compare_memory_candidate(_candidate("verify startup migrations"), _reference("check migration on launch"), similarity=provider)
    assert result.kind is MemoryConflictKind.NEAR_DUPLICATE
    assert result.requires_review is True
    assert provider.calls == 1
    assert compare_memory_candidate(_candidate("verify startup migrations"), _reference("check migration on launch")).kind is MemoryConflictKind.UNKNOWN


def test_cross_scope_denied_before_semantic_model_call():
    provider = FakeSimilarity(1.0)
    with pytest.raises(PermissionError):
        compare_memory_candidate(_candidate(), replace(_reference(), owner_id="other"), similarity=provider)
    assert provider.calls == 0


def test_invalid_score_and_unusable_reference_fail_closed():
    with pytest.raises(ValueError):
        compare_memory_candidate(_candidate("other fact"), _reference(), similarity=FakeSimilarity(float("nan")))
    result = compare_memory_candidate(_candidate(), replace(_reference(), status=MemoryLifecycle.RETRACTED))
    assert result.kind is MemoryConflictKind.UNKNOWN
    assert result.requires_review is True
