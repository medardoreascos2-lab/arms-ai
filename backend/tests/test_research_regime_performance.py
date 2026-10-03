from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from backend.research.regime_performance import (
    MarketRegimeLabel,
    PerformanceBucket,
    RegimePerformanceAnalytics,
    RegimePerformanceObservation,
    RegimePerformanceResult,
    TradingSessionLabel,
)


NOW = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)


def observation(
    observation_id: str,
    net_r: str,
    *,
    regime: MarketRegimeLabel | None,
    session: TradingSessionLabel | None,
) -> RegimePerformanceObservation:
    value = Decimal(net_r)
    return RegimePerformanceObservation(
        observation_id=observation_id,
        timestamp=NOW,
        net_r=value,
        profitable=value > 0,
        regime=regime,
        session=session,
    )


def test_all_supported_regimes_and_sessions_are_aggregated_from_source_labels() -> None:
    observations = (
        observation("one", "1.5", regime=MarketRegimeLabel.BULLISH, session=TradingSessionLabel.ASIA),
        observation("two", "-1", regime=MarketRegimeLabel.BEARISH, session=TradingSessionLabel.LONDON),
        observation("three", "0", regime=MarketRegimeLabel.RANGE, session=TradingSessionLabel.NEW_YORK),
        observation("four", ".5", regime=MarketRegimeLabel.LOW_VOLATILITY, session=TradingSessionLabel.ASIA),
        observation("five", "-.25", regime=MarketRegimeLabel.NO_TRADE, session=TradingSessionLabel.LONDON),
    )

    result = RegimePerformanceAnalytics().analyze(observations, generated_at=NOW)

    assert {item.label for item in result.regime_buckets} == {item.value for item in MarketRegimeLabel}
    assert {item.label for item in result.session_buckets} == {item.value for item in TradingSessionLabel}
    assert result.observation_count == 5
    assert result.unlabeled_regime_count == 0
    assert result.unlabeled_session_count == 0


def test_missing_labels_remain_unlabeled_and_are_never_inferred() -> None:
    result = RegimePerformanceAnalytics().analyze(
        (observation("missing", "1", regime=None, session=None),),
        generated_at=NOW,
    )

    assert result.regime_buckets == ()
    assert result.session_buckets == ()
    assert result.unlabeled_regime_count == 1
    assert result.unlabeled_session_count == 1
    assert result.inferred_labels_used is False


def test_sparse_source_emits_only_labels_that_are_present() -> None:
    result = RegimePerformanceAnalytics().analyze(
        (
            observation("a", "1", regime=MarketRegimeLabel.RANGE, session=None),
            observation("b", "-1", regime=None, session=TradingSessionLabel.NEW_YORK),
        ),
        generated_at=NOW,
    )

    assert [item.label for item in result.regime_buckets] == ["RANGE"]
    assert [item.label for item in result.session_buckets] == ["NEW_YORK"]


def test_aggregation_reconciles_profit_counts_totals_and_averages() -> None:
    result = RegimePerformanceAnalytics().analyze(
        (
            observation("a", "2", regime=MarketRegimeLabel.BULLISH, session=TradingSessionLabel.ASIA),
            observation("b", "-1", regime=MarketRegimeLabel.BULLISH, session=TradingSessionLabel.ASIA),
            observation("c", "0", regime=MarketRegimeLabel.BULLISH, session=TradingSessionLabel.ASIA),
        ),
        generated_at=NOW,
    )

    bucket = result.regime_buckets[0]
    assert bucket.observation_count == 3
    assert bucket.profitable_count == 1
    assert bucket.total_net_r == Decimal("1")
    assert bucket.average_net_r == Decimal("1") / Decimal("3")


def test_analysis_is_deterministic_regardless_of_input_order() -> None:
    first = observation("a", "1", regime=MarketRegimeLabel.BULLISH, session=TradingSessionLabel.ASIA)
    second = observation("b", "-1", regime=MarketRegimeLabel.BEARISH, session=TradingSessionLabel.LONDON)
    engine = RegimePerformanceAnalytics()

    forward = engine.analyze((first, second), generated_at=NOW)
    reverse = engine.analyze((second, first), generated_at=NOW)

    assert forward.source_hash == reverse.source_hash
    assert forward.result_hash == reverse.result_hash
    assert forward.document() == reverse.document()


@pytest.mark.parametrize("field,value", [("regime", "BULLISH"), ("session", "ASIA")])
def test_plain_text_labels_are_rejected_instead_of_inferred(field: str, value: str) -> None:
    kwargs = {"regime": None, "session": None, field: value}
    with pytest.raises(ValueError, match=field):
        RegimePerformanceObservation(
            observation_id="bad-label",
            timestamp=NOW,
            net_r=Decimal("1"),
            profitable=True,
            **kwargs,
        )


def test_profitability_must_reconcile_with_net_r() -> None:
    with pytest.raises(ValueError, match="profitable must equal"):
        RegimePerformanceObservation("bad", NOW, Decimal("-1"), True)


@pytest.mark.parametrize("value", [Decimal("NaN"), Decimal("Infinity")])
def test_nonfinite_results_are_rejected(value: Decimal) -> None:
    with pytest.raises(ValueError, match="finite Decimal"):
        RegimePerformanceObservation("bad", NOW, value, False)


def test_naive_timestamps_are_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        RegimePerformanceObservation("bad", datetime(2026, 10, 3), Decimal("0"), False)


def test_duplicate_observation_ids_are_rejected() -> None:
    item = observation("same", "1", regime=None, session=None)
    with pytest.raises(ValueError, match="must be unique"):
        RegimePerformanceAnalytics().analyze((item, item), generated_at=NOW)


def test_empty_input_is_rejected() -> None:
    with pytest.raises(ValueError, match="nonempty tuple"):
        RegimePerformanceAnalytics().analyze((), generated_at=NOW)


def test_forged_bucket_and_result_reconciliation_are_rejected() -> None:
    with pytest.raises(ValueError, match="average_net_r"):
        PerformanceBucket("BULLISH", 2, 1, Decimal("1"), Decimal("1"))

    bucket = PerformanceBucket("BULLISH", 1, 1, Decimal("1"), Decimal("1"))
    with pytest.raises(ValueError, match="regime counts"):
        RegimePerformanceResult(
            generated_at=NOW,
            source_hash="a" * 64,
            regime_buckets=(bucket,),
            session_buckets=(),
            unlabeled_regime_count=0,
            unlabeled_session_count=2,
            observation_count=2,
        )


def test_result_has_no_execution_or_strategy_rewrite_authority() -> None:
    result = RegimePerformanceAnalytics().analyze(
        (observation("safe", "1", regime=None, session=None),),
        generated_at=NOW,
    )
    source = Path(__file__).parents[1] / "research" / "regime_performance.py"
    text = source.read_text(encoding="utf-8")

    assert result.execution_authorized is False
    assert result.strategy_rewrite_authorized is False
    assert "EnterLong" not in text
    assert "EnterShort" not in text
    assert "submit_order" not in text


def test_label_enums_are_exactly_the_roadmap_contract() -> None:
    assert {item.value for item in MarketRegimeLabel} == {
        "BULLISH", "BEARISH", "RANGE", "LOW_VOLATILITY", "NO_TRADE"
    }
    assert {item.value for item in TradingSessionLabel} == {"ASIA", "LONDON", "NEW_YORK"}
