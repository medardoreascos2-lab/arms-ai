"""Fail-closed admission guards against research overfitting and leakage."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import re


_HASH = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class OverfittingGuardPolicy:
    minimum_training_samples: int
    minimum_validation_samples: int
    maximum_hypotheses: int
    maximum_parameter_combinations: int
    maximum_complexity_score: Decimal

    def __post_init__(self) -> None:
        for name in ("minimum_training_samples", "minimum_validation_samples", "maximum_hypotheses", "maximum_parameter_combinations"):
            value = getattr(self, name)
            if type(value) is not int or value < 1:
                raise ValueError(f"{name} must be positive")
        score = Decimal(str(self.maximum_complexity_score))
        if not score.is_finite() or score < 0:
            raise ValueError("maximum_complexity_score must be finite and nonnegative")
        object.__setattr__(self, "maximum_complexity_score", score)


@dataclass(frozen=True)
class ResearchSearchDeclaration:
    training_samples: int
    validation_samples: int
    hypotheses_tested_before: int
    hypotheses_requested: int
    parameter_combinations_requested: int
    complexity_score: Decimal
    training_dataset_hash: str
    validation_dataset_hash: str
    holdout_dataset_hash: str
    holdout_opened: bool
    feature_window_end: datetime
    outcome_window_start: datetime

    def __post_init__(self) -> None:
        for name in ("training_samples", "validation_samples", "hypotheses_tested_before", "hypotheses_requested", "parameter_combinations_requested"):
            value = getattr(self, name)
            minimum = 0 if name == "hypotheses_tested_before" else 1
            if type(value) is not int or value < minimum:
                raise ValueError(f"{name} is invalid")
        score = Decimal(str(self.complexity_score))
        if not score.is_finite() or score < 0:
            raise ValueError("complexity_score must be finite and nonnegative")
        object.__setattr__(self, "complexity_score", score)
        for name in ("training_dataset_hash", "validation_dataset_hash", "holdout_dataset_hash"):
            if not isinstance(getattr(self, name), str) or _HASH.fullmatch(getattr(self, name)) is None:
                raise ValueError(f"{name} must be lowercase SHA-256")
        if len({self.training_dataset_hash, self.validation_dataset_hash, self.holdout_dataset_hash}) != 3:
            raise ValueError("training, validation, and holdout datasets must be distinct")
        if type(self.holdout_opened) is not bool:
            raise ValueError("holdout_opened must be bool")
        for name in ("feature_window_end", "outcome_window_start"):
            value = getattr(self, name)
            if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{name} must be timezone-aware")
            object.__setattr__(self, name, value.astimezone(timezone.utc))

    def document(self) -> dict[str, object]:
        return {name: (format(value, "f") if isinstance(value, Decimal) else value.isoformat() if isinstance(value, datetime) else value)
                for name, value in self.__dict__.items()}


@dataclass(frozen=True)
class OverfittingGuardResult:
    accepted: bool
    blocking_reasons: tuple[str, ...]
    declaration_hash: str
    complexity_penalty: Decimal
    multiple_testing_count: int
    holdout_preserved: bool
    data_leakage_detected: bool
    execution_authorized: bool = field(default=False, init=False)
    optimization_authorized: bool = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "optimization_authorized", self.accepted)
        if self.accepted != (not self.blocking_reasons):
            raise ValueError("accepted does not reconcile")


class ResearchOverfittingGuard:
    def evaluate(self, declaration: ResearchSearchDeclaration, policy: OverfittingGuardPolicy) -> OverfittingGuardResult:
        if not isinstance(declaration, ResearchSearchDeclaration) or not isinstance(policy, OverfittingGuardPolicy):
            raise ValueError("declaration and policy are required")
        reasons: list[str] = []
        if declaration.training_samples < policy.minimum_training_samples:
            reasons.append("INSUFFICIENT_TRAINING_SAMPLES")
        if declaration.validation_samples < policy.minimum_validation_samples:
            reasons.append("INSUFFICIENT_VALIDATION_SAMPLES")
        tests = declaration.hypotheses_tested_before + declaration.hypotheses_requested
        if tests > policy.maximum_hypotheses:
            reasons.append("MULTIPLE_TESTING_BUDGET_EXCEEDED")
        if declaration.parameter_combinations_requested > policy.maximum_parameter_combinations:
            reasons.append("PARAMETER_SEARCH_BUDGET_EXCEEDED")
        if declaration.holdout_opened:
            reasons.append("HOLDOUT_ALREADY_OPENED")
        leakage = declaration.feature_window_end >= declaration.outcome_window_start
        if leakage:
            reasons.append("TEMPORAL_DATA_LEAKAGE")
        penalty = max(Decimal("0"), declaration.complexity_score - policy.maximum_complexity_score)
        if penalty > 0:
            reasons.append("CANDIDATE_COMPLEXITY_LIMIT_EXCEEDED")
        encoded = json.dumps(declaration.document(), sort_keys=True, separators=(",", ":")).encode()
        return OverfittingGuardResult(not reasons, tuple(sorted(reasons)), hashlib.sha256(encoded).hexdigest(),
                                      penalty, tests, not declaration.holdout_opened, leakage)
