from datetime import datetime, timedelta

from backend.backtesting.backtest_engine import BacktestEngine
from backend.models.candle import Candle


class DummyPipeline:
    def __init__(self):
        self.calls = 0

    def run(self, initial_context=None):
        self.calls += 1

        return {
            "trade_plan": type(
                "TradePlanStub",
                (),
                {
                    "authorized": self.calls % 2 == 0,
                    "decision": (
                        "BUY"
                        if self.calls % 2 == 0
                        else "NO_TRADE"
                    ),
                },
            )()
        }


def build_candles(total: int) -> list[Candle]:
    candles = []
    base_timestamp = datetime(2026, 1, 1, 9, 30)

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


def test_backtest_engine_rejects_empty_candle_list():
    pipeline = DummyPipeline()
    engine = BacktestEngine(pipeline=pipeline)

    try:
        engine.run(candles=[])
    except ValueError as error:
        assert "candles" in str(error)
    else:
        raise AssertionError(
            "BacktestEngine debía rechazar una lista vacía."
        )
