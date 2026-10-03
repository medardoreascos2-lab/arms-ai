"""Deterministic rolling walk-forward evaluation for isolated research."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import Enum
import hashlib
import json
import re
from typing import Protocol

from .backtest_runner import (
    ResearchBar,
    ResearchParameterSet,
    _decimal_text,
    _load_bars,
    _utc_text,
)
from .dataset_registry import HistoricalDataset, HistoricalDatasetRegistry


_HASH = re.compile(r"^[0-9a-f]{64}$")


class WalkForwardEngineError(RuntimeError):
    """Base deterministic walk-forward failure."""


class WalkForwardDataError(WalkForwardEngineError):
    """Verified data cannot satisfy the declared walk-forward plan."""


class WalkForwardDeterminismError(WalkForwardEngineError):
    """Equivalent walk-forward replays produced different results."""


class WalkForwardWindowStatus(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class WalkForwardFailureStage(str, Enum):
    TRAINING = "TRAINING"
    VALIDATION = "VALIDATION"


def _positive_int(value: object, name: str) -> int:
    if type(value) is not int or value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _decimal(value: object, name: str, *, nonnegative: bool = False) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite decimal")
    try:
        result = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite decimal") from exc
    if not result.is_finite() or (nonnegative and result < 0):
        raise ValueError(f"{name} must be a finite nonnegative decimal")
    return result


def _canonical_hash(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, allow_nan=False,
        sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _bar_document(bar: ResearchBar) -> dict[str, object]:
    return {
        "close": _decimal_text(bar.close),
        "high": _decimal_text(bar.high),
        "index": bar.index,
        "low": _decimal_text(bar.low),
        "open": _decimal_text(bar.open),
        "timestamp": _utc_text(bar.timestamp),
        "volume": _decimal_text(bar.volume),
    }


def _bars_hash(bars: tuple[ResearchBar, ...]) -> str:
    return _canonical_hash([_bar_document(bar) for bar in bars])


def _failure(exc: Exception) -> tuple[str, str]:
    code = type(exc).__name__
    reason = str(exc).strip() or code
    return code[:128], reason[:512]


@dataclass(frozen=True)
class WalkForwardPlan:
    training_size: int
    validation_size: int
    step_size: int
    minimum_sample_size: int

    def __post_init__(self) -> None:
        for name in (
            "training_size", "validation_size", "step_size", "minimum_sample_size"
        ):
            object.__setattr__(self, name, _positive_int(getattr(self, name), name))
        if self.training_size < self.minimum_sample_size:
            raise ValueError("training_size must meet minimum_sample_size")
        if self.validation_size < self.minimum_sample_size:
            raise ValueError("validation_size must meet minimum_sample_size")

    def document(self) -> dict[str, int]:
        return {
            "minimum_sample_size": self.minimum_sample_size,
            "step_size": self.step_size,
            "training_size": self.training_size,
            "validation_size": self.validation_size,
        }


@dataclass(frozen=True)
class WalkForwardWindow:
    index: int
    training_start: int
    training_end: int
    validation_start: int
    validation_end: int

    def __post_init__(self) -> None:
        if type(self.index) is not int or self.index < 0:
            raise ValueError("window index must be a nonnegative integer")
        for name in (
            "training_start", "training_end", "validation_start", "validation_end"
        ):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} must be a nonnegative integer")
        if self.training_start >= self.training_end:
            raise ValueError("training window must be nonempty")
        if self.training_end != self.validation_start:
            raise ValueError("training and validation must be contiguous and separate")
        if self.validation_start >= self.validation_end:
            raise ValueError("validation window must be nonempty")

    def document(self) -> dict[str, int]:
        return {
            "index": self.index,
            "training_end": self.training_end,
            "training_start": self.training_start,
            "validation_end": self.validation_end,
            "validation_start": self.validation_start,
        }


def generate_walk_forward_windows(
    total_samples: int, plan: WalkForwardPlan
) -> tuple[WalkForwardWindow, ...]:
    if type(total_samples) is not int or total_samples < 0:
        raise ValueError("total_samples must be a nonnegative integer")
    if not isinstance(plan, WalkForwardPlan):
        raise ValueError("plan must be WalkForwardPlan")
    windows = []
    start = 0
    while start + plan.training_size + plan.validation_size <= total_samples:
        training_end = start + plan.training_size
        windows.append(WalkForwardWindow(
            index=len(windows),
            training_start=start,
            training_end=training_end,
            validation_start=training_end,
            validation_end=training_end + plan.validation_size,
        ))
        start += plan.step_size
    return tuple(windows)


@dataclass(frozen=True)
class WalkForwardContext:
    dataset_id: str
    dataset_record_hash: str
    dataset_sha256: str
    plan_hash: str
    window: WalkForwardWindow
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)


@dataclass(frozen=True)
class WalkForwardCandidate:
    parameters: ResearchParameterSet
    training_data_hash: str
    training_sample_count: int
    training_starts_at: datetime
    training_ends_at: datetime
    selected_after_index: int
    hash: str = field(init=False)
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.parameters, ResearchParameterSet):
            raise ValueError("parameters must be ResearchParameterSet")
        if (
            not isinstance(self.training_data_hash, str)
            or _HASH.fullmatch(self.training_data_hash) is None
        ):
            raise ValueError("training_data_hash must be a sha256 digest")
        _positive_int(self.training_sample_count, "training_sample_count")
        if self.training_starts_at > self.training_ends_at:
            raise ValueError("training timestamps must be chronological")
        if type(self.selected_after_index) is not int or self.selected_after_index < 0:
            raise ValueError("selected_after_index must be nonnegative")
        object.__setattr__(self, "hash", _canonical_hash(self.document(include_hash=False)))

    def document(self, *, include_hash: bool = True) -> dict[str, object]:
        document: dict[str, object] = {
            "parameter_set": self.parameters.canonical_json,
            "parameter_set_sha256": self.parameters.sha256,
            "selected_after_index": self.selected_after_index,
            "training_data_hash": self.training_data_hash,
            "training_ends_at": _utc_text(self.training_ends_at),
            "training_sample_count": self.training_sample_count,
            "training_starts_at": _utc_text(self.training_starts_at),
        }
        if include_hash:
            document["hash"] = self.hash
        return document


@dataclass(frozen=True)
class WalkForwardMetrics:
    sample_count: int
    trade_count: int
    net_pnl: Decimal
    max_drawdown: Decimal
    passed: bool

    def __post_init__(self) -> None:
        _positive_int(self.sample_count, "sample_count")
        if type(self.trade_count) is not int or self.trade_count < 0:
            raise ValueError("trade_count must be a nonnegative integer")
        object.__setattr__(self, "net_pnl", _decimal(self.net_pnl, "net_pnl"))
        object.__setattr__(
            self, "max_drawdown", _decimal(self.max_drawdown, "max_drawdown", nonnegative=True)
        )
        if type(self.passed) is not bool:
            raise ValueError("passed must be bool")

    def document(self) -> dict[str, object]:
        return {
            "max_drawdown": _decimal_text(self.max_drawdown),
            "net_pnl": _decimal_text(self.net_pnl),
            "passed": self.passed,
            "sample_count": self.sample_count,
            "trade_count": self.trade_count,
        }


class WalkForwardWorkflow(Protocol):
    def select_candidate(
        self,
        training_bars: tuple[ResearchBar, ...],
        context: WalkForwardContext,
    ) -> ResearchParameterSet: ...

    def evaluate_candidate(
        self,
        candidate: WalkForwardCandidate,
        validation_bars: tuple[ResearchBar, ...],
        context: WalkForwardContext,
    ) -> WalkForwardMetrics: ...


class WalkForwardWorkflowFactory(Protocol):
    def __call__(self, context: WalkForwardContext) -> WalkForwardWorkflow: ...


@dataclass(frozen=True)
class WalkForwardWindowResult:
    window: WalkForwardWindow
    status: WalkForwardWindowStatus
    candidate: WalkForwardCandidate | None
    metrics: WalkForwardMetrics | None
    failure_stage: WalkForwardFailureStage | None
    failure_code: str | None
    failure_reason: str | None
    hash: str = field(init=False)

    def __post_init__(self) -> None:
        if self.status is WalkForwardWindowStatus.SUCCEEDED:
            if self.candidate is None or self.metrics is None:
                raise ValueError("successful window requires candidate and metrics")
            if any(value is not None for value in (
                self.failure_stage, self.failure_code, self.failure_reason
            )):
                raise ValueError("successful window cannot include failure details")
        elif self.status is WalkForwardWindowStatus.FAILED:
            if self.metrics is not None:
                raise ValueError("failed window cannot include metrics")
            if self.failure_stage is None or not self.failure_code or not self.failure_reason:
                raise ValueError("failed window requires explicit failure details")
        else:
            raise ValueError("invalid walk-forward window status")
        object.__setattr__(self, "hash", _canonical_hash(self.document(include_hash=False)))

    def document(self, *, include_hash: bool = True) -> dict[str, object]:
        document: dict[str, object] = {
            "candidate": None if self.candidate is None else self.candidate.document(),
            "failure_code": self.failure_code,
            "failure_reason": self.failure_reason,
            "failure_stage": None if self.failure_stage is None else self.failure_stage.value,
            "metrics": None if self.metrics is None else self.metrics.document(),
            "status": self.status.value,
            "window": self.window.document(),
        }
        if include_hash:
            document["hash"] = self.hash
        return document


@dataclass(frozen=True)
class WalkForwardAggregate:
    total_windows: int
    successful_windows: int
    failed_windows: int
    passed_validations: int
    failed_validations: int
    failed_window_indexes: tuple[int, ...]
    total_validation_samples: int
    total_trades: int
    total_net_pnl: Decimal
    worst_window_max_drawdown: Decimal
    all_windows_succeeded: bool

    def document(self) -> dict[str, object]:
        return {
            "all_windows_succeeded": self.all_windows_succeeded,
            "failed_validations": self.failed_validations,
            "failed_window_indexes": list(self.failed_window_indexes),
            "failed_windows": self.failed_windows,
            "passed_validations": self.passed_validations,
            "successful_windows": self.successful_windows,
            "total_net_pnl": _decimal_text(self.total_net_pnl),
            "total_trades": self.total_trades,
            "total_validation_samples": self.total_validation_samples,
            "total_windows": self.total_windows,
            "worst_window_max_drawdown": _decimal_text(self.worst_window_max_drawdown),
        }


@dataclass(frozen=True)
class WalkForwardResult:
    run_id: str
    result_hash: str
    dataset_id: str
    dataset_record_hash: str
    dataset_sha256: str
    plan: WalkForwardPlan
    windows: tuple[WalkForwardWindowResult, ...]
    aggregate: WalkForwardAggregate
    deterministic_replay_verified: bool
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)
    live_execution_authorized: bool = field(default=False, init=False)

    def document(self, *, include_result_hash: bool = True) -> dict[str, object]:
        document: dict[str, object] = {
            "aggregate": self.aggregate.document(),
            "dataset_id": self.dataset_id,
            "dataset_record_hash": self.dataset_record_hash,
            "dataset_sha256": self.dataset_sha256,
            "deterministic_replay_verified": self.deterministic_replay_verified,
            "plan": self.plan.document(),
            "run_id": self.run_id,
            "windows": [window.document() for window in self.windows],
        }
        if include_result_hash:
            document["result_hash"] = self.result_hash
        return document


def _aggregate(results: tuple[WalkForwardWindowResult, ...]) -> WalkForwardAggregate:
    succeeded = tuple(
        result for result in results if result.status is WalkForwardWindowStatus.SUCCEEDED
    )
    failed = tuple(
        result for result in results if result.status is WalkForwardWindowStatus.FAILED
    )
    metrics = tuple(result.metrics for result in succeeded if result.metrics is not None)
    return WalkForwardAggregate(
        total_windows=len(results),
        successful_windows=len(succeeded),
        failed_windows=len(failed),
        passed_validations=sum(1 for item in metrics if item.passed),
        failed_validations=sum(1 for item in metrics if not item.passed),
        failed_window_indexes=tuple(item.window.index for item in failed),
        total_validation_samples=sum(item.sample_count for item in metrics),
        total_trades=sum(item.trade_count for item in metrics),
        total_net_pnl=sum((item.net_pnl for item in metrics), Decimal(0)),
        worst_window_max_drawdown=max(
            (item.max_drawdown for item in metrics), default=Decimal(0)
        ),
        all_windows_succeeded=not failed,
    )


class WalkForwardResearchEngine:
    """Evaluates fixed rolling windows without exposing future bars."""

    execution_authorized = False
    production_mutation_authorized = False
    live_execution_authorized = False

    def __init__(self, registry: HistoricalDatasetRegistry):
        if not isinstance(registry, HistoricalDatasetRegistry):
            raise ValueError("registry must be HistoricalDatasetRegistry")
        self._registry = registry

    def run(
        self,
        *,
        dataset_id: str,
        plan: WalkForwardPlan,
        workflow_factory: WalkForwardWorkflowFactory,
    ) -> WalkForwardResult:
        if not isinstance(dataset_id, str) or not dataset_id.strip():
            raise ValueError("dataset_id must be nonempty text")
        if not isinstance(plan, WalkForwardPlan):
            raise ValueError("plan must be WalkForwardPlan")
        if not callable(workflow_factory):
            raise ValueError("workflow_factory must be callable")
        dataset = self._registry.require_verified(dataset_id.strip())
        bars = _load_bars(dataset)
        windows = generate_walk_forward_windows(len(bars), plan)
        if not windows:
            raise WalkForwardDataError(
                "dataset has no complete train/validation window at the minimum sample size"
            )
        plan_hash = _canonical_hash(plan.document())
        run_id = _canonical_hash({
            "dataset_id": dataset.dataset_id,
            "dataset_record_hash": dataset.record_hash,
            "dataset_sha256": dataset.sha256,
            "plan_hash": plan_hash,
        })
        first = self._replay(dataset, bars, windows, plan, plan_hash, run_id, workflow_factory)
        second = self._replay(dataset, bars, windows, plan, plan_hash, run_id, workflow_factory)
        if first.result_hash != second.result_hash:
            raise WalkForwardDeterminismError(
                "equivalent walk-forward replays diverged"
            )
        return self._result(
            dataset, plan, run_id, first.windows, deterministic=True
        )

    def _replay(
        self,
        dataset: HistoricalDataset,
        bars: tuple[ResearchBar, ...],
        windows: tuple[WalkForwardWindow, ...],
        plan: WalkForwardPlan,
        plan_hash: str,
        run_id: str,
        workflow_factory: WalkForwardWorkflowFactory,
    ) -> WalkForwardResult:
        results = []
        for window in windows:
            training = bars[window.training_start:window.training_end]
            validation = bars[window.validation_start:window.validation_end]
            if len(training) < plan.minimum_sample_size or len(validation) < plan.minimum_sample_size:
                raise WalkForwardDataError("generated window violates minimum sample size")
            if training[-1].timestamp >= validation[0].timestamp:
                raise WalkForwardDataError("training and validation are not chronological")
            context = WalkForwardContext(
                dataset_id=dataset.dataset_id,
                dataset_record_hash=dataset.record_hash,
                dataset_sha256=dataset.sha256,
                plan_hash=plan_hash,
                window=window,
            )
            try:
                workflow = workflow_factory(context)
                selector = getattr(workflow, "select_candidate", None)
                evaluator = getattr(workflow, "evaluate_candidate", None)
                if not callable(selector) or not callable(evaluator):
                    raise TypeError(
                        "workflow must implement select_candidate() and evaluate_candidate()"
                    )
                parameters = selector(training, context)
                if not isinstance(parameters, ResearchParameterSet):
                    raise TypeError("select_candidate() must return ResearchParameterSet")
                candidate = WalkForwardCandidate(
                    parameters=parameters,
                    training_data_hash=_bars_hash(training),
                    training_sample_count=len(training),
                    training_starts_at=training[0].timestamp,
                    training_ends_at=training[-1].timestamp,
                    selected_after_index=training[-1].index,
                )
            except Exception as exc:
                if isinstance(exc, (MemoryError, RecursionError)):
                    raise
                code, reason = _failure(exc)
                results.append(WalkForwardWindowResult(
                    window=window,
                    status=WalkForwardWindowStatus.FAILED,
                    candidate=None,
                    metrics=None,
                    failure_stage=WalkForwardFailureStage.TRAINING,
                    failure_code=code,
                    failure_reason=reason,
                ))
                continue
            try:
                metrics = evaluator(candidate, validation, context)
                if not isinstance(metrics, WalkForwardMetrics):
                    raise TypeError("evaluate_candidate() must return WalkForwardMetrics")
                if metrics.sample_count != len(validation):
                    raise ValueError(
                        "validation metrics sample_count must match the isolated window"
                    )
                results.append(WalkForwardWindowResult(
                    window=window,
                    status=WalkForwardWindowStatus.SUCCEEDED,
                    candidate=candidate,
                    metrics=metrics,
                    failure_stage=None,
                    failure_code=None,
                    failure_reason=None,
                ))
            except Exception as exc:
                if isinstance(exc, (MemoryError, RecursionError)):
                    raise
                code, reason = _failure(exc)
                results.append(WalkForwardWindowResult(
                    window=window,
                    status=WalkForwardWindowStatus.FAILED,
                    candidate=candidate,
                    metrics=None,
                    failure_stage=WalkForwardFailureStage.VALIDATION,
                    failure_code=code,
                    failure_reason=reason,
                ))
        return self._result(dataset, plan, run_id, tuple(results), deterministic=False)

    @staticmethod
    def _result(
        dataset: HistoricalDataset,
        plan: WalkForwardPlan,
        run_id: str,
        windows: tuple[WalkForwardWindowResult, ...],
        *,
        deterministic: bool,
    ) -> WalkForwardResult:
        provisional = WalkForwardResult(
            run_id=run_id,
            result_hash="0" * 64,
            dataset_id=dataset.dataset_id,
            dataset_record_hash=dataset.record_hash,
            dataset_sha256=dataset.sha256,
            plan=plan,
            windows=windows,
            aggregate=_aggregate(windows),
            deterministic_replay_verified=deterministic,
        )
        digest = _canonical_hash(provisional.document(include_result_hash=False))
        return replace(provisional, result_hash=digest)
