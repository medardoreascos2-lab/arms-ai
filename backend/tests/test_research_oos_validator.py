"""R31E tests for strict frozen-candidate out-of-sample validation."""

from dataclasses import FrozenInstanceError
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
from backend.research.experiment import (
    ExperimentWindow,
    StrategyExperiment,
    StrategyExperimentStatus,
)
from backend.research.oos_validator import (
    OosCandidateFreezeError,
    OosDataError,
    OosDeterminismError,
    OosEvaluationError,
    OosMetrics,
    OosOutcome,
    OosValidationRules,
    OutOfSampleValidator,
)


UTC = timezone.utc
TRAIN_START = datetime(2026, 7, 1, tzinfo=UTC)
VALIDATION_START = datetime(2026, 8, 1, tzinfo=UTC)
TEST_START = datetime(2026, 9, 1, 14, 30, tzinfo=UTC)
TEST_END = TEST_START + timedelta(minutes=4)


def registry_with_oos(tmp_path: Path, oos_count: int = 4):
    source = tmp_path / "oos.csv"
    lines = ["timestamp,open,high,low,close,volume"]
    # Explicit pre-OOS and post-OOS rows prove the evaluator receives only test bars.
    timestamps = [TEST_START - timedelta(minutes=1)]
    timestamps.extend(TEST_START + timedelta(minutes=i) for i in range(oos_count))
    timestamps.append(TEST_END)
    for index, timestamp in enumerate(timestamps):
        price = Decimal(100) + Decimal(index)
        lines.append(
            f"{timestamp.isoformat().replace('+00:00', 'Z')},"
            f"{price},{price + 1},{price - 1},{price},10"
        )
    source.write_text("\n".join(lines) + "\n", encoding="utf-8")
    registry = HistoricalDatasetRegistry((tmp_path,))
    registry.register(
        HistoricalDatasetRegistration(
            dataset_id="nq-oos-september",
            instrument="NQ",
            contract="NQ DEC26",
            timeframe="1m",
            session_template="CME ETH",
            starts_at=TEST_START - timedelta(minutes=1),
            ends_at=TEST_END + timedelta(minutes=1),
            source="test-fixture:explicit-simulated-oos-bars",
            window=DatasetWindow.ONE_MONTH,
            file_format=DatasetFileFormat.CSV,
            expected_bar_count=len(timestamps),
            expected_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
            certification_status=DatasetCertificationStatus.AVAILABLE_UNCERTIFIED,
        ),
        path=source,
        registered_at=TRAIN_START,
    )
    return registry, source


def validation_passed_experiment():
    item = StrategyExperiment.create(
        experiment_id="exp-oos-001",
        parent_production_version="prod-v8",
        candidate_parameters=ResearchParameterSet.from_mapping(
            {"risk": Decimal("0.5"), "threshold": Decimal("0.8")}
        ),
        dataset_ids=("nq-oos-september", "nq-train", "nq-validation"),
        train_window=ExperimentWindow(TRAIN_START, VALIDATION_START),
        validation_window=ExperimentWindow(
            VALIDATION_START, TEST_START - timedelta(days=1)
        ),
        test_window=ExperimentWindow(TEST_START, TEST_END),
        creation_reason="Predeclared strict OOS evaluation",
        created_at=TRAIN_START,
    )
    item = item.transition(
        StrategyExperimentStatus.BACKTESTED,
        reason="walk-forward complete",
        transitioned_at=TEST_START - timedelta(days=2),
    )
    return item.transition(
        StrategyExperimentStatus.VALIDATION_PASSED,
        reason="validation gates passed",
        transitioned_at=TEST_START - timedelta(days=1),
    )


def rules(**changes):
    values = dict(
        minimum_sample_size=4,
        minimum_trade_count=2,
        minimum_net_pnl=Decimal("0"),
        maximum_drawdown=Decimal("100"),
    )
    values.update(changes)
    return OosValidationRules(**values)


