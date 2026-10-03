"""Strict, deterministic out-of-sample validation for frozen candidates."""

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
    _utc,
    _utc_text,
)
from .dataset_registry import HistoricalDatasetRegistry
from .experiment import ExperimentWindow, StrategyExperiment, StrategyExperimentStatus


_HASH = re.compile(r"^[0-9a-f]{64}$")


class OosValidationError(RuntimeError):
    """Base strict out-of-sample validation failure."""


class OosCandidateFreezeError(OosValidationError):
    """A candidate cannot be frozen under the declared OOS contract."""


class OosDataError(OosValidationError):
    """Pinned OOS evidence is unavailable, changed, or insufficient."""


class OosEvaluationError(OosValidationError):
    """The isolated OOS evaluator failed or returned invalid evidence."""


class OosDeterminismError(OosValidationError):
    """Equivalent OOS evaluations produced different results."""


class OosOutcome(str, Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"


def _positive_int(value: object, name: str, *, allow_zero: bool = False) -> int:
    minimum = 0 if allow_zero else 1
    if type(value) is not int or value < minimum:
        qualifier = "nonnegative" if allow_zero else "positive"
        raise ValueError(f"{name} must be a {qualifier} integer")
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


def _require_hash(value: object, name: str) -> str:
    if not isinstance(value, str) or _HASH.fullmatch(value) is None:
        raise ValueError(f"{name} must be a lowercase sha256 digest")
    return value


@dataclass(frozen=True)
class OosValidationRules:
    minimum_sample_size: int
    minimum_trade_count: int
    minimum_net_pnl: Decimal
    maximum_drawdown: Decimal

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "minimum_sample_size",
            _positive_int(self.minimum_sample_size, "minimum_sample_size"),
        )
        object.__setattr__(
            self,
            "minimum_trade_count",
            _positive_int(self.minimum_trade_count, "minimum_trade_count", allow_zero=True),
        )
        object.__setattr__(
            self, "minimum_net_pnl", _decimal(self.minimum_net_pnl, "minimum_net_pnl")
        )
        object.__setattr__(
            self,
            "maximum_drawdown",
            _decimal(self.maximum_drawdown, "maximum_drawdown", nonnegative=True),
        )

    def document(self) -> dict[str, object]:
        return {
            "maximum_drawdown": _decimal_text(self.maximum_drawdown),
            "minimum_net_pnl": _decimal_text(self.minimum_net_pnl),
            "minimum_sample_size": self.minimum_sample_size,
            "minimum_trade_count": self.minimum_trade_count,
        }


@dataclass(frozen=True)
class FrozenOosCandidate:
    experiment_id: str
    experiment_hash: str
    parent_production_version: str
    parameters: ResearchParameterSet
    oos_dataset_id: str
    oos_dataset_record_hash: str
    oos_dataset_sha256: str
    oos_window: ExperimentWindow
    rules: OosValidationRules
    frozen_at: datetime
    hash: str = field(init=False)
    execution_authorized: bool = field(default=False, init=False)
    paper_execution_authorized: bool = field(default=False, init=False)
    live_execution_authorized: bool = field(default=False, init=False)
    production_assignment_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.experiment_id, str) or not self.experiment_id:
            raise ValueError("experiment_id must be nonempty text")
        _require_hash(self.experiment_hash, "experiment_hash")
        if not isinstance(self.parent_production_version, str) or not self.parent_production_version:
            raise ValueError("parent_production_version must be nonempty text")
        if not isinstance(self.parameters, ResearchParameterSet):
            raise ValueError("parameters must be ResearchParameterSet")
        if not isinstance(self.oos_dataset_id, str) or not self.oos_dataset_id:
            raise ValueError("oos_dataset_id must be nonempty text")
        _require_hash(self.oos_dataset_record_hash, "oos_dataset_record_hash")
        _require_hash(self.oos_dataset_sha256, "oos_dataset_sha256")
        if not isinstance(self.oos_window, ExperimentWindow):
            raise ValueError("oos_window must be ExperimentWindow")
        if not isinstance(self.rules, OosValidationRules):
            raise ValueError("rules must be OosValidationRules")
        frozen = _utc(self.frozen_at, "frozen_at")
        if frozen > self.oos_window.starts_at:
            raise ValueError("candidate must be frozen before the OOS window starts")
        object.__setattr__(self, "frozen_at", frozen)
        object.__setattr__(self, "hash", _canonical_hash(self.document(include_hash=False)))

    def document(self, *, include_hash: bool = True) -> dict[str, object]:
        document: dict[str, object] = {
            "experiment_hash": self.experiment_hash,
            "experiment_id": self.experiment_id,
            "frozen_at": _utc_text(self.frozen_at),
            "oos_dataset_id": self.oos_dataset_id,
            "oos_dataset_record_hash": self.oos_dataset_record_hash,
            "oos_dataset_sha256": self.oos_dataset_sha256,
            "oos_window": self.oos_window.document(),
            "parameter_set": self.parameters.canonical_json,
            "parameter_set_sha256": self.parameters.sha256,
            "parent_production_version": self.parent_production_version,
            "rules": self.rules.document(),
        }
        if include_hash:
            document["hash"] = self.hash
        return document


