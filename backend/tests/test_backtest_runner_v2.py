from datetime import datetime

from backend.backtesting.backtest_runner_v2 import (
    BacktestRunnerV2,
)
from backend.models.candle import Candle


class FakeReplayEngine:

    def __init__(self, candles):
        self.candles = candles
        self.index = 0

    def current(self):
        return self.candles[self.index]

    def has_next(self):
        return self.index < len(self.candles) - 1

    def next(self):
        self.index += 1
        return self.candles[self.index]

    def reset(self):
        self.index = 0


class FakeBridge:

    def __init__(self):
        self.calls = []

    def publish(self, candle):
        self.calls.append(candle)

        return {
            "processed": True,
        }


def build_candle(index):

    return Candle(
        symbol="NQ",
        timeframe="1m",
        open=100 + index,
        high=101 + index,
        low=99 + index,
        close=100.5 + index,
        volume=1000,
        timestamp=datetime(
            2026,
            1,
            1,
            0,
            index,
        ),
    )


def test_runs_complete_replay():

    candles = [
        build_candle(0),
        build_candle(1),
        build_candle(2),
    ]

    runner = BacktestRunnerV2(
        replay_engine_v2=FakeReplayEngine(
            candles,
        ),
        replay_market_data_bridge_v2=FakeBridge(),
    )

    processed = runner.run()

    assert processed == 3


def test_runner_resets_before_running():

    candles = [
        build_candle(0),
        build_candle(1),
    ]

    replay = FakeReplayEngine(
        candles,
    )

    replay.index = 1

    runner = BacktestRunnerV2(
        replay_engine_v2=replay,
        replay_market_data_bridge_v2=FakeBridge(),
    )

    runner.run()

    assert replay.index == 1
