"""R31C tests for immutable research experiment identity and lifecycle."""

from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from backend.research.backtest_runner import ResearchParameterSet
from backend.research.experiment import (
    ExperimentTransitionError,
    ExperimentWindow,
    StrategyExperiment,
    StrategyExperimentStatus,
)


UTC = timezone.utc
NOW = datetime(2026, 10, 4, 12, 0, tzinfo=UTC)


def windows():
    return (
        ExperimentWindow(NOW - timedelta(days=90), NOW - timedelta(days=60)),
        ExperimentWindow(NOW - timedelta(days=60), NOW - timedelta(days=30)),
        ExperimentWindow(NOW - timedelta(days=30), NOW),
    )


def experiment(**changes):
    train, validation, test = windows()
    values = dict(
        experiment_id="exp-nq-2026-001",
        parent_production_version="prod-v8",
        candidate_parameters=ResearchParameterSet.from_mapping(
            {"risk": Decimal("0.5"), "minimum_probability": Decimal("0.8")}
        ),
        dataset_ids=("nq-validation", "nq-train", "nq-test"),
        train_window=train,
        validation_window=validation,
        test_window=test,
        creation_reason="Evaluate a bounded parameter candidate",
        created_at=NOW,
    )
    values.update(changes)
    return StrategyExperiment.create(**values)


def test_create_stores_required_identity_and_begins_in_research():
    item = experiment()

    assert item.experiment_id == "exp-nq-2026-001"
    assert item.parent_production_version == "prod-v8"
    assert item.dataset_ids == ("nq-test", "nq-train", "nq-validation")
    assert item.status is StrategyExperimentStatus.RESEARCH
    assert item.revision == 0 and item.previous_hash is None
    assert len(item.hash) == 64
    assert item.document()["hash"] == item.hash
    assert item.document()["candidate_parameter_set_sha256"] == item.candidate_parameters.sha256
    assert item.execution_authorized is False
    assert item.paper_execution_authorized is False
    assert item.live_execution_authorized is False
    assert item.production_assignment_authorized is False


def test_equivalent_definition_has_deterministic_hash():
    first = experiment()
    second = experiment(dataset_ids=("nq-test", "nq-validation", "nq-train"))

    assert first == second
    assert first.hash == second.hash


@pytest.mark.parametrize(
    "change",
    (
        {"experiment_id": "exp-nq-2026-002"},
        {"parent_production_version": "prod-v9"},
        {"dataset_ids": ("another-dataset",)},
        {"creation_reason": "Different hypothesis"},
        {"candidate_parameters": ResearchParameterSet.from_mapping({"risk": 1})},
    ),
)
def test_each_identity_input_changes_hash(change):
    assert experiment(**change).hash != experiment().hash


def test_windows_require_timezone_order_and_strict_separation():
    with pytest.raises(ValueError, match="timezone-aware"):
        ExperimentWindow(datetime(2026, 1, 1), datetime(2026, 1, 2))
    with pytest.raises(ValueError, match="precede"):
        ExperimentWindow(NOW, NOW)

    train, validation, test = windows()
    overlapping = ExperimentWindow(
        validation.starts_at - timedelta(seconds=1), validation.ends_at
    )
    with pytest.raises(ValueError, match="train and validation"):
        experiment(train_window=overlapping)
    overlapping_test = ExperimentWindow(
        validation.ends_at - timedelta(seconds=1), test.ends_at
    )
    with pytest.raises(ValueError, match="validation and test"):
        experiment(test_window=overlapping_test)


def test_dataset_ids_are_nonempty_unique_and_valid():
    with pytest.raises(ValueError, match="nonempty tuple"):
        experiment(dataset_ids=())
    with pytest.raises(ValueError, match="unique"):
        experiment(dataset_ids=("same", "same"))
    with pytest.raises(ValueError, match="invalid"):
        experiment(dataset_ids=("invalid id",))


