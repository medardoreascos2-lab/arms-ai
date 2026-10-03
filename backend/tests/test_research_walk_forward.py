"""R31D tests for deterministic, leak-resistant walk-forward research."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
from pathlib import Path

import pytest

from backend.research.backtest_runner import ResearchParameterSet
from backend.research.dataset_registry import (
    DatasetCertificationStatus,
    DatasetFileFormat,
    DatasetIntegrityError,
    DatasetWindow,
    HistoricalDatasetRegistration,
    HistoricalDatasetRegistry,
)
from backend.research.walk_forward import (
    WalkForwardDataError,
    WalkForwardDeterminismError,
    WalkForwardFailureStage,
    WalkForwardMetrics,
    WalkForwardPlan,
    WalkForwardResearchEngine,
    WalkForwardWindowStatus,
    generate_walk_forward_windows,
)


UTC = timezone.utc
START = datetime(2026, 9, 1, 14, 30, tzinfo=UTC)


def registry_with_bars(tmp_path: Path, count: int = 12):
    source = tmp_path / "walk-forward.csv"
    lines = ["timestamp,open,high,low,close,volume"]
    for index in range(count):
        timestamp = START + timedelta(minutes=index)
        price = Decimal(100) + Decimal(index)
        lines.append(
            f"{timestamp.isoformat().replace('+00:00', 'Z')},"
            f"{price},{price + 1},{price - 1},{price},10"
        )
    source.write_text("\n".join(lines) + "\n", encoding="utf-8")
    registry = HistoricalDatasetRegistry((tmp_path,))
    registry.register(
        HistoricalDatasetRegistration(
            dataset_id="nq-walk-forward",
            instrument="NQ",
            contract="NQ DEC26",
            timeframe="1m",
            session_template="CME ETH",
            starts_at=START,
            ends_at=START + timedelta(minutes=count),
            source="test-fixture:explicit-simulated-walk-forward-bars",
            window=DatasetWindow.ONE_MONTH,
            file_format=DatasetFileFormat.CSV,
            expected_bar_count=count,
            expected_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
            certification_status=DatasetCertificationStatus.AVAILABLE_UNCERTIFIED,
        ),
        path=source,
        registered_at=START,
    )
    return registry, source


def plan():
    return WalkForwardPlan(
        training_size=4,
        validation_size=2,
        step_size=2,
        minimum_sample_size=2,
    )


class SuccessfulWorkflow:
    def __init__(self, observations=None):
        self.observations = observations

    def select_candidate(self, training_bars, context):
        if self.observations is not None:
            self.observations.append((
                "train",
                context.window.index,
                tuple(bar.index for bar in training_bars),
                training_bars[-1].timestamp,
            ))
        return ResearchParameterSet.from_mapping({
            "window": context.window.index,
            "threshold": Decimal("0.8"),
        })

    def evaluate_candidate(self, candidate, validation_bars, context):
        if self.observations is not None:
            self.observations.append((
                "validation",
                context.window.index,
                tuple(bar.index for bar in validation_bars),
                validation_bars[0].timestamp,
                candidate.selected_after_index,
            ))
        index = context.window.index
        return WalkForwardMetrics(
            sample_count=len(validation_bars),
            trade_count=index + 1,
            net_pnl=Decimal(index + 1),
            max_drawdown=Decimal(index) / Decimal(2),
            passed=index % 2 == 0,
        )


def test_window_generation_is_rolling_contiguous_and_deterministic():
    windows = generate_walk_forward_windows(12, plan())

    assert [window.document() for window in windows] == [
        {"index": 0, "training_start": 0, "training_end": 4, "validation_start": 4, "validation_end": 6},
        {"index": 1, "training_start": 2, "training_end": 6, "validation_start": 6, "validation_end": 8},
        {"index": 2, "training_start": 4, "training_end": 8, "validation_start": 8, "validation_end": 10},
        {"index": 3, "training_start": 6, "training_end": 10, "validation_start": 10, "validation_end": 12},
    ]
    assert windows == generate_walk_forward_windows(12, plan())


def test_engine_exposes_only_chronological_training_and_validation_slices(tmp_path):
    registry, _ = registry_with_bars(tmp_path)
    observations = []

    result = WalkForwardResearchEngine(registry).run(
        dataset_id="nq-walk-forward",
        plan=plan(),
        workflow_factory=lambda context: SuccessfulWorkflow(observations),
    )

    first_replay = observations[:8]
    for index in range(0, len(first_replay), 2):
        training = first_replay[index]
        validation = first_replay[index + 1]
        assert training[0] == "train" and validation[0] == "validation"
        assert max(training[2]) < min(validation[2])
        assert training[3] < validation[3]
        assert validation[4] == max(training[2])
    assert result.deterministic_replay_verified is True
    assert result.execution_authorized is False
    assert result.production_mutation_authorized is False
    assert result.live_execution_authorized is False


def test_aggregate_reports_every_window_and_keeps_failed_validations_visible(tmp_path):
    registry, _ = registry_with_bars(tmp_path)

    result = WalkForwardResearchEngine(registry).run(
        dataset_id="nq-walk-forward",
        plan=plan(),
        workflow_factory=lambda context: SuccessfulWorkflow(),
    )

    assert len(result.windows) == 4
    assert all(item.status is WalkForwardWindowStatus.SUCCEEDED for item in result.windows)
    assert result.aggregate.total_windows == 4
    assert result.aggregate.successful_windows == 4
    assert result.aggregate.failed_windows == 0
    assert result.aggregate.passed_validations == 2
    assert result.aggregate.failed_validations == 2
    assert result.aggregate.total_validation_samples == 8
    assert result.aggregate.total_trades == 10
    assert result.aggregate.total_net_pnl == Decimal("10")
    assert result.aggregate.worst_window_max_drawdown == Decimal("1.5")
    assert result.aggregate.failed_window_indexes == ()
    assert result.aggregate.all_windows_succeeded is True


def test_training_failure_is_recorded_and_later_windows_continue(tmp_path):
    registry, _ = registry_with_bars(tmp_path)

    class TrainingFailure(SuccessfulWorkflow):
        def select_candidate(self, training_bars, context):
            if context.window.index == 1:
                raise RuntimeError("declared training failure")
            return super().select_candidate(training_bars, context)

    result = WalkForwardResearchEngine(registry).run(
        dataset_id="nq-walk-forward",
        plan=plan(),
        workflow_factory=lambda context: TrainingFailure(),
    )

    failed = result.windows[1]
    assert failed.status is WalkForwardWindowStatus.FAILED
    assert failed.failure_stage is WalkForwardFailureStage.TRAINING
    assert failed.failure_code == "RuntimeError"
    assert failed.failure_reason == "declared training failure"
    assert failed.candidate is None and failed.metrics is None
    assert result.windows[2].status is WalkForwardWindowStatus.SUCCEEDED
    assert result.aggregate.failed_windows == 1
    assert result.aggregate.failed_window_indexes == (1,)
    assert result.aggregate.all_windows_succeeded is False
    assert result.document()["windows"][1]["failure_reason"] == "declared training failure"


def test_validation_failure_preserves_frozen_training_candidate(tmp_path):
    registry, _ = registry_with_bars(tmp_path)

    class ValidationFailure(SuccessfulWorkflow):
        def evaluate_candidate(self, candidate, validation_bars, context):
            if context.window.index == 2:
                raise ValueError("validation evidence unavailable")
            return super().evaluate_candidate(candidate, validation_bars, context)

    result = WalkForwardResearchEngine(registry).run(
        dataset_id="nq-walk-forward",
        plan=plan(),
        workflow_factory=lambda context: ValidationFailure(),
    )

    failed = result.windows[2]
    assert failed.status is WalkForwardWindowStatus.FAILED
    assert failed.failure_stage is WalkForwardFailureStage.VALIDATION
    assert failed.failure_code == "ValueError"
    assert failed.candidate is not None
    assert failed.candidate.selected_after_index == 7
    assert failed.metrics is None
    assert len(failed.candidate.hash) == 64


def test_incorrect_validation_sample_count_fails_the_window(tmp_path):
    registry, _ = registry_with_bars(tmp_path)

    class WrongCount(SuccessfulWorkflow):
        def evaluate_candidate(self, candidate, validation_bars, context):
            return WalkForwardMetrics(
                sample_count=1,
                trade_count=0,
                net_pnl=0,
                max_drawdown=0,
                passed=False,
            )

    result = WalkForwardResearchEngine(registry).run(
        dataset_id="nq-walk-forward",
        plan=plan(),
        workflow_factory=lambda context: WrongCount(),
    )

    assert result.aggregate.failed_windows == 4
    assert all(
        item.failure_stage is WalkForwardFailureStage.VALIDATION
        and "sample_count" in item.failure_reason
        for item in result.windows
    )


def test_equivalent_runs_have_identical_identity_and_result_hashes(tmp_path):
    registry, _ = registry_with_bars(tmp_path)
    engine = WalkForwardResearchEngine(registry)

    first = engine.run(
        dataset_id="nq-walk-forward",
        plan=plan(),
        workflow_factory=lambda context: SuccessfulWorkflow(),
    )
    second = engine.run(
        dataset_id="nq-walk-forward",
        plan=plan(),
        workflow_factory=lambda context: SuccessfulWorkflow(),
    )

    assert first == second
    assert first.run_id == second.run_id
    assert first.result_hash == second.result_hash


def test_nondeterministic_candidate_selection_is_rejected(tmp_path):
    registry, _ = registry_with_bars(tmp_path)
    calls = 0

    class Variable(SuccessfulWorkflow):
        def __init__(self, value):
            super().__init__()
            self.value = value

        def select_candidate(self, training_bars, context):
            return ResearchParameterSet.from_mapping({"value": self.value})

    def factory(context):
        nonlocal calls
        calls += 1
        return Variable(calls)

    with pytest.raises(WalkForwardDeterminismError, match="diverged"):
        WalkForwardResearchEngine(registry).run(
            dataset_id="nq-walk-forward", plan=plan(), workflow_factory=factory
        )


def test_plan_rejects_invalid_or_below_minimum_sizes():
    with pytest.raises(ValueError, match="positive integer"):
        WalkForwardPlan(True, 2, 1, 1)
    with pytest.raises(ValueError, match="training_size"):
        WalkForwardPlan(1, 2, 1, 2)
    with pytest.raises(ValueError, match="validation_size"):
        WalkForwardPlan(2, 1, 1, 2)
    with pytest.raises(ValueError, match="nonnegative integer"):
        generate_walk_forward_windows(-1, plan())


def test_insufficient_dataset_fails_instead_of_returning_empty_success(tmp_path):
    registry, _ = registry_with_bars(tmp_path, count=5)

    with pytest.raises(WalkForwardDataError, match="no complete"):
        WalkForwardResearchEngine(registry).run(
            dataset_id="nq-walk-forward",
            plan=plan(),
            workflow_factory=lambda context: SuccessfulWorkflow(),
        )


def test_modified_dataset_fails_before_workflow_creation(tmp_path):
    registry, source = registry_with_bars(tmp_path)
    source.write_text(source.read_text().replace(",100,101,99,100,10", ",100,101,99,101,10"))
    called = []

    with pytest.raises(DatasetIntegrityError, match="not currently verified"):
        WalkForwardResearchEngine(registry).run(
            dataset_id="nq-walk-forward",
            plan=plan(),
            workflow_factory=lambda context: called.append(True) or SuccessfulWorkflow(),
        )

    assert called == []


def test_walk_forward_module_has_no_execution_dependencies():
    import backend.research.walk_forward as module

    source = Path(module.__file__).read_text(encoding="utf-8").lower()
    forbidden = (
        "from backend.execution", "import backend.execution", "submit_order(",
        "enterlong(", "entershort(", "broker_adapter", "requests", "httpx",
    )
    assert all(token not in source for token in forbidden)
    assert WalkForwardResearchEngine.execution_authorized is False
    assert WalkForwardResearchEngine.production_mutation_authorized is False
    assert WalkForwardResearchEngine.live_execution_authorized is False
