from dataclasses import asdict
from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest

from backend.backtesting.csv_candle_loader_v2 import CsvCandleLoaderV2
from backend.backtesting.historical_data_loader import HistoricalDataLoader
from backend.backtesting.parameter_backtest_engine_factory_v2 import ParameterBacktestEngineFactoryV2
from backend.market_structure.market_structure_engine_v2 import MarketStructureEngineV2
from backend.market_structure.market_structure_engine_v3 import MarketStructureEngineV3
from backend.models.candle import Candle
from backend.smart_money.liquidity_engine_v2 import LiquidityEngineV2
from backend.smart_money.smart_money_engine_v2 import SmartMoneyEngineV2
from backend.strategies.parameterized_strategy_runner_v2 import (
    ParameterizedStrategyRunnerV2, _estimate_market_regime,
)
from backend.tests.test_production_certified_outcome_v17 import api_settings
from backend.trend.trend_context_engine_v2 import TrendContextEngineV2


def fvg_prices(direction="BULLISH"):
    pairs = [(100.0, 95.0), (104.0, 99.0), (108.0, 102.0)]
    if direction == "BEARISH":
        pairs.reverse()
    return {
        f"{name}_{side}": value
        for name, pair in zip(("first", "second", "third"), pairs)
        for side, value in zip(("high", "low"), pair)
    }


@pytest.mark.parametrize("direction", ["BULLISH", "BEARISH"])
@pytest.mark.parametrize("flat_mask", range(1, 8))
def test_any_flat_pattern_candle_returns_no_fvg_without_mutation(direction, flat_mask):
    prices = fvg_prices(direction)
    for index, name in enumerate(("first", "second", "third")):
        if flat_mask & (1 << index):
            midpoint = (prices[f"{name}_high"] + prices[f"{name}_low"]) / 2
            prices[f"{name}_high"] = prices[f"{name}_low"] = midpoint
    original = dict(prices)
    engine = SmartMoneyEngineV2()
    result = engine.detect_fvg(**prices)
    assert result == engine.detect_fvg(**prices)
    assert prices == original
    assert result["fvg"] is False
    assert result["direction"] == "NONE"
    assert result["gap_low"] is result["gap_high"] is None
    assert result["gap_size"] == 0.0
    assert {key: result[key] for key in prices} == prices


@pytest.mark.parametrize("direction", ["BULLISH", "BEARISH"])
def test_normal_fvg_retains_exact_gap(direction):
    result = SmartMoneyEngineV2().detect_fvg(**fvg_prices(direction))
    assert result["fvg"] is True
    assert result["direction"] == direction
    assert (result["gap_low"], result["gap_high"], result["gap_size"]) == (100, 102, 2)


@pytest.mark.parametrize("position", range(3))
def test_flat_neighbour_does_not_mask_inverted_range(position):
    prices = fvg_prices()
    names = ("first", "second", "third")
    flat = names[(position + 1) % 3]
    prices[f"{flat}_high"] = prices[f"{flat}_low"]
    invalid = names[position]
    prices[f"{invalid}_high"] = prices[f"{invalid}_low"] - 1
    with pytest.raises(ValueError, match=f"{invalid}_high"):
        SmartMoneyEngineV2().detect_fvg(**prices)


@pytest.mark.parametrize("field", list(fvg_prices()))
@pytest.mark.parametrize("value", [0.0, -1.0, float("nan"), float("inf"), float("-inf")])
def test_invalid_prices_still_fail_even_with_flat_neighbour(field, value):
    prices = fvg_prices()
    prices["second_high"] = prices["second_low"]
    prices[field] = value
    with pytest.raises(ValueError, match=field):
        SmartMoneyEngineV2().detect_fvg(**prices)


def write_flat_csv(path, count=20):
    rows = ["symbol,timeframe,timestamp,open,high,low,close,volume"]
    for index in range(count):
        timestamp = datetime(2026, 8, 17, 4, 29) + timedelta(minutes=index)
        rows.append(f"NQ,1m,{timestamp.isoformat()},30242.5,30242.5,30242.5,30242.5,1")
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def test_flat_data_survives_both_loaders_and_complete_production_replay(tmp_path, api_settings):
    path = tmp_path / "flat.csv"
    write_flat_csv(path)
    original_csv = path.read_bytes()
    data = CsvCandleLoaderV2(csv_path=path, symbol="NQ", timeframe="1m").load()
    assert data == HistoricalDataLoader().load_csv(path)
    assert len(data) == 20
    assert all(isinstance(c, Candle) and c.open == c.high == c.low == c.close for c in data)
    original_candles = [asdict(c) for c in data]
    engine = ParameterBacktestEngineFactoryV2(csv_path=None, settings=api_settings)(
        {"ema": 10, "stop_loss": 30, "take_profit": 60},
    )
    session = engine.pipeline.pipeline.backtest_session_v2
    detector = session.strategy_runner_v2.smart_money_engine
    detector.detect_fvg = Mock(wraps=detector.detect_fvg)
    result = engine.run_single_pass(data)
    assert detector.detect_fvg.call_count > 0
    assert result.total_candles == len(session.candle_history) == len(data)
    assert [c["timestamp"] for c in session.candle_history] == [c.timestamp for c in data]
    assert session.backtest_runner_v2.replay_engine_v2.position() == len(data) - 1
    assert [asdict(c) for c in data] == original_candles
    assert path.read_bytes() == original_csv
    assert result.trades == []


@pytest.mark.parametrize("ohlc", ["100,99,100,100", "101,100,100,100", "100,100,100,101"])
def test_canonical_csv_validation_still_rejects_malformed_ohlc(tmp_path, ohlc):
    path = tmp_path / "invalid.csv"
    path.write_text(
        "symbol,timeframe,timestamp,open,high,low,close,volume\n"
        f"NQ,1m,2026-08-17T04:29:00,{ohlc},1\n", encoding="utf-8",
    )
    with pytest.raises(ValueError, match="OHLC"):
        CsvCandleLoaderV2(csv_path=path, symbol="NQ", timeframe="1m").load()


def test_other_backtest_detectors_accept_flat_history_without_mutation():
    data = [
        Candle("NQ", "1m", 100, 100, 100, 100, 1,
               datetime(2026, 1, 1) + timedelta(minutes=i))
        for i in range(20)
    ]
    original = [asdict(c) for c in data]
    v2 = MarketStructureEngineV2().analyze(data)
    v3 = MarketStructureEngineV3().analyze(data)
    assert not v2.bos and not v2.choch and v2.trend == "RANGE"
    assert not v3.bos and not v3.choch and v3.structure == "NO_SWINGS"
    trend = TrendContextEngineV2().analyze(data, data)
    assert not trend.aligned and trend.allowed_direction == "NONE"
    liquidity = LiquidityEngineV2()
    assert liquidity.analyze(data) == "NO"
    assert liquidity.sweep_index is None
    runner = ParameterizedStrategyRunnerV2(ema=10, stop_loss=30, take_profit=60)
    regime, score, tradable = _estimate_market_regime(runner.market_regime_engine, original)
    assert regime["regime"] == "NO_TRADE"
    assert not tradable and score == 0
    assert [asdict(c) for c in data] == original
