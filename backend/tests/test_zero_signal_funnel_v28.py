"""Observer regressions use synthetic test candles, never the ignored dataset."""

from dataclasses import asdict

from backend.backtesting.csv_candle_loader_v2 import CsvCandleLoaderV2
from backend.backtesting.parameter_backtest_engine_factory_v2 import ParameterBacktestEngineFactoryV2
from backend.tests.diagnose_zero_signal_funnel_v28 import collect
from backend.tests.test_production_certified_outcome_v17 import (
    api_settings,
    _write_relative_volatility_ten_trade_csv,
)


def test_observer_preserves_real_decisions_and_execution(tmp_path, api_settings):
    path = tmp_path / "explicit_synthetic.csv"
    _write_relative_volatility_ten_trade_csv(path, opportunities=2)
    candles = CsvCandleLoaderV2(csv_path=path, symbol="NQ", timeframe="1m").load()
    factory = ParameterBacktestEngineFactoryV2(csv_path=None, settings=api_settings)
    parameters = {"ema": 10, "stop_loss": 30, "take_profit": 60}
    observed, plain = factory(parameters), factory(parameters)
    strategy = observed.pipeline.pipeline.backtest_session_v2.strategy_runner_v2
    original_run = strategy.run
    report, rows, result = collect(observed, candles)
    reference = plain.run_single_pass(candles)
    observed_session = observed.pipeline.pipeline.backtest_session_v2
    plain_session = plain.pipeline.pipeline.backtest_session_v2
    assert strategy.run == original_run
    assert observed_session.decisions == plain_session.decisions
    assert asdict(result.statistics) == asdict(reference.statistics)
    assert [trade.pnl for trade in result.trades] == [trade.pnl for trade in reference.trades]
    assert result.equity_curve.balance == reference.equity_curve.balance
    # V29R: this short fixture has fewer than ten completed 1h bars. Observer
    # transparency includes the canonical warm-up HOLD and zero side effects.
    assert report["accepted"] == report["simulated_trades"] == 0
    assert report["final_counts"] == {"HOLD": len(candles)-5}
    assert report["warmup_candles"] == 4
    assert len(rows) == len(candles) - 5
    assert report["htf_alias_count"] == 0
    assert all(row["htf_1h_length"] < 10 for row in rows)
    assert report["detector_not_evaluated"] >= 5
    assert all(row["history_length"] <= 50 for row in rows)
    assert all("analyze" not in row.get("liquidity", {}) for row in rows)
    assert [row["index"] for row in rows] == list(range(5, len(candles)))
    # Every rejected/non-A+ observed quality result is counted honestly.
    for row in rows:
        if "quality" in row and row["confluence"]["grade"] != "A+":
            assert row["quality"]["score"] <= 60
            assert row["quality"]["approved"] is False
