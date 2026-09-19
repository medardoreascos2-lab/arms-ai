"""V30 math, isolation and safety tests; no local market dataset required."""

from dataclasses import asdict
from datetime import datetime, timedelta
import math
from types import SimpleNamespace

import pytest

from backend.intelligence.confluence_engine_v2 import ConfluenceEngineV2
from backend.intelligence.trade_quality_engine_v1 import TradeQualityEngineV1
from backend.tests.research_calibration_v30 import (
    classify_hypothetically, distribution, hypothetical_boundary, metrics,
    percentile, score_analysis, session_for, temporal, trading_date, write_json,
)
from backend.backtesting.parameter_backtest_engine_factory_v2 import ParameterBacktestEngineFactoryV2
from backend.tests.diagnose_zero_signal_funnel_v28 import collect
from backend.tests.test_production_certified_outcome_v17 import api_settings
from backend.tests.test_closed_bar_aggregation_v29r import minutes
from backend.models.candle import Candle


def inputs():
    return dict(trend_score=1, structure_score=.75, liquidity_score=1, fvg_score=1,
                ema_alignment_score=1, market_regime_score=.5, probability_score=1,
                volume_score=1, risk_approved=True, sizing_approved=True, market_tradable=True)


@pytest.mark.parametrize("regime,expected", [(1, 95.59), (.5, 86.76), (0, 77.94)])
def test_formula_component_domain_maxima(regime, expected):
    kwargs = {**inputs(), "market_regime_score": regime}
    assert ConfluenceEngineV2().evaluate(**kwargs)["score"] == expected


@pytest.mark.parametrize("veto", [None, "risk_approved", "sizing_approved", "market_tradable"])
def test_hypothetical_grade_changes_no_scores_or_vetoes(veto):
    real = ConfluenceEngineV2()
    kwargs = inputs()
    if veto:
        kwargs[veto] = False
    original = real.evaluate(**kwargs)
    result = classify_hypothetically(real.evaluate, 85)(**kwargs)
    assert result["grade"] == "A+" and original["grade"] == "A"
    assert {k: v for k, v in result.items() if k != "grade"} == {k: v for k, v in original.items() if k != "grade"}
    assert real.evaluate(**kwargs) == original
    assert result["approved"] is (veto is None)


@pytest.mark.parametrize("threshold", [79.99, 90.01, float("nan")])
def test_hypothetical_boundary_cannot_lower_downstream_floor(threshold):
    with pytest.raises(ValueError):
        classify_hypothetically(ConfluenceEngineV2().evaluate, threshold)


def test_quality_is_discrete_and_choch_is_hard_veto():
    quality = TradeQualityEngineV1()
    structure = SimpleNamespace(structure="HH_HL", bos=True, choch=False)
    trend = SimpleNamespace(aligned=True)
    assert quality.evaluate(confluence=SimpleNamespace(grade="A"), market_structure=structure, trend_context=trend).score == 60
    assert quality.evaluate(confluence=SimpleNamespace(grade="A+"), market_structure=structure, trend_context=trend).score == 100
    structure.choch = True
    result = quality.evaluate(confluence=SimpleNamespace(grade="A+"), market_structure=structure, trend_context=trend)
    assert result.score == 0 and not result.approved


def row(index, minute, direction="LONG", score=80, quality=60, choch=False):
    time = datetime(2026, 8, 3, 9) + timedelta(minutes=minute)
    return dict(index=index, time=time.isoformat()+"-05:00", date="2026-08-03",
                direction=direction, regime="RANGE", score=score, quality=quality,
                choch=choch,
                trend=1, structure=.75, liquidity=.5, fvg=.5, ema_alignment=1, market_regime=.5, volume=.5)


def test_percentiles_histograms_and_fixed_grade_matrix():
    assert percentile([0, 10, 20, 30], 75) == 22.5
    assert percentile([], 50) is None
    rows = [row(1, 1, score=49.99), row(2, 2, score=50), row(3, 3, score=80), row(4, 4, score=90, quality=0, choch=True)]
    report = score_analysis(rows)
    assert sum(distribution(rows)["histogram"].values()) == 4
    assert report["quality_matrix_fixed_A_plus_90"]["80"] == {"85": 0, "80": 0, "75": 0, "70": 0, "60": 1}


def test_clustering_respects_direction_gaps_and_dates():
    rows = [row(1, 1), row(2, 2), row(4, 4), row(5, 5, "SHORT"), row(6, 20, "SHORT")]
    result = temporal(rows)
    assert result["raw"] == 5
    assert result["consecutive_clusters"] == 4
    assert result["episodes"] == 3
    assert result["median_episode_spacing_minutes"] == 9.5
    assert temporal([])["episodes"] == 0
    rows[1]["date"] = "2026-08-04"
    assert temporal(rows)["episodes"] == 5


def test_canonical_date_labels_and_naive_time_rejection():
    assert trading_date("2026-08-03T17:00:00-05:00") == "2026-08-04"
    assert trading_date("2026-08-02T17:00:00-05:00") == "2026-08-03"
    with pytest.raises(ValueError):
        trading_date("2026-08-03T17:00:00")