@dataclass(frozen=True)
class OosEvaluationContext:
    candidate_hash: str
    dataset_id: str
    dataset_record_hash: str
    dataset_sha256: str
    window: ExperimentWindow
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)


@dataclass(frozen=True)
class OosMetrics:
    sample_count: int
    trade_count: int
    net_pnl: Decimal
    max_drawdown: Decimal

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "sample_count", _positive_int(self.sample_count, "sample_count")
        )
        object.__setattr__(
            self,
            "trade_count",
            _positive_int(self.trade_count, "trade_count", allow_zero=True),
        )
        object.__setattr__(self, "net_pnl", _decimal(self.net_pnl, "net_pnl"))
        object.__setattr__(
            self,
            "max_drawdown",
            _decimal(self.max_drawdown, "max_drawdown", nonnegative=True),
        )

    def document(self) -> dict[str, object]:
        return {
            "max_drawdown": _decimal_text(self.max_drawdown),
            "net_pnl": _decimal_text(self.net_pnl),
            "sample_count": self.sample_count,
            "trade_count": self.trade_count,
        }


class OosEvaluator(Protocol):
    def evaluate(
        self,
        candidate: FrozenOosCandidate,
        oos_bars: tuple[ResearchBar, ...],
        context: OosEvaluationContext,
    ) -> OosMetrics: ...


class OosEvaluatorFactory(Protocol):
    def __call__(self, context: OosEvaluationContext) -> OosEvaluator: ...


@dataclass(frozen=True)
class OosValidationResult:
    run_id: str
    result_hash: str
    candidate_hash: str
    experiment_id: str
    experiment_hash: str
    dataset_id: str
    dataset_record_hash: str
    dataset_sha256: str
    outcome: OosOutcome
    blocking_reasons: tuple[str, ...]
    metrics: OosMetrics
    oos_starts_at: datetime
    oos_ends_at: datetime
    deterministic_replay_verified: bool
    confidence_intervals: None = field(default=None, init=False)
    confidence_intervals_implemented: bool = field(default=False, init=False)
    execution_authorized: bool = field(default=False, init=False)
    paper_execution_authorized: bool = field(default=False, init=False)
    live_execution_authorized: bool = field(default=False, init=False)
    production_assignment_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if self.blocking_reasons != tuple(sorted(set(self.blocking_reasons))):
            raise ValueError("blocking_reasons must be sorted and unique")
        if self.outcome is OosOutcome.PASSED and self.blocking_reasons:
            raise ValueError("passed OOS result cannot have blocking reasons")
        if self.outcome is OosOutcome.FAILED and not self.blocking_reasons:
            raise ValueError("failed OOS result requires blocking reasons")

    def document(self, *, include_result_hash: bool = True) -> dict[str, object]:
        document: dict[str, object] = {
            "blocking_reasons": list(self.blocking_reasons),
            "candidate_hash": self.candidate_hash,
            "confidence_intervals": None,
            "confidence_intervals_implemented": False,
            "dataset_id": self.dataset_id,
            "dataset_record_hash": self.dataset_record_hash,
            "dataset_sha256": self.dataset_sha256,
            "deterministic_replay_verified": self.deterministic_replay_verified,
            "experiment_hash": self.experiment_hash,
            "experiment_id": self.experiment_id,
            "metrics": self.metrics.document(),
            "oos_ends_at": _utc_text(self.oos_ends_at),
            "oos_starts_at": _utc_text(self.oos_starts_at),
            "outcome": self.outcome.value,
            "run_id": self.run_id,
        }
        if include_result_hash:
            document["result_hash"] = self.result_hash
        return document