def frozen_candidate(tmp_path: Path, **changes):
    registry, source = registry_with_oos(tmp_path)
    values = dict(
        experiment=validation_passed_experiment(),
        oos_dataset_id="nq-oos-september",
        rules=rules(),
        frozen_at=TEST_START - timedelta(hours=1),
    )
    values.update(changes)
    candidate = OutOfSampleValidator(registry).freeze_candidate(**values)
    return registry, source, candidate


class PassingEvaluator:
    def __init__(self, seen=None):
        self.seen = seen

    def evaluate(self, candidate, oos_bars, context):
        if self.seen is not None:
            self.seen.append((
                tuple(bar.timestamp for bar in oos_bars),
                candidate.parameters,
                context,
            ))
        return OosMetrics(
            sample_count=len(oos_bars),
            trade_count=3,
            net_pnl=Decimal("250"),
            max_drawdown=Decimal("75"),
        )


def test_freeze_pins_candidate_parameters_rules_and_dataset_identity(tmp_path):
    registry, _, candidate = frozen_candidate(tmp_path)
    record = registry.require_verified("nq-oos-september")

    assert candidate.experiment_id == "exp-oos-001"
    assert candidate.experiment_hash == validation_passed_experiment().hash
    assert candidate.parameters == validation_passed_experiment().candidate_parameters
    assert candidate.oos_dataset_record_hash == record.record_hash
    assert candidate.oos_dataset_sha256 == record.sha256
    assert candidate.oos_window == validation_passed_experiment().test_window
    assert candidate.rules == rules()
    assert len(candidate.hash) == 64
    assert candidate.execution_authorized is False
    assert candidate.paper_execution_authorized is False
    assert candidate.live_execution_authorized is False
    assert candidate.production_assignment_authorized is False
    with pytest.raises(FrozenInstanceError):
        candidate.parameters = ResearchParameterSet.from_mapping({"risk": 10})


def test_candidate_freeze_requires_validation_passed_status(tmp_path):
    registry, _ = registry_with_oos(tmp_path)
    research = StrategyExperiment.create(
        experiment_id="research-only",
        parent_production_version="prod-v8",
        candidate_parameters=ResearchParameterSet.from_mapping({"risk": 1}),
        dataset_ids=("nq-oos-september",),
        train_window=ExperimentWindow(TRAIN_START, VALIDATION_START),
        validation_window=ExperimentWindow(
            VALIDATION_START, TEST_START - timedelta(days=1)
        ),
        test_window=ExperimentWindow(TEST_START, TEST_END),
        creation_reason="not ready",
        created_at=TRAIN_START,
    )

    with pytest.raises(OosCandidateFreezeError, match="VALIDATION_PASSED"):
        OutOfSampleValidator(registry).freeze_candidate(
            experiment=research,
            oos_dataset_id="nq-oos-september",
            rules=rules(),
            frozen_at=TEST_START - timedelta(hours=1),
        )


def test_candidate_freeze_rejects_validation_passed_before_window_end(tmp_path):
    registry, _ = registry_with_oos(tmp_path)
    item = StrategyExperiment.create(
        experiment_id="premature-validation",
        parent_production_version="prod-v8",
        candidate_parameters=ResearchParameterSet.from_mapping({"risk": 1}),
        dataset_ids=("nq-oos-september",),
        train_window=ExperimentWindow(TRAIN_START, VALIDATION_START),
        validation_window=ExperimentWindow(
            VALIDATION_START, TEST_START - timedelta(days=1)
        ),
        test_window=ExperimentWindow(TEST_START, TEST_END),
        creation_reason="premature status regression",
        created_at=TRAIN_START,
    )
    item = item.transition(
        StrategyExperimentStatus.BACKTESTED,
        reason="backtest",
        transitioned_at=VALIDATION_START,
    ).transition(
        StrategyExperimentStatus.VALIDATION_PASSED,
        reason="incorrect early pass",
        transitioned_at=VALIDATION_START + timedelta(days=1),
    )

    with pytest.raises(OosCandidateFreezeError, match="before the validation window ends"):
        OutOfSampleValidator(registry).freeze_candidate(
            experiment=item,
            oos_dataset_id="nq-oos-september",
            rules=rules(),
            frozen_at=TEST_START - timedelta(hours=1),
        )


