from dataclasses import dataclass

import pytest

from backend.backtesting.walk_forward_engine import (
    WalkForwardEngine,
)
from backend.backtesting.walk_forward_splitter import (
    WalkForwardSplitter,
)


@dataclass
class DummyBacktestResult:
    total_candles: int
    net_profit: float


class DummyBacktestEngine:
    def __init__(
        self,
        expected_training,
        expected_testing,
        net_profit,
    ):
        self.expected_training = expected_training
        self.expected_testing = expected_testing
        self.net_profit = net_profit
        self.calls = 0

    def run_walk_forward_window(
        self,
        training_candles,
        testing_candles,
    ):
        assert training_candles == self.expected_training
        assert testing_candles == self.expected_testing

        self.calls += 1

        return DummyBacktestResult(
            total_candles=len(testing_candles),
            net_profit=self.net_profit,
        )


def test_walk_forward_engine_runs_all_windows():
    candles = list(range(180))

    splitter = WalkForwardSplitter(
        training_size=100,
        testing_size=20,
        step_size=20,
    )

    engines = [
        DummyBacktestEngine(
            expected_training=candles[0:100],
            expected_testing=candles[100:120],
            net_profit=10.0,
        ),
        DummyBacktestEngine(
            expected_training=candles[20:120],
            expected_testing=candles[120:140],
            net_profit=20.0,
        ),
        DummyBacktestEngine(
            expected_training=candles[40:140],
            expected_testing=candles[140:160],
            net_profit=-5.0,
        ),
        DummyBacktestEngine(
            expected_training=candles[60:160],
            expected_testing=candles[160:180],
            net_profit=15.0,
        ),
    ]

    created = []

    def engine_factory(window):
        engine = engines[len(created)]
        created.append(engine)
        return engine

    result = WalkForwardEngine(
        splitter=splitter,
        engine_factory=engine_factory,
    ).run(candles=candles)

    assert len(result.windows) == 4

    assert [
        window_result.result.net_profit
        for window_result in result.windows
    ] == [
        10.0,
        20.0,
        -5.0,
        15.0,
    ]

    assert all(
        engine.calls == 1
        for engine in engines
    )


def test_walk_forward_engine_preserves_window_metadata():
    candles = list(range(80))

    splitter = WalkForwardSplitter(
        training_size=50,
        testing_size=10,
        step_size=10,
    )

    def engine_factory(window):
        return DummyBacktestEngine(
            expected_training=candles[
                window.training_start:
                window.training_end
            ],
            expected_testing=candles[
                window.testing_start:
                window.testing_end
            ],
            net_profit=5.0,
        )

    result = WalkForwardEngine(
        splitter=splitter,
        engine_factory=engine_factory,
    ).run(candles=candles)

    first = result.windows[0]

    assert first.window_number == 1
    assert first.training_start == 0
    assert first.training_end == 50
    assert first.testing_start == 50
    assert first.testing_end == 60


def test_walk_forward_engine_returns_empty_result_when_insufficient_data():
    splitter = WalkForwardSplitter(
        training_size=100,
        testing_size=20,
        step_size=20,
    )

    result = WalkForwardEngine(
        splitter=splitter,
        engine_factory=lambda window: object(),
    ).run(
        candles=list(range(50)),
    )

    assert result.windows == []
    assert result.total_windows == 0


def test_walk_forward_engine_rejects_empty_candles():
    splitter = WalkForwardSplitter(
        training_size=100,
        testing_size=20,
        step_size=20,
    )

    engine = WalkForwardEngine(
        splitter=splitter,
        engine_factory=lambda window: object(),
    )

    with pytest.raises(
        ValueError,
        match="candles",
    ):
        engine.run(candles=[])


def test_walk_forward_engine_requires_callable_factory():
    splitter = WalkForwardSplitter(
        training_size=100,
        testing_size=20,
        step_size=20,
    )

    with pytest.raises(
        TypeError,
        match="engine_factory",
    ):
        WalkForwardEngine(
            splitter=splitter,
            engine_factory=None,
        )
