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

    assert pipeline.calls == 9
    assert result.total_candles == 10
    assert result.total_signals == 9


def test_backtest_engine_counts_authorized_trades():
    pipeline = DummyPipeline()
    engine = BacktestEngine(pipeline=pipeline)

    result = engine.run(
        candles=build_candles(6),
    )

    assert result.authorized_trades == 2
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

    assert result.authorized_trades == 3
    assert statistics.total_trades == 3
    assert statistics.winning_trades == 2
    assert statistics.losing_trades == 1
    assert statistics.net_profit == 200.0
    assert statistics.win_rate == 66.67
    assert statistics.profit_factor == pytest.approx(
        5.0,
        rel=1e-2,
    )
    assert statistics.expectancy == 66.67


def test_backtest_engine_ignores_missing_simulated_trade():
    pipeline = DummyPipeline()
    engine = BacktestEngine(pipeline=pipeline)

    result = engine.run(
        candles=build_candles(4),
    )

    assert result.authorized_trades == 1
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


from backend.backtesting.historical_data_loader import HistoricalDataLoader


def test_backtest_engine_runs_from_csv(tmp_path):
    file_path = tmp_path / "candles.csv"

    file_path.write_text(
        "\n".join(
            [
                (
                    "timestamp,symbol,timeframe,open,high,"
                    "low,close,volume"
                ),
                (
                    "2026-01-01T09:30:00,TEST,1m,"
                    "100.0,101.0,99.5,100.5,1000"
                ),
                (
                    "2026-01-01T09:31:00,TEST,1m,"
                    "100.5,102.0,100.0,101.5,1200"
                ),
            ]
        ),
        encoding="utf-8",
    )

    pipeline = DummyPipeline()
    engine = BacktestEngine(pipeline=pipeline)

    result = engine.run_from_csv(
        file_path=file_path,
    )

    assert result.total_candles == 2
    assert result.total_signals == 1
    assert pipeline.calls == 1


def test_backtest_engine_accepts_custom_loader(tmp_path):
    class DummyLoader:
        def load_csv(self, file_path):
            return build_candles(3)

    pipeline = DummyPipeline()

    engine = BacktestEngine(
        pipeline=pipeline,
        historical_data_loader=DummyLoader(),
    )

    result = engine.run_from_csv(
        file_path=tmp_path / "ignored.csv",
    )

    assert result.total_candles == 3
    assert pipeline.calls == 2


class WindowTrackingPipeline:
    def __init__(self):
        self.windows: list[list[Candle]] = []

    def run(self, initial_context=None):
        window = list(
            initial_context["backtest_candles"]
        )
        self.windows.append(window)

        return {
            "trade_plan": type(
                "TradePlanStub",
                (),
                {
                    "authorized": False,
                    "decision": "NO_TRADE",
                },
            )(),
            "simulated_trade": None,
        }


def test_backtest_engine_sends_growing_windows():
    pipeline = WindowTrackingPipeline()

    engine = BacktestEngine(
        pipeline=pipeline,
        minimum_candles=3,
    )

    candles = build_candles(5)

    result = engine.run(candles=candles)

    assert len(pipeline.windows) == 2

    assert pipeline.windows[0] == candles[:3]
    assert pipeline.windows[1] == candles[:4]

    assert result.total_candles == 5
    assert result.total_signals == 2


def test_backtest_engine_skips_insufficient_history():
    pipeline = WindowTrackingPipeline()

    engine = BacktestEngine(
        pipeline=pipeline,
        minimum_candles=10,
    )

    result = engine.run(
        candles=build_candles(5),
    )

    assert pipeline.windows == []
    assert result.total_candles == 5
    assert result.total_signals == 0


def test_backtest_engine_rejects_invalid_minimum_candles():
    with pytest.raises(
        ValueError,
        match="minimum_candles",
    ):
        BacktestEngine(
            pipeline=WindowTrackingPipeline(),
            minimum_candles=0,
        )


class NextCandleTrackingPipeline:
    def __init__(self):
        self.contexts = []

    def run(self, initial_context=None):
        self.contexts.append(initial_context)

        return {
            "trade_plan": type(
                "TradePlanStub",
                (),
                {
                    "authorized": False,
                    "decision": "NO_TRADE",
                },
            )(),
            "simulated_trade": None,
        }


def test_backtest_engine_passes_next_candle():
    pipeline = NextCandleTrackingPipeline()

    engine = BacktestEngine(
        pipeline=pipeline,
        minimum_candles=3,
    )

    candles = build_candles(5)

    result = engine.run(candles=candles)

    assert len(pipeline.contexts) == 2

    first_context = pipeline.contexts[0]
    second_context = pipeline.contexts[1]

    assert first_context["backtest_candles"] == candles[:3]
    assert first_context["backtest_next_candle"] == candles[3]

    assert second_context["backtest_candles"] == candles[:4]
    assert second_context["backtest_next_candle"] == candles[4]

    assert result.total_signals == 2


def test_backtest_engine_does_not_evaluate_last_candle_without_future_data():
    pipeline = NextCandleTrackingPipeline()

    engine = BacktestEngine(
        pipeline=pipeline,
        minimum_candles=3,
    )

    candles = build_candles(3)

    result = engine.run(candles=candles)

    assert pipeline.contexts == []
    assert result.total_signals == 0


def test_backtest_engine_collects_simulated_trades():
    pipeline = DummyPipelineWithPnls(
        pnls=[
            100.0,
            -50.0,
            25.0,
        ]
    )

    engine = BacktestEngine(
        pipeline=pipeline,
        minimum_candles=1,
    )

    result = engine.run(
        candles=build_candles(4),
    )

    assert len(result.trades) == 3
    assert [trade.pnl for trade in result.trades] == [
        100.0,
        -50.0,
        25.0,
    ]


def test_backtest_result_defaults_to_empty_trade_list():
    from backend.models.backtest_result import BacktestResult

    result = BacktestResult()

    assert result.trades == []


def test_backtest_result_show_includes_trade_count(capsys):
    from backend.models.backtest_result import BacktestResult

    result = BacktestResult(
        total_candles=10,
        total_signals=4,
        authorized_trades=2,
        blocked_signals=2,
    )

    result.show()

    output = capsys.readouterr().out

    assert "Operaciones registradas: 0" in output