def test_freeze_rejects_unlisted_dataset_or_late_boundary(tmp_path):
    registry, _ = registry_with_oos(tmp_path)
    validator = OutOfSampleValidator(registry)
    item = validation_passed_experiment()

    with pytest.raises(OosCandidateFreezeError, match="experiment dataset IDs"):
        validator.freeze_candidate(
            experiment=item,
            oos_dataset_id="not-declared",
            rules=rules(),
            frozen_at=TEST_START - timedelta(hours=1),
        )
    with pytest.raises(OosCandidateFreezeError, match="before the OOS"):
        validator.freeze_candidate(
            experiment=item,
            oos_dataset_id="nq-oos-september",
            rules=rules(),
            frozen_at=TEST_START + timedelta(seconds=1),
        )


def test_validator_exposes_only_bars_inside_frozen_test_window(tmp_path):
    registry, _, candidate = frozen_candidate(tmp_path)
    seen = []

    result = OutOfSampleValidator(registry).validate(
        candidate, lambda context: PassingEvaluator(seen)
    )

    assert len(seen) == 2
    for timestamps, parameters, context in seen:
        assert timestamps == tuple(TEST_START + timedelta(minutes=i) for i in range(4))
        assert all(TEST_START <= value < TEST_END for value in timestamps)
        assert parameters is candidate.parameters
        assert context.window == candidate.oos_window
        assert context.candidate_hash == candidate.hash
        assert context.execution_authorized is False
        assert context.production_mutation_authorized is False
    assert result.outcome is OosOutcome.PASSED


def test_passing_result_reports_metrics_and_explicitly_omits_confidence_intervals(tmp_path):
    registry, _, candidate = frozen_candidate(tmp_path)

    result = OutOfSampleValidator(registry).validate(
        candidate, lambda context: PassingEvaluator()
    )

    assert result.blocking_reasons == ()
    assert result.metrics.trade_count == 3
    assert result.metrics.net_pnl == Decimal("250")
    assert result.metrics.max_drawdown == Decimal("75")
    assert result.deterministic_replay_verified is True
    assert result.confidence_intervals is None
    assert result.confidence_intervals_implemented is False
    assert result.document()["confidence_intervals"] is None
    assert result.execution_authorized is False
    assert result.paper_execution_authorized is False
    assert result.live_execution_authorized is False
    assert result.production_assignment_authorized is False


def test_all_failed_gates_are_reported_without_short_circuiting(tmp_path):
    registry, _, candidate = frozen_candidate(tmp_path)

    class FailingGates:
        def evaluate(self, candidate, oos_bars, context):
            return OosMetrics(
                sample_count=len(oos_bars),
                trade_count=1,
                net_pnl=Decimal("-10"),
                max_drawdown=Decimal("101"),
            )

    result = OutOfSampleValidator(registry).validate(
        candidate, lambda context: FailingGates()
    )

    assert result.outcome is OosOutcome.FAILED
    assert result.blocking_reasons == (
        "MAXIMUM_DRAWDOWN_EXCEEDED",
        "MINIMUM_NET_PNL_NOT_MET",
        "MINIMUM_TRADE_COUNT_NOT_MET",
    )
    assert result.metrics.trade_count == 1


def test_changed_dataset_fails_before_oos_evaluator(tmp_path):
    registry, source, candidate = frozen_candidate(tmp_path)
    source.write_text(source.read_text().replace(",101,102,100,101,10", ",101,102,100,102,10"))
    called = []

    with pytest.raises(DatasetIntegrityError, match="not currently verified"):
        OutOfSampleValidator(registry).validate(
            candidate, lambda context: called.append(True) or PassingEvaluator()
        )

    assert called == []


