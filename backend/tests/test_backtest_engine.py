from datetime import datetime, timedelta

import pytest

from backend.backtesting.backtest_engine import BacktestEngine
from backend.models.candle import Candle


class DummyPipeline:
    def __init__(self):
        self.calls = 0

    def run(self, initial_context=None):
        self.calls += 1

        authorized = self.calls % 2 == 0

        return {
            "trade_plan": type(
                "TradePlanStub",
                (),
                {
                    "authorized": authorized,
                    "decision": (
                        "BUY"
                        if authorized
                        else "NO_TRADE"
                    ),
                },
            )(),
            "simulated_trade": None,
        }


class DummyPipelineWithPnls:
    def __init__(
        self,
        pnls: list[float],
    ) -> None:
        self.pnls = pnls
        self.calls = 0

    def run(self, initial_context=None):
        pnl = self.pnls[self.calls]
        self.calls += 1

        return {
            "trade_plan": type(
                "TradePlanStub",
                (),
                {
                    "authorized": True,
                    "decision": "BUY",
                },
            )(),
            "simulated_trade": type(
                "SimulatedTradeStub",
                (),
                {
                    "pnl": pnl,
                },
            )(),
        }


def build_candles(total: int) -> list[Candle]:
    candles = []
    base_timestamp = datetime(
        2026,
        1,
        1,
        9,
        30,
    )

    for index in range(total):
        price = 100.0 + index

        candles.append(
            Candle(
                symbol="TEST",
                timeframe="1m",
                open=price,
                high=price + 1.0,
                low=price - 1.0,
                close=price + 0.5,
                volume=1000 + index,
                timestamp=(
                    base_timestamp
                    + timedelta(minutes=index)
                ),
            )
        )

    return candles


def test_backtest_engine_processes_all_candles():
    pipeline = DummyPipeline()
    engine = BacktestEngine(pipeline=pipeline)

    result = engine.run(
        candles=build_candles(10),
    )

    assert pipeline.calls == 10
    assert result.total_candles == 10
    assert result.total_signals == 10


def test_backtest_engine_counts_authorized_trades():
    pipeline = DummyPipeline()
    engine = BacktestEngine(pipeline=pipeline)

    result = engine.run(
        candles=build_candles(6),
    )

    assert result.authorized_trades == 3
    assert result.blocked_signals == 3


def test_backtest_engine_calculates_statistics_from_pnls():
    pipeline = DummyPipelineWithPnls(
        pnls=[
            100.0,
            -50.0,
            150.0,
            -25.0,
        ]
    )

    engine = BacktestEngine(
        pipeline=pipeline,
    )

    result = engine.run(
        candles=build_candles(4),
    )

    statistics = result.statistics

    assert result.authorized_trades == 4
    assert statistics.total_trades == 4
    assert statistics.winning_trades == 2
    assert statistics.losing_trades == 2
    assert statistics.net_profit == 175.0
    assert statistics.win_rate == 50.0
    assert statistics.profit_factor == pytest.approx(
        250.0 / 75.0,
        rel=1e-2,
    )
    assert statistics.expectancy == 43.75


def test_backtest_engine_ignores_missing_simulated_trade():
    pipeline = DummyPipeline()
    engine = BacktestEngine(pipeline=pipeline)

    result = engine.run(
        candles=build_candles(4),
    )

    assert result.authorized_trades == 2
    assert result.statistics.total_trades == 0
    assert result.statistics.net_profit == 0.0


def test_backtest_engine_rejects_empty_candle_list():
    pipeline = DummyPipeline()
    engine = BacktestEngine(pipeline=pipeline)

    with pytest.raises(
        ValueError,
        match="candles",
    ):
        engine.run(candles=[])