def test_valid_lifecycle_builds_a_tamper_evident_hash_chain():
    research = experiment()
    backtested = research.transition(
        StrategyExperimentStatus.BACKTESTED,
        reason="Deterministic backtest completed",
        transitioned_at=NOW + timedelta(minutes=1),
    )
    passed = backtested.transition(
        StrategyExperimentStatus.VALIDATION_PASSED,
        reason="All predeclared validation gates passed",
        transitioned_at=NOW + timedelta(minutes=2),
    )
    challenger = passed.transition(
        StrategyExperimentStatus.PAPER_CHALLENGER,
        reason="Approved for isolated paper observation",
        transitioned_at=NOW + timedelta(minutes=3),
    )
    candidate = challenger.transition(
        StrategyExperimentStatus.PROMOTION_CANDIDATE,
        reason="Paper evidence is eligible for human review",
        transitioned_at=NOW + timedelta(minutes=4),
    )

    chain = (research, backtested, passed, challenger, candidate)
    assert [item.revision for item in chain] == [0, 1, 2, 3, 4]
    assert all(current.previous_hash == previous.hash for previous, current in zip(chain, chain[1:]))
    assert len({item.hash for item in chain}) == len(chain)
    assert candidate.production_assignment_authorized is False


@pytest.mark.parametrize(
    "start,target",
    (
        (StrategyExperimentStatus.RESEARCH, StrategyExperimentStatus.VALIDATION_PASSED),
        (StrategyExperimentStatus.BACKTESTED, StrategyExperimentStatus.PAPER_CHALLENGER),
        (StrategyExperimentStatus.VALIDATION_FAILED, StrategyExperimentStatus.RESEARCH),
        (StrategyExperimentStatus.REJECTED, StrategyExperimentStatus.BACKTESTED),
    ),
)
def test_invalid_lifecycle_skips_are_rejected(start, target):
    item = experiment()
    if start is StrategyExperimentStatus.BACKTESTED:
        item = item.transition(
            start, reason="backtest", transitioned_at=NOW + timedelta(minutes=1)
        )
    elif start in (StrategyExperimentStatus.VALIDATION_FAILED, StrategyExperimentStatus.REJECTED):
        item = item.transition(
            StrategyExperimentStatus.BACKTESTED,
            reason="backtest",
            transitioned_at=NOW + timedelta(minutes=1),
        )
        item = item.transition(
            start,
            reason="terminal result",
            transitioned_at=NOW + timedelta(minutes=2),
        )

    with pytest.raises(ExperimentTransitionError, match="not allowed"):
        item.transition(target, reason="skip", transitioned_at=NOW + timedelta(hours=1))


def test_production_status_does_not_exist_and_cannot_be_assigned():
    assert "PRODUCTION" not in StrategyExperimentStatus.__members__
    with pytest.raises(ValueError):
        StrategyExperimentStatus("PRODUCTION")
    with pytest.raises(ExperimentTransitionError, match="only StrategyExperimentStatus"):
        experiment().transition(
            "PRODUCTION",
            reason="research may not promote",
            transitioned_at=NOW + timedelta(minutes=1),
        )


def test_transition_timestamp_cannot_move_backward():
    with pytest.raises(ExperimentTransitionError, match="cannot move backward"):
        experiment().transition(
            StrategyExperimentStatus.BACKTESTED,
            reason="backtest",
            transitioned_at=NOW - timedelta(seconds=1),
        )


def test_experiment_records_are_frozen():
    item = experiment()
    with pytest.raises(FrozenInstanceError):
        item.status = StrategyExperimentStatus.REJECTED
    with pytest.raises(FrozenInstanceError):
        item.hash = "0" * 64


def test_experiment_module_has_no_execution_or_production_assignment_dependency():
    import backend.research.experiment as module

    source = Path(module.__file__).read_text(encoding="utf-8").lower()
    forbidden = (
        "from backend.execution", "import backend.execution", "submit_order(",
        "enterlong(", "entershort(", "broker_adapter", 'production = "production"',
    )
    assert all(token not in source for token in forbidden)
    assert StrategyExperiment.production_assignment_authorized is False