def test_partition_metrics_start_drawdown_at_zero_and_empty_is_undefined():
    trades = [dict(pnl=p, direction="BUY", regime="RANGE") for p in [-100, 200, -50]]
    result = metrics(trades, 2)
    assert result["net_pnl"] == 50
    assert result["max_drawdown"] == 100
    assert result["profit_factor"] == 200 / 150
    assert result["trades_per_day"] == 1.5
    assert metrics([], 2)["win_rate_percent"] is None


def test_outputs_cannot_overwrite_existing_work(tmp_path):
    path = tmp_path / "evidence.json"
    write_json(path, {"value": 1})
    before = path.read_bytes()
    with pytest.raises(FileExistsError):
        write_json(path, {"value": 2})
    assert path.read_bytes() == before


def test_observer_and_boundary_90_preserve_production_and_restore_methods(api_settings):
    factory = ParameterBacktestEngineFactoryV2(csv_path=None, settings=api_settings)
    parameters = {"ema": 10, "stop_loss": 30, "take_profit": 60}
    observed, plain = factory(parameters), factory(parameters)
    data = minutes(720)
    owner = session_for(observed).strategy_runner_v2.confluence_engine
    original = owner.evaluate
    with hypothetical_boundary(observed, 90):
        _, _, result = collect(observed, data)
    reference = plain.run_single_pass(data)
    assert owner.evaluate == original
    assert session_for(observed).decisions == session_for(plain).decisions
    assert asdict(result.statistics) == asdict(reference.statistics)
    assert result.equity_curve.__dict__ == reference.equity_curve.__dict__
    assert result.trades == reference.trades


def test_hypothetical_boundary_restores_on_exception(api_settings):
    engine = ParameterBacktestEngineFactoryV2(csv_path=None, settings=api_settings)({"ema": 10, "stop_loss": 30, "take_profit": 60})
    owner = session_for(engine).strategy_runner_v2.confluence_engine
    original = owner.evaluate
    with pytest.raises(RuntimeError):
        with hypothetical_boundary(engine, 80):
            raise RuntimeError("research aborted")
    assert owner.evaluate == original


def synthetic_maximum_witness(*, bearish=False, ranging=False, high_volatility=False,
                              low_volatility=False, compressed=False):
    """Construct OHLCV only, not detector outputs; never a recorded NQ sample."""
    data = []
    for i in range(1440):
        close = 20000 + i * .03 + 10 * math.sin(2 * math.pi * i / 240)
        data.append(Candle("NQ", "1m", close, close+4, close-4, close, 1000,
                           datetime(2026, 8, 3) + timedelta(minutes=i)))
    base = data[-51].close
    for j in range(50):
        close = base + j * .3
        wick = 4 + 2 * math.sin(2 * math.pi * j / 6)
        data[-50+j] = Candle("NQ", "1m", close, close+wick, close-wick, close,
                             1000, data[-50+j].timestamp)
    level = data[-8].close - 3
    for j in range(-8, -4):
        data[j].low = level
    data[-4].low = level - .25
    for j, extra in [(-2, 5), (-1, 10)]:
        close = data[j].close + extra
        data[j].open = data[j].close = close
        data[j].high, data[j].low = close+4, close-4
    data[-1].volume = 2000
    if ranging:
        for j in range(40):
            data[-50+j].close += 1.9 if j % 2 else -1.9
    if high_volatility:
        for c in data:
            c.open -= 12000
            c.high -= 12000
            c.low -= 12000
            c.close -= 12000
    if low_volatility:
        for c in data:
            c.open += 40000
            c.high += 40000
            c.low += 40000
            c.close += 40000
    if compressed:
        data[-50].high += 2000
    if bearish:
        for c in data:
            c.open, c.close = 40000-c.open, 40000-c.close
            c.high, c.low = 40000-c.low, 40000-c.high
    last = data[-1]
    data.append(Candle("NQ", "1m", last.close, last.high, last.low, last.close,
                       1000, last.timestamp+timedelta(minutes=1)))
    return data


@pytest.mark.parametrize("options,regime,expected", [
    ({}, "TREND_UP", 95.59),
    ({"bearish": True}, "TREND_DOWN", 95.59),
    ({"ranging": True}, "RANGE", 86.76),
    ({"high_volatility": True}, "HIGH_VOLATILITY", 86.76),
    ({"low_volatility": True}, "LOW_VOLATILITY", 77.94),
    ({"compressed": True}, "NO_TRADE", 77.94),
])
def test_actual_canonical_detectors_attain_theoretical_maxima(
    api_settings, options, regime, expected,
):
    data = synthetic_maximum_witness(**options)
    assert all(c.low <= min(c.open, c.close) <= max(c.open, c.close) <= c.high for c in data)
    engine = ParameterBacktestEngineFactoryV2(csv_path=None, settings=api_settings)({"ema": 10, "stop_loss": 30, "take_profit": 60})
    _, rows, _ = collect(engine, data)
    witness = rows[-1]
    assert witness["regime"]["regime"] == regime
    assert witness["confluence"]["score"] == expected
    assert witness["trend"]["allowed_direction"] == ("SHORT" if options.get("bearish") else "LONG")
    assert witness["structure"]["score"] == 75
    assert witness["htf_alias"] is False
    if regime in {"LOW_VOLATILITY", "NO_TRADE"}:
        assert not witness["confluence"]["approved"]
        assert "market_not_tradable" in witness["confluence"]["blocking_reasons"]