def test_record_identity_pin_is_checked_before_evaluation(tmp_path, monkeypatch):
    registry, _, candidate = frozen_candidate(tmp_path)
    record = registry.require_verified("nq-oos-september")
    altered = object.__new__(type(record))
    altered.__dict__.update(record.__dict__)
    altered.__dict__["record_hash"] = "0" * 64
    monkeypatch.setattr(registry, "require_verified", lambda dataset_id: altered)
    called = []

    with pytest.raises(OosDataError, match="differs from the frozen OOS pin"):
        OutOfSampleValidator(registry).validate(
            candidate, lambda context: called.append(True) or PassingEvaluator()
        )

    assert called == []


def test_incorrect_metrics_sample_count_fails_closed(tmp_path):
    registry, _, candidate = frozen_candidate(tmp_path)

    class WrongCount:
        def evaluate(self, candidate, oos_bars, context):
            return OosMetrics(1, 0, 0, 0)

    with pytest.raises(OosEvaluationError, match="evaluation failed") as failure:
        OutOfSampleValidator(registry).validate(
            candidate, lambda context: WrongCount()
        )
    assert "sample_count" in str(failure.value.__cause__)


def test_insufficient_oos_samples_fail_before_evaluator(tmp_path):
    registry, _ = registry_with_oos(tmp_path, oos_count=2)
    candidate = OutOfSampleValidator(registry).freeze_candidate(
        experiment=validation_passed_experiment(),
        oos_dataset_id="nq-oos-september",
        rules=rules(minimum_sample_size=4),
        frozen_at=TEST_START - timedelta(hours=1),
    )
    called = []

    with pytest.raises(OosDataError, match="minimum sample size"):
        OutOfSampleValidator(registry).validate(
            candidate, lambda context: called.append(True) or PassingEvaluator()
        )
    assert called == []


def test_equivalent_validations_have_identical_hashes(tmp_path):
    registry, _, candidate = frozen_candidate(tmp_path)
    validator = OutOfSampleValidator(registry)

    first = validator.validate(candidate, lambda context: PassingEvaluator())
    second = validator.validate(candidate, lambda context: PassingEvaluator())

    assert first == second
    assert first.run_id == second.run_id
    assert first.result_hash == second.result_hash


def test_nondeterministic_oos_metrics_are_rejected(tmp_path):
    registry, _, candidate = frozen_candidate(tmp_path)
    calls = 0

    class Variable:
        def __init__(self, value):
            self.value = value

        def evaluate(self, candidate, oos_bars, context):
            return OosMetrics(len(oos_bars), 3, self.value, 1)

    def factory(context):
        nonlocal calls
        calls += 1
        return Variable(calls)

    with pytest.raises(OosDeterminismError, match="diverged"):
        OutOfSampleValidator(registry).validate(candidate, factory)


def test_evaluator_errors_never_return_partial_oos_success(tmp_path):
    registry, _, candidate = frozen_candidate(tmp_path)

    class Explodes:
        def evaluate(self, candidate, oos_bars, context):
            raise RuntimeError("no result")

    with pytest.raises(OosEvaluationError, match="evaluation failed"):
        OutOfSampleValidator(registry).validate(
            candidate, lambda context: Explodes()
        )


def test_oos_rules_validate_exact_gate_values():
    with pytest.raises(ValueError, match="positive integer"):
        rules(minimum_sample_size=0)
    with pytest.raises(ValueError, match="nonnegative integer"):
        rules(minimum_trade_count=-1)
    with pytest.raises(ValueError, match="nonnegative decimal"):
        rules(maximum_drawdown=-1)


def test_oos_module_has_no_parameter_search_or_execution_dependencies():
    import backend.research.oos_validator as module

    source = Path(module.__file__).read_text(encoding="utf-8").lower()
    forbidden = (
        "select_candidate", "optimize", "parameter_search",
        "from backend.execution", "import backend.execution", "submit_order(",
        "enterlong(", "entershort(", "broker_adapter", "requests", "httpx",
    )
    assert all(token not in source for token in forbidden)
    assert OutOfSampleValidator.execution_authorized is False
    assert OutOfSampleValidator.paper_execution_authorized is False
    assert OutOfSampleValidator.live_execution_authorized is False
    assert OutOfSampleValidator.production_assignment_authorized is False
