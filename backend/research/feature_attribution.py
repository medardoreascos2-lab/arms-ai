"""Deterministic, research-only feature attribution without causal claims."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, localcontext
import hashlib
import json
import re


FEATURE_NAMES = (
    "ATR", "BOS", "CHOCH", "EMA", "FVG", "HTF",
    "L1", "RSI", "liquidity", "news", "trend",
)
ATTRIBUTION_INTERPRETATION = "DESCRIPTIVE_PREDICTIVE_ASSOCIATION_NOT_CAUSATION"
ATTRIBUTION_LIMITATIONS = (
    "ABLATION_AND_PERMUTATION_PREDICTIONS_ARE_SOURCE_PROVIDED",
    "ASSOCIATIONS_MAY_REFLECT_CONFOUNDING_OR_FEATURE_INTERACTIONS",
    "IN_SAMPLE_RESULTS_DO_NOT_ESTABLISH_OUT_OF_SAMPLE_PERFORMANCE",
    "NO_CAUSAL_EFFECT_IS_ESTIMATED",
)
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


def _decimal(value: object, name: str) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite Decimal")
    try:
        number = value if isinstance(value, Decimal) else Decimal(str(value))
    except Exception as exc:
        raise ValueError(f"{name} must be a finite Decimal") from exc
    if not number.is_finite():
        raise ValueError(f"{name} must be a finite Decimal")
    return number


def _utc(value: datetime, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _utc_text(value: datetime) -> str:
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _hash(value: object) -> str:
    return hashlib.sha256(json.dumps(
        value, ensure_ascii=False, allow_nan=False,
        sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()


def _feature_pairs(value: object, name: str) -> tuple[tuple[str, Decimal], ...]:
    if not isinstance(value, tuple):
        raise ValueError(f"{name} must be a tuple")
    pairs: list[tuple[str, Decimal]] = []
    for item in value:
        if not isinstance(item, tuple) or len(item) != 2:
            raise ValueError(f"{name} contains an invalid item")
        pairs.append((item[0], _decimal(item[1], f"{name}_value")))
    normalized = tuple(sorted(pairs))
    if tuple(pairs) != normalized or tuple(item[0] for item in normalized) != FEATURE_NAMES:
        raise ValueError(f"{name} must contain every supported feature exactly once in sorted order")
    return normalized


def _pairs_document(value: tuple[tuple[str, Decimal], ...]) -> dict[str, str]:
    return {name: format(number, "f") for name, number in value}


@dataclass(frozen=True)
class FeatureAttributionObservation:
    observation_id: str
    timestamp: datetime
    observed_net_r: Decimal
    baseline_prediction: Decimal
    feature_values: tuple[tuple[str, Decimal], ...]
    ablated_predictions: tuple[tuple[str, Decimal], ...]
    permuted_predictions: tuple[tuple[str, Decimal], ...]

    def __post_init__(self) -> None:
        if not isinstance(self.observation_id, str) or _ID.fullmatch(self.observation_id) is None:
            raise ValueError("observation_id is invalid")
        object.__setattr__(self, "timestamp", _utc(self.timestamp, "timestamp"))
        object.__setattr__(self, "observed_net_r", _decimal(self.observed_net_r, "observed_net_r"))
        object.__setattr__(self, "baseline_prediction", _decimal(self.baseline_prediction, "baseline_prediction"))
        for name in ("feature_values", "ablated_predictions", "permuted_predictions"):
            object.__setattr__(self, name, _feature_pairs(getattr(self, name), name))

    def document(self) -> dict[str, object]:
        return {
            "ablated_predictions": _pairs_document(self.ablated_predictions),
            "baseline_prediction": format(self.baseline_prediction, "f"),
            "feature_values": _pairs_document(self.feature_values),
            "observation_id": self.observation_id,
            "observed_net_r": format(self.observed_net_r, "f"),
            "permuted_predictions": _pairs_document(self.permuted_predictions),
            "timestamp": _utc_text(self.timestamp),
        }


@dataclass(frozen=True)
class FeatureAttributionMetric:
    feature: str
    sample_count: int
    baseline_mean_absolute_error: Decimal
    ablation_mean_absolute_error: Decimal
    ablation_error_delta: Decimal
    permutation_mean_absolute_error: Decimal
    permutation_error_delta: Decimal
    correlation_with_net_r: Decimal | None
    high_value_mean_net_r: Decimal | None
    low_value_mean_net_r: Decimal | None
    stratified_mean_difference: Decimal | None
    interpretation: str = field(default=ATTRIBUTION_INTERPRETATION, init=False)

    def __post_init__(self) -> None:
        if self.feature not in FEATURE_NAMES:
            raise ValueError("feature is unsupported")
        if type(self.sample_count) is not int or self.sample_count < 2:
            raise ValueError("sample_count must be at least two")
        for name in (
            "baseline_mean_absolute_error", "ablation_mean_absolute_error",
            "ablation_error_delta", "permutation_mean_absolute_error",
            "permutation_error_delta",
        ):
            object.__setattr__(self, name, _decimal(getattr(self, name), name))
        optional = (
            "correlation_with_net_r", "high_value_mean_net_r",
            "low_value_mean_net_r", "stratified_mean_difference",
        )
        for name in optional:
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _decimal(value, name))
        if self.ablation_error_delta != self.ablation_mean_absolute_error - self.baseline_mean_absolute_error:
            raise ValueError("ablation_error_delta does not reconcile")
        if self.permutation_error_delta != self.permutation_mean_absolute_error - self.baseline_mean_absolute_error:
            raise ValueError("permutation_error_delta does not reconcile")
        if (self.high_value_mean_net_r is None) != (self.low_value_mean_net_r is None):
            raise ValueError("stratified means must both be present or absent")
        expected = None if self.high_value_mean_net_r is None else self.high_value_mean_net_r - self.low_value_mean_net_r
        if self.stratified_mean_difference != expected:
            raise ValueError("stratified_mean_difference does not reconcile")

    def document(self) -> dict[str, object]:
        def optional(value: Decimal | None) -> str | None:
            return None if value is None else format(value, "f")
        return {
            "ablation_error_delta": format(self.ablation_error_delta, "f"),
            "ablation_mean_absolute_error": format(self.ablation_mean_absolute_error, "f"),
            "baseline_mean_absolute_error": format(self.baseline_mean_absolute_error, "f"),
            "correlation_with_net_r": optional(self.correlation_with_net_r),
            "feature": self.feature,
            "high_value_mean_net_r": optional(self.high_value_mean_net_r),
            "interpretation": self.interpretation,
            "low_value_mean_net_r": optional(self.low_value_mean_net_r),
            "permutation_error_delta": format(self.permutation_error_delta, "f"),
            "permutation_mean_absolute_error": format(self.permutation_mean_absolute_error, "f"),
            "sample_count": self.sample_count,
            "stratified_mean_difference": optional(self.stratified_mean_difference),
        }


@dataclass(frozen=True)
class FeatureAttributionResult:
    generated_at: datetime
    source_hash: str
    observation_count: int
    metrics: tuple[FeatureAttributionMetric, ...]
    result_hash: str = field(init=False)
    limitations: tuple[str, ...] = field(default=ATTRIBUTION_LIMITATIONS, init=False)
    causal_claim_authorized: bool = field(default=False, init=False)
    strategy_rewrite_authorized: bool = field(default=False, init=False)
    execution_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "generated_at", _utc(self.generated_at, "generated_at"))
        if not isinstance(self.source_hash, str) or re.fullmatch(r"[0-9a-f]{64}", self.source_hash) is None:
            raise ValueError("source_hash must be lowercase SHA-256")
        if type(self.observation_count) is not int or self.observation_count < 2:
            raise ValueError("observation_count must be at least two")
        if not isinstance(self.metrics, tuple) or tuple(item.feature for item in self.metrics) != FEATURE_NAMES:
            raise ValueError("metrics must cover every supported feature in sorted order")
        if any(item.sample_count != self.observation_count for item in self.metrics):
            raise ValueError("metric sample counts do not reconcile")
        object.__setattr__(self, "result_hash", _hash(self.document(include_hash=False)))

    def document(self, *, include_hash: bool = True) -> dict[str, object]:
        value: dict[str, object] = {
            "causal_claim_authorized": self.causal_claim_authorized,
            "execution_authorized": self.execution_authorized,
            "generated_at": _utc_text(self.generated_at),
            "limitations": list(self.limitations),
            "metrics": [item.document() for item in self.metrics],
            "observation_count": self.observation_count,
            "source_hash": self.source_hash,
            "strategy_rewrite_authorized": self.strategy_rewrite_authorized,
        }
        if include_hash:
            value["result_hash"] = self.result_hash
        return value


class StrategyFeatureAttribution:
    """Compare source-provided baseline, ablation, and permutation predictions."""

    def analyze(
        self,
        observations: tuple[FeatureAttributionObservation, ...],
        *,
        generated_at: datetime,
    ) -> FeatureAttributionResult:
        if not isinstance(observations, tuple) or len(observations) < 2:
            raise ValueError("observations must be a tuple with at least two items")
        if any(not isinstance(item, FeatureAttributionObservation) for item in observations):
            raise ValueError("observations contains an invalid item")
        ordered = tuple(sorted(observations, key=lambda item: item.observation_id))
        if len({item.observation_id for item in ordered}) != len(ordered):
            raise ValueError("observation_id values must be unique")

        baseline_mae = self._mae(ordered, "baseline_prediction")
        metrics = tuple(self._metric(name, ordered, baseline_mae) for name in FEATURE_NAMES)
        return FeatureAttributionResult(
            generated_at=generated_at,
            source_hash=_hash([item.document() for item in ordered]),
            observation_count=len(ordered),
            metrics=metrics,
        )

    @staticmethod
    def _mae(observations: tuple[FeatureAttributionObservation, ...], attribute: str) -> Decimal:
        return sum((abs(getattr(item, attribute) - item.observed_net_r) for item in observations), Decimal("0")) / Decimal(len(observations))

    def _metric(
        self,
        feature: str,
        observations: tuple[FeatureAttributionObservation, ...],
        baseline_mae: Decimal,
    ) -> FeatureAttributionMetric:
        values = [dict(item.feature_values)[feature] for item in observations]
        outcomes = [item.observed_net_r for item in observations]
        ablation_mae = self._feature_mae(observations, feature, "ablated_predictions")
        permutation_mae = self._feature_mae(observations, feature, "permuted_predictions")
        low_mean, high_mean = self._stratified_means(values, outcomes)
        return FeatureAttributionMetric(
            feature=feature,
            sample_count=len(observations),
            baseline_mean_absolute_error=baseline_mae,
            ablation_mean_absolute_error=ablation_mae,
            ablation_error_delta=ablation_mae - baseline_mae,
            permutation_mean_absolute_error=permutation_mae,
            permutation_error_delta=permutation_mae - baseline_mae,
            correlation_with_net_r=self._correlation(values, outcomes),
            high_value_mean_net_r=high_mean,
            low_value_mean_net_r=low_mean,
            stratified_mean_difference=None if high_mean is None else high_mean - low_mean,
        )

    @staticmethod
    def _feature_mae(
        observations: tuple[FeatureAttributionObservation, ...],
        feature: str,
        attribute: str,
    ) -> Decimal:
        total = sum((
            abs(dict(getattr(item, attribute))[feature] - item.observed_net_r)
            for item in observations
        ), Decimal("0"))
        return total / Decimal(len(observations))

    @staticmethod
    def _stratified_means(
        values: list[Decimal], outcomes: list[Decimal],
    ) -> tuple[Decimal | None, Decimal | None]:
        ordered = sorted(values)
        median = ordered[len(ordered) // 2]
        low = [outcome for value, outcome in zip(values, outcomes) if value < median]
        high = [outcome for value, outcome in zip(values, outcomes) if value >= median]
        if not low or not high:
            return None, None
        return sum(low, Decimal("0")) / Decimal(len(low)), sum(high, Decimal("0")) / Decimal(len(high))

    @staticmethod
    def _correlation(values: list[Decimal], outcomes: list[Decimal]) -> Decimal | None:
        count = Decimal(len(values))
        mean_x = sum(values, Decimal("0")) / count
        mean_y = sum(outcomes, Decimal("0")) / count
        numerator = sum(((x - mean_x) * (y - mean_y) for x, y in zip(values, outcomes)), Decimal("0"))
        sum_x = sum(((x - mean_x) ** 2 for x in values), Decimal("0"))
        sum_y = sum(((y - mean_y) ** 2 for y in outcomes), Decimal("0"))
        if sum_x == 0 or sum_y == 0:
            return None
        with localcontext() as context:
            context.prec = 28
            return numerator / (sum_x * sum_y).sqrt()
