from datetime import datetime

import pytest

from backend.backtesting.backtest_runner_v2 import (
    BacktestRunnerV2,
)
from backend.models.candle import Candle


class FakeReplayEngine:

    def __init__(self, candles):
        self.candles = candles
        self.index = 0

    def current(self):
        if not self.candles:
            return None

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
            "symbol": candle.symbol,
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


def test_runner_notifies_observer_for_every_candle():

    candles = [
        build_candle(0),
        build_candle(1),
        build_candle(2),
    ]

    observed = []

    def observer(candle, publish_result):
        observed.append(
            (
                candle,
                publish_result,
            )
        )

    runner = BacktestRunnerV2(
        replay_engine_v2=FakeReplayEngine(candles),
        replay_market_data_bridge_v2=FakeBridge(),
    )

    processed = runner.run(
        on_candle=observer,
    )

    assert processed == 3
    assert len(observed) == 3

    assert observed[0][0] is candles[0]
    assert observed[1][0] is candles[1]
    assert observed[2][0] is candles[2]

    assert observed[0][1]["processed"] is True
    assert observed[0][1]["symbol"] == "NQ"


def test_runner_continues_working_without_observer():

    candles = [
        build_candle(0),
        build_candle(1),
    ]

    runner = BacktestRunnerV2(
        replay_engine_v2=FakeReplayEngine(candles),
        replay_market_data_bridge_v2=FakeBridge(),
    )

    assert runner.run() == 2


def test_runner_rejects_invalid_observer():

    runner = BacktestRunnerV2(
        replay_engine_v2=FakeReplayEngine(
            [
                build_candle(0),
            ]
        ),
        replay_market_data_bridge_v2=FakeBridge(),
    )

    with pytest.raises(
        TypeError,
        match="on_candle",
    ):
        runner.run(
            on_candle="INVALID",
        )


def test_runner_does_not_notify_observer_when_replay_is_empty():

    observed = []

    runner = BacktestRunnerV2(
        replay_engine_v2=FakeReplayEngine([]),
        replay_market_data_bridge_v2=FakeBridge(),
    )

    processed = runner.run(
        on_candle=lambda candle, result: observed.append(
            (
                candle,
                result,
            )
        ),
    )

    assert processed == 0
    assert observed == []