class OutOfSampleValidator:
    """Freezes a validated candidate, then evaluates only pinned OOS bars."""

    execution_authorized = False
    paper_execution_authorized = False
    live_execution_authorized = False
    production_assignment_authorized = False

    def __init__(self, registry: HistoricalDatasetRegistry):
        if not isinstance(registry, HistoricalDatasetRegistry):
            raise ValueError("registry must be HistoricalDatasetRegistry")
        self._registry = registry

    def freeze_candidate(
        self,
        *,
        experiment: StrategyExperiment,
        oos_dataset_id: str,
        rules: OosValidationRules,
        frozen_at: datetime,
    ) -> FrozenOosCandidate:
        if not isinstance(experiment, StrategyExperiment):
            raise OosCandidateFreezeError("experiment must be StrategyExperiment")
        if experiment.status is not StrategyExperimentStatus.VALIDATION_PASSED:
            raise OosCandidateFreezeError(
                "experiment must be VALIDATION_PASSED before OOS candidate freeze"
            )
        if experiment.status_updated_at < experiment.validation_window.ends_at:
            raise OosCandidateFreezeError(
                "validation cannot pass before the validation window ends"
            )
        if not isinstance(oos_dataset_id, str) or oos_dataset_id not in experiment.dataset_ids:
            raise OosCandidateFreezeError(
                "OOS dataset must be one of the experiment dataset IDs"
            )
        if not isinstance(rules, OosValidationRules):
            raise OosCandidateFreezeError("rules must be OosValidationRules")
        frozen = _utc(frozen_at, "frozen_at")
        if frozen < experiment.status_updated_at:
            raise OosCandidateFreezeError(
                "candidate cannot be frozen before validation passed"
            )
        if frozen > experiment.test_window.starts_at:
            raise OosCandidateFreezeError(
                "candidate must be frozen before the OOS window starts"
            )
        dataset = self._registry.require_verified(oos_dataset_id)
        return FrozenOosCandidate(
            experiment_id=experiment.experiment_id,
            experiment_hash=experiment.hash,
            parent_production_version=experiment.parent_production_version,
            parameters=experiment.candidate_parameters,
            oos_dataset_id=dataset.dataset_id,
            oos_dataset_record_hash=dataset.record_hash,
            oos_dataset_sha256=dataset.sha256,
            oos_window=experiment.test_window,
            rules=rules,
            frozen_at=frozen,
        )

    def validate(
        self,
        candidate: FrozenOosCandidate,
        evaluator_factory: OosEvaluatorFactory,
    ) -> OosValidationResult:
        if not isinstance(candidate, FrozenOosCandidate):
            raise ValueError("candidate must be FrozenOosCandidate")
        if not callable(evaluator_factory):
            raise ValueError("evaluator_factory must be callable")
        dataset = self._registry.require_verified(candidate.oos_dataset_id)
        if (
            dataset.record_hash != candidate.oos_dataset_record_hash
            or dataset.sha256 != candidate.oos_dataset_sha256
        ):
            raise OosDataError("current dataset identity differs from the frozen OOS pin")
        bars = _load_bars(dataset)
        oos_bars = tuple(
            bar for bar in bars
            if candidate.oos_window.starts_at <= bar.timestamp < candidate.oos_window.ends_at
        )
        if len(oos_bars) < candidate.rules.minimum_sample_size:
            raise OosDataError("OOS window does not meet minimum sample size")
        if oos_bars[0].timestamp < candidate.frozen_at:
            raise OosDataError("OOS bars precede the frozen candidate boundary")
        context = OosEvaluationContext(
            candidate_hash=candidate.hash,
            dataset_id=dataset.dataset_id,
            dataset_record_hash=dataset.record_hash,
            dataset_sha256=dataset.sha256,
            window=candidate.oos_window,
        )
        run_id = _canonical_hash({
            "candidate_hash": candidate.hash,
            "dataset_record_hash": dataset.record_hash,
            "dataset_sha256": dataset.sha256,
        })
        first = self._evaluate(candidate, oos_bars, context, run_id, evaluator_factory)
        second = self._evaluate(candidate, oos_bars, context, run_id, evaluator_factory)
        if first.result_hash != second.result_hash:
            raise OosDeterminismError("equivalent OOS evaluations diverged")
        return self._result(candidate, context, run_id, first.metrics, deterministic=True)

    def _evaluate(
        self,
        candidate: FrozenOosCandidate,
        bars: tuple[ResearchBar, ...],
        context: OosEvaluationContext,
        run_id: str,
        evaluator_factory: OosEvaluatorFactory,
    ) -> OosValidationResult:
        try:
            evaluator = evaluator_factory(context)
            method = getattr(evaluator, "evaluate", None)
            if not callable(method):
                raise TypeError("OOS evaluator must implement evaluate()")
            metrics = method(candidate, bars, context)
            if not isinstance(metrics, OosMetrics):
                raise TypeError("OOS evaluator must return OosMetrics")
            if metrics.sample_count != len(bars):
                raise ValueError("OOS metrics sample_count must match isolated OOS bars")
        except Exception as exc:
            if isinstance(exc, (MemoryError, RecursionError)):
                raise
            raise OosEvaluationError("isolated OOS evaluation failed") from exc
        return self._result(candidate, context, run_id, metrics, deterministic=False)

    @staticmethod
    def _result(
        candidate: FrozenOosCandidate,
        context: OosEvaluationContext,
        run_id: str,
        metrics: OosMetrics,
        *,
        deterministic: bool,
    ) -> OosValidationResult:
        reasons = []
        if metrics.trade_count < candidate.rules.minimum_trade_count:
            reasons.append("MINIMUM_TRADE_COUNT_NOT_MET")
        if metrics.net_pnl < candidate.rules.minimum_net_pnl:
            reasons.append("MINIMUM_NET_PNL_NOT_MET")
        if metrics.max_drawdown > candidate.rules.maximum_drawdown:
            reasons.append("MAXIMUM_DRAWDOWN_EXCEEDED")
        blocking = tuple(sorted(reasons))
        provisional = OosValidationResult(
            run_id=run_id,
            result_hash="0" * 64,
            candidate_hash=candidate.hash,
            experiment_id=candidate.experiment_id,
            experiment_hash=candidate.experiment_hash,
            dataset_id=context.dataset_id,
            dataset_record_hash=context.dataset_record_hash,
            dataset_sha256=context.dataset_sha256,
            outcome=OosOutcome.PASSED if not blocking else OosOutcome.FAILED,
            blocking_reasons=blocking,
            metrics=metrics,
            oos_starts_at=context.window.starts_at,
            oos_ends_at=context.window.ends_at,
            deterministic_replay_verified=deterministic,
        )
        digest = _canonical_hash(provisional.document(include_result_hash=False))
        return replace(provisional, result_hash=digest)
