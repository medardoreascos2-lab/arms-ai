"""Strict, research-only strategy promotion eligibility evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
import hashlib
import json
import re

from .challenger_registry import ChallengerStatus, StrategyChallengerRecord


_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_HASH = re.compile(r"^[0-9a-f]{64}$")
_CRITERION_NAMES = (
    "minimum_trades",
    "minimum_oos_periods",
    "walk_forward_consistency",
    "max_drawdown",
    "profit_factor",
    "expectancy",
    "stress_survival",
    "parameter_stability",
)


class PromotionGateError(RuntimeError):
    """Promotion evidence cannot be safely evaluated."""


class PromotionGateOutcome(str, Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"


def _text(value: object, name: str, *, identifier: bool = False) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be nonempty text")
    normalized = value.strip()
    if len(normalized) > 512:
        raise ValueError(f"{name} is too long")
    if identifier and _ID.fullmatch(normalized) is None:
        raise ValueError(f"{name} is invalid")
    return normalized


def _sha256(value: object, name: str) -> str:
    if not isinstance(value, str) or _HASH.fullmatch(value) is None:
        raise ValueError(f"{name} must be a lowercase sha256 digest")
    return value


def _utc(value: datetime, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _utc_text(value: datetime) -> str:
    return _utc(value, "timestamp").isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def _decimal(value: object, name: str, *, nonnegative: bool = False) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite Decimal")
    try:
        number = value if isinstance(value, Decimal) else Decimal(str(value))
    except Exception as exc:
        raise ValueError(f"{name} must be a finite Decimal") from exc
    if not number.is_finite():
        raise ValueError(f"{name} must be a finite Decimal")
    if nonnegative and number < 0:
        raise ValueError(f"{name} must be nonnegative")
    return number


def _ratio(value: object, name: str) -> Decimal:
    number = _decimal(value, name, nonnegative=True)
    if number > 1:
        raise ValueError(f"{name} must be between 0 and 1")
    return number


def _positive_int(value: object, name: str, *, allow_zero: bool = False) -> int:
    minimum = 0 if allow_zero else 1
    if type(value) is not int or value < minimum:
        qualifier = "nonnegative" if allow_zero else "positive"
        raise ValueError(f"{name} must be a {qualifier} integer")
    return value


def _evidence_ids(values: object) -> tuple[str, ...]:
    if not isinstance(values, tuple) or not values:
        raise ValueError("evidence_ids must be a nonempty tuple")
    normalized = tuple(sorted(_text(value, "evidence_id", identifier=True) for value in values))
    if len(set(normalized)) != len(normalized):
        raise ValueError("evidence_ids must be unique")
    return normalized


def _decimal_text(value: Decimal) -> str:
    return format(value, "f")


def _hash(document: dict[str, object]) -> str:
    encoded = json.dumps(
        document, ensure_ascii=False, allow_nan=False,
        sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class PromotionGateCriteria:
    minimum_trades: int
    minimum_oos_periods: int
    minimum_walk_forward_consistency: Decimal
    maximum_drawdown: Decimal
    minimum_profit_factor: Decimal
    minimum_expectancy: Decimal
    minimum_stress_survival: Decimal
    minimum_parameter_stability: Decimal
    hash: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "minimum_trades", _positive_int(
            self.minimum_trades, "minimum_trades"
        ))
        object.__setattr__(self, "minimum_oos_periods", _positive_int(
            self.minimum_oos_periods, "minimum_oos_periods"
        ))
        object.__setattr__(self, "minimum_walk_forward_consistency", _ratio(
            self.minimum_walk_forward_consistency, "minimum_walk_forward_consistency"
        ))
        object.__setattr__(self, "maximum_drawdown", _decimal(
            self.maximum_drawdown, "maximum_drawdown", nonnegative=True
        ))
        object.__setattr__(self, "minimum_profit_factor", _decimal(
            self.minimum_profit_factor, "minimum_profit_factor", nonnegative=True
        ))
        object.__setattr__(self, "minimum_expectancy", _decimal(
            self.minimum_expectancy, "minimum_expectancy"
        ))
        object.__setattr__(self, "minimum_stress_survival", _ratio(
            self.minimum_stress_survival, "minimum_stress_survival"
        ))
        object.__setattr__(self, "minimum_parameter_stability", _ratio(
            self.minimum_parameter_stability, "minimum_parameter_stability"
        ))
        object.__setattr__(self, "hash", _hash(self.document(include_hash=False)))

    def document(self, *, include_hash: bool = True) -> dict[str, object]:
        document: dict[str, object] = {
            "maximum_drawdown": _decimal_text(self.maximum_drawdown),
            "minimum_expectancy": _decimal_text(self.minimum_expectancy),
            "minimum_oos_periods": self.minimum_oos_periods,
            "minimum_parameter_stability": _decimal_text(self.minimum_parameter_stability),
            "minimum_profit_factor": _decimal_text(self.minimum_profit_factor),
            "minimum_stress_survival": _decimal_text(self.minimum_stress_survival),
            "minimum_trades": self.minimum_trades,
            "minimum_walk_forward_consistency": _decimal_text(
                self.minimum_walk_forward_consistency
            ),
        }
        if include_hash:
            document["hash"] = self.hash
        return document


@dataclass(frozen=True)
class PromotionEvidence:
    strategy_id: str
    challenger_record_hash: str
    parameter_set_sha256: str
    evidence_ids: tuple[str, ...]
    trade_count: int
    oos_periods: int
    walk_forward_consistency: Decimal
    max_drawdown: Decimal
    profit_factor: Decimal
    expectancy: Decimal
    stress_survival: Decimal
    parameter_stability: Decimal
    hash: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "strategy_id", _text(
            self.strategy_id, "strategy_id", identifier=True
        ))
        object.__setattr__(self, "challenger_record_hash", _sha256(
            self.challenger_record_hash, "challenger_record_hash"
        ))
        object.__setattr__(self, "parameter_set_sha256", _sha256(
            self.parameter_set_sha256, "parameter_set_sha256"
        ))
        object.__setattr__(self, "evidence_ids", _evidence_ids(self.evidence_ids))
        object.__setattr__(self, "trade_count", _positive_int(
            self.trade_count, "trade_count", allow_zero=True
        ))
        object.__setattr__(self, "oos_periods", _positive_int(
            self.oos_periods, "oos_periods", allow_zero=True
        ))
        object.__setattr__(self, "walk_forward_consistency", _ratio(
            self.walk_forward_consistency, "walk_forward_consistency"
        ))
        object.__setattr__(self, "max_drawdown", _decimal(
            self.max_drawdown, "max_drawdown", nonnegative=True
        ))
        object.__setattr__(self, "profit_factor", _decimal(
            self.profit_factor, "profit_factor", nonnegative=True
        ))
        object.__setattr__(self, "expectancy", _decimal(
            self.expectancy, "expectancy"
        ))
        object.__setattr__(self, "stress_survival", _ratio(
            self.stress_survival, "stress_survival"
        ))
        object.__setattr__(self, "parameter_stability", _ratio(
            self.parameter_stability, "parameter_stability"
        ))
        object.__setattr__(self, "hash", _hash(self.document(include_hash=False)))

    def document(self, *, include_hash: bool = True) -> dict[str, object]:
        document: dict[str, object] = {
            "challenger_record_hash": self.challenger_record_hash,
            "evidence_ids": list(self.evidence_ids),
            "expectancy": _decimal_text(self.expectancy),
            "max_drawdown": _decimal_text(self.max_drawdown),
            "oos_periods": self.oos_periods,
            "parameter_set_sha256": self.parameter_set_sha256,
            "parameter_stability": _decimal_text(self.parameter_stability),
            "profit_factor": _decimal_text(self.profit_factor),
            "strategy_id": self.strategy_id,
            "stress_survival": _decimal_text(self.stress_survival),
            "trade_count": self.trade_count,
            "walk_forward_consistency": _decimal_text(self.walk_forward_consistency),
        }
        if include_hash:
            document["hash"] = self.hash
        return document


@dataclass(frozen=True)
class PromotionCriterionResult:
    name: str
    actual: str
    comparator: str
    required: str
    passed: bool
    blocking_reason: str | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _text(self.name, "name", identifier=True))
        if self.comparator not in {">=", "<="}:
            raise ValueError("comparator must be >= or <=")
        object.__setattr__(self, "actual", _text(self.actual, "actual"))
        object.__setattr__(self, "required", _text(self.required, "required"))
        if type(self.passed) is not bool:
            raise ValueError("passed must be bool")
        if self.passed:
            if self.blocking_reason is not None:
                raise ValueError("passed criterion cannot have a blocking reason")
        else:
            object.__setattr__(self, "blocking_reason", _text(
                self.blocking_reason, "blocking_reason", identifier=True
            ))

    def document(self) -> dict[str, object]:
        return {
            "actual": self.actual,
            "blocking_reason": self.blocking_reason,
            "comparator": self.comparator,
            "name": self.name,
            "passed": self.passed,
            "required": self.required,
        }


@dataclass(frozen=True)
class PromotionGateResult:
    outcome: PromotionGateOutcome
    candidate_strategy_id: str
    candidate_record_hash: str
    criteria_hash: str
    evidence_hash: str
    criterion_results: tuple[PromotionCriterionResult, ...]
    blocking_reasons: tuple[str, ...]
    evaluated_at: datetime
    recommended_status: ChallengerStatus | None
    evaluation_id: str = field(init=False)
    human_operator_approval_required: bool = field(default=True, init=False)
    registry_mutation_authorized: bool = field(default=False, init=False)
    execution_authorized: bool = field(default=False, init=False)
    paper_execution_authorized: bool = field(default=False, init=False)
    live_execution_authorized: bool = field(default=False, init=False)
    production_assignment_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.outcome, PromotionGateOutcome):
            raise ValueError("outcome must be PromotionGateOutcome")
        object.__setattr__(self, "candidate_strategy_id", _text(
            self.candidate_strategy_id, "candidate_strategy_id", identifier=True
        ))
        object.__setattr__(self, "candidate_record_hash", _sha256(
            self.candidate_record_hash, "candidate_record_hash"
        ))
        object.__setattr__(self, "criteria_hash", _sha256(
            self.criteria_hash, "criteria_hash"
        ))
        object.__setattr__(self, "evidence_hash", _sha256(
            self.evidence_hash, "evidence_hash"
        ))
        if not isinstance(self.criterion_results, tuple) or len(self.criterion_results) != 8:
            raise ValueError("criterion_results must contain all eight promotion criteria")
        if any(not isinstance(item, PromotionCriterionResult) for item in self.criterion_results):
            raise ValueError("criterion_results contains an invalid item")
        if tuple(item.name for item in self.criterion_results) != _CRITERION_NAMES:
            raise ValueError("criterion_results must use the canonical criterion order")
        expected_reasons = tuple(sorted(
            item.blocking_reason
            for item in self.criterion_results
            if item.blocking_reason is not None
        ))
        if self.blocking_reasons != expected_reasons:
            raise ValueError("blocking_reasons must exactly match failed criteria")
        if self.outcome is PromotionGateOutcome.PASSED:
            if self.blocking_reasons:
                raise ValueError("passed promotion gate cannot have blocking reasons")
            if self.recommended_status is not ChallengerStatus.PROMOTION_CANDIDATE:
                raise ValueError("passed gate can only recommend PROMOTION_CANDIDATE")
        else:
            if not self.blocking_reasons:
                raise ValueError("failed promotion gate requires blocking reasons")
            if self.recommended_status is not None:
                raise ValueError("failed promotion gate cannot recommend a status")
        object.__setattr__(self, "evaluated_at", _utc(self.evaluated_at, "evaluated_at"))
        object.__setattr__(self, "evaluation_id", _hash(self.document(
            include_evaluation_id=False
        )))

    def document(self, *, include_evaluation_id: bool = True) -> dict[str, object]:
        document: dict[str, object] = {
            "blocking_reasons": list(self.blocking_reasons),
            "candidate_record_hash": self.candidate_record_hash,
            "candidate_strategy_id": self.candidate_strategy_id,
            "criteria_hash": self.criteria_hash,
            "criterion_results": [item.document() for item in self.criterion_results],
            "evaluated_at": _utc_text(self.evaluated_at),
            "evidence_hash": self.evidence_hash,
            "human_operator_approval_required": True,
            "outcome": self.outcome.value,
            "recommended_status": (
                None if self.recommended_status is None else self.recommended_status.value
            ),
        }
        if include_evaluation_id:
            document["evaluation_id"] = self.evaluation_id
        return document


class StrategyPromotionGate:
    """Evaluates eligibility and never mutates strategy or execution state."""

    human_operator_approval_required = True
    registry_mutation_authorized = False
    execution_authorized = False
    paper_execution_authorized = False
    live_execution_authorized = False
    production_assignment_authorized = False

    def evaluate(
        self,
        *,
        candidate: StrategyChallengerRecord,
        evidence: PromotionEvidence,
        criteria: PromotionGateCriteria,
        evaluated_at: datetime,
    ) -> PromotionGateResult:
        if not isinstance(candidate, StrategyChallengerRecord):
            raise ValueError("candidate must be StrategyChallengerRecord")
        if not isinstance(evidence, PromotionEvidence):
            raise ValueError("evidence must be PromotionEvidence")
        if not isinstance(criteria, PromotionGateCriteria):
            raise ValueError("criteria must be PromotionGateCriteria")
        if candidate.status is not ChallengerStatus.PAPER_CHALLENGER:
            raise PromotionGateError("candidate must be PAPER_CHALLENGER")
        if evidence.strategy_id != candidate.strategy_id:
            raise PromotionGateError("promotion evidence strategy does not match candidate")
        if evidence.challenger_record_hash != candidate.hash:
            raise PromotionGateError("promotion evidence does not bind current candidate revision")
        if evidence.parameter_set_sha256 != candidate.parameters.sha256:
            raise PromotionGateError("promotion evidence parameter set does not match candidate")
        if evidence.evidence_ids != candidate.evidence_ids:
            raise PromotionGateError(
                "promotion evidence must exactly match the candidate registered evidence set"
            )

        checks = (
            self._minimum("minimum_trades", evidence.trade_count, criteria.minimum_trades),
            self._minimum("minimum_oos_periods", evidence.oos_periods, criteria.minimum_oos_periods),
            self._minimum(
                "walk_forward_consistency",
                evidence.walk_forward_consistency,
                criteria.minimum_walk_forward_consistency,
            ),
            self._maximum("max_drawdown", evidence.max_drawdown, criteria.maximum_drawdown),
            self._minimum("profit_factor", evidence.profit_factor, criteria.minimum_profit_factor),
            self._minimum("expectancy", evidence.expectancy, criteria.minimum_expectancy),
            self._minimum(
                "stress_survival", evidence.stress_survival, criteria.minimum_stress_survival
            ),
            self._minimum(
                "parameter_stability",
                evidence.parameter_stability,
                criteria.minimum_parameter_stability,
            ),
        )
        reasons = tuple(sorted(
            item.blocking_reason for item in checks if item.blocking_reason is not None
        ))
        passed = not reasons
        return PromotionGateResult(
            outcome=PromotionGateOutcome.PASSED if passed else PromotionGateOutcome.FAILED,
            candidate_strategy_id=candidate.strategy_id,
            candidate_record_hash=candidate.hash,
            criteria_hash=criteria.hash,
            evidence_hash=evidence.hash,
            criterion_results=checks,
            blocking_reasons=reasons,
            evaluated_at=evaluated_at,
            recommended_status=(
                ChallengerStatus.PROMOTION_CANDIDATE if passed else None
            ),
        )

    @staticmethod
    def _minimum(name: str, actual: int | Decimal, required: int | Decimal):
        passed = actual >= required
        return PromotionCriterionResult(
            name=name,
            actual=str(actual),
            comparator=">=",
            required=str(required),
            passed=passed,
            blocking_reason=None if passed else f"{name.upper()}_BELOW_MINIMUM",
        )

    @staticmethod
    def _maximum(name: str, actual: Decimal, required: Decimal):
        passed = actual <= required
        return PromotionCriterionResult(
            name=name,
            actual=str(actual),
            comparator="<=",
            required=str(required),
            passed=passed,
            blocking_reason=None if passed else f"{name.upper()}_ABOVE_MAXIMUM",
        )
