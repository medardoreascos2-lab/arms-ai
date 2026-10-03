from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from backend.research.feature_attribution import (
    ATTRIBUTION_INTERPRETATION,
    ATTRIBUTION_LIMITATIONS,
    FEATURE_NAMES,
    FeatureAttributionMetric,
    FeatureAttributionObservation,
    StrategyFeatureAttribution,
)


NOW = datetime(2026, 10, 3, 13, tzinfo=timezone.utc)


def pairs(value: str) -> tuple[tuple[str, Decimal], ...]:
    return tuple((name, Decimal(value)) for name in FEATURE_NAMES)


def observation(identifier: str, outcome: str, feature_value: str, alternate: str) -> FeatureAttributionObservation:
    return FeatureAttributionObservation(
        observation_id=identifier,
        timestamp=NOW,
        observed_net_r=Decimal(outcome),
        baseline_prediction=Decimal(outcome),
        feature_values=pairs(feature_value),
        ablated_predictions=pairs("0"),
        permuted_predictions=pairs(alternate),
    )


def sample() -> tuple[FeatureAttributionObservation, ...]:
    return (
        observation("one", "-1", "-1", "1"),
        observation("two", "0", "0", "0"),
        observation("three", "1", "1", "-1"),
    )


def test_all_roadmap_features_have_ablation_permutation_and_stratified_metrics() -> None:
    result = StrategyFeatureAttribution().analyze(sample(), generated_at=NOW)

    assert tuple(item.feature for item in result.metrics) == FEATURE_NAMES
    bos = next(item for item in result.metrics if item.feature == "BOS")
    assert bos.baseline_mean_absolute_error == 0
    assert bos.ablation_mean_absolute_error == Decimal("2") / Decimal("3")
    assert bos.ablation_error_delta == Decimal("2") / Decimal("3")
    assert bos.permutation_mean_absolute_error == Decimal("4") / Decimal("3")
    assert bos.permutation_error_delta == Decimal("4") / Decimal("3")
    assert bos.correlation_with_net_r == Decimal("1")
    assert bos.low_value_mean_net_r == Decimal("-1")
    assert bos.high_value_mean_net_r == Decimal(".5")
    assert bos.stratified_mean_difference == Decimal("1.5")


def test_results_are_explicitly_noncausal_and_document_limitations() -> None:
    result = StrategyFeatureAttribution().analyze(sample(), generated_at=NOW)

    assert result.causal_claim_authorized is False
    assert result.strategy_rewrite_authorized is False
    assert result.execution_authorized is False
    assert result.limitations == ATTRIBUTION_LIMITATIONS
    assert all(item.interpretation == ATTRIBUTION_INTERPRETATION for item in result.metrics)


def test_constant_feature_has_no_correlation_or_stratified_claim() -> None:
    observations = (
        observation("one", "-1", "1", "0"),
        observation("two", "1", "1", "0"),
    )
    result = StrategyFeatureAttribution().analyze(observations, generated_at=NOW)

    metric = result.metrics[0]
    assert metric.correlation_with_net_r is None
    assert metric.low_value_mean_net_r is None
    assert metric.high_value_mean_net_r is None
    assert metric.stratified_mean_difference is None


def test_analysis_is_deterministic_regardless_of_source_order() -> None:
    observations = sample()
    engine = StrategyFeatureAttribution()
    first = engine.analyze(observations, generated_at=NOW)
    second = engine.analyze(tuple(reversed(observations)), generated_at=NOW)

    assert first.source_hash == second.source_hash
    assert first.result_hash == second.result_hash
    assert first.document() == second.document()


def test_duplicate_ids_and_insufficient_samples_fail_closed() -> None:
    item = sample()[0]
    with pytest.raises(ValueError, match="at least two"):
        StrategyFeatureAttribution().analyze((item,), generated_at=NOW)
    with pytest.raises(ValueError, match="must be unique"):
        StrategyFeatureAttribution().analyze((item, item), generated_at=NOW)


def test_missing_extra_or_reordered_feature_sets_are_rejected() -> None:
    complete = pairs("1")
    for invalid in (complete[:-1], complete + (("unknown", Decimal("1")),), tuple(reversed(complete))):
        with pytest.raises(ValueError, match="every supported feature"):
            FeatureAttributionObservation("bad", NOW, Decimal("1"), Decimal("1"), invalid, complete, complete)


@pytest.mark.parametrize("field_index", [4, 5, 6])
def test_each_prediction_and_value_map_requires_the_exact_feature_contract(field_index: int) -> None:
    values: list[object] = ["bad", NOW, Decimal("1"), Decimal("1"), pairs("1"), pairs("1"), pairs("1")]
    values[field_index] = pairs("1")[:-1]
    with pytest.raises(ValueError, match="every supported feature"):
        FeatureAttributionObservation(*values)


@pytest.mark.parametrize("value", [Decimal("NaN"), Decimal("Infinity")])
def test_nonfinite_financial_values_are_rejected(value: Decimal) -> None:
    with pytest.raises(ValueError, match="finite Decimal"):
        FeatureAttributionObservation("bad", NOW, value, Decimal("0"), pairs("0"), pairs("0"), pairs("0"))


def test_naive_timestamp_is_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        FeatureAttributionObservation("bad", datetime(2026, 10, 3), Decimal("0"), Decimal("0"), pairs("0"), pairs("0"), pairs("0"))


def test_metric_deltas_cannot_be_forged() -> None:
    with pytest.raises(ValueError, match="ablation_error_delta"):
        FeatureAttributionMetric(
            feature="BOS",
            sample_count=2,
            baseline_mean_absolute_error=Decimal("1"),
            ablation_mean_absolute_error=Decimal("2"),
            ablation_error_delta=Decimal("0"),
            permutation_mean_absolute_error=Decimal("2"),
            permutation_error_delta=Decimal("1"),
            correlation_with_net_r=None,
            high_value_mean_net_r=None,
            low_value_mean_net_r=None,
            stratified_mean_difference=None,
        )


def test_feature_contract_is_exactly_the_requested_set() -> None:
    assert set(FEATURE_NAMES) == {
        "BOS", "CHOCH", "liquidity", "FVG", "EMA", "RSI",
        "ATR", "trend", "HTF", "L1", "news",
    }


def test_module_has_no_execution_or_strategy_mutation_calls() -> None:
    source = Path(__file__).parents[1] / "research" / "feature_attribution.py"
    text = source.read_text(encoding="utf-8")
    assert "EnterLong" not in text
    assert "EnterShort" not in text
    assert "submit_order" not in text
    assert "promote(" not in text
