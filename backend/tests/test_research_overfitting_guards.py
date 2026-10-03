from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from backend.research.overfitting_guards import OverfittingGuardPolicy, ResearchOverfittingGuard, ResearchSearchDeclaration

NOW = datetime(2026, 10, 3, tzinfo=timezone.utc)
POLICY = OverfittingGuardPolicy(100, 50, 20, 100, Decimal("5"))


def valid() -> ResearchSearchDeclaration:
    return ResearchSearchDeclaration(100, 50, 2, 3, 40, Decimal("3"), "a"*64, "b"*64, "c"*64, False, NOW, NOW+timedelta(days=1))


def test_valid_predeclared_search_is_admitted_without_execution_authority() -> None:
    result = ResearchOverfittingGuard().evaluate(valid(), POLICY)
    assert result.accepted and result.optimization_authorized
    assert result.execution_authorized is False
    assert result.multiple_testing_count == 5
    assert result.holdout_preserved and not result.data_leakage_detected


@pytest.mark.parametrize("changes,reason", [
    ({"training_samples": 99}, "INSUFFICIENT_TRAINING_SAMPLES"),
    ({"validation_samples": 49}, "INSUFFICIENT_VALIDATION_SAMPLES"),
    ({"hypotheses_requested": 19}, "MULTIPLE_TESTING_BUDGET_EXCEEDED"),
    ({"parameter_combinations_requested": 101}, "PARAMETER_SEARCH_BUDGET_EXCEEDED"),
    ({"holdout_opened": True}, "HOLDOUT_ALREADY_OPENED"),
    ({"feature_window_end": NOW + timedelta(days=1)}, "TEMPORAL_DATA_LEAKAGE"),
    ({"complexity_score": Decimal("6")}, "CANDIDATE_COMPLEXITY_LIMIT_EXCEEDED"),
])
def test_each_guard_fails_closed(changes: dict[str, object], reason: str) -> None:
    result = ResearchOverfittingGuard().evaluate(replace(valid(), **changes), POLICY)
    assert not result.accepted and not result.optimization_authorized
    assert reason in result.blocking_reasons


def test_dataset_reuse_across_partitions_is_rejected() -> None:
    with pytest.raises(ValueError, match="must be distinct"):
        replace(valid(), holdout_dataset_hash="a"*64)


def test_declaration_hash_is_deterministic() -> None:
    first = ResearchOverfittingGuard().evaluate(valid(), POLICY)
    second = ResearchOverfittingGuard().evaluate(valid(), POLICY)
    assert first.declaration_hash == second.declaration_hash


def test_all_failures_are_reported_together() -> None:
    declaration = replace(valid(), training_samples=1, validation_samples=1, holdout_opened=True, complexity_score=Decimal("9"))
    result = ResearchOverfittingGuard().evaluate(declaration, POLICY)
    assert len(result.blocking_reasons) == 4
