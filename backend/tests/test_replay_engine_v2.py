from datetime import datetime

from backend.backtesting.replay_engine_v2 import ReplayEngineV2
from backend.models.candle import Candle


def build_candle(index: int) -> Candle:
    return Candle(
        symbol="NQ",
        timeframe="1m",
        open=100 + index,
        high=101 + index,
        low=99 + index,
        close=100.5 + index,
        volume=1000,
        timestamp=datetime(2026, 1, 1, 0, index),
    )


def test_load_and_iteration():
    engine = ReplayEngineV2()

    candles = [
        build_candle(0),
        build_candle(1),
        build_candle(2),
    ]

    engine.load(candles)

    assert engine.total() == 3
    assert engine.position() == 0
    assert engine.current() == candles[0]

    assert engine.has_next()

    engine.next()

    assert engine.position() == 1
    assert engine.current() == candles[1]

    engine.next()

    assert engine.position() == 2
    assert engine.current() == candles[2]
    assert not engine.has_next()


def test_reset():
    engine = ReplayEngineV2()

    candles = [
        build_candle(0),
        build_candle(1),
    ]

    engine.load(candles)

    engine.next()

    engine.reset()

    assert engine.position() == 0
    assert engine.current() == candles[0]


def test_empty_load():
    engine = ReplayEngineV2()

    try:
        engine.load([])
        assert False
    except ValueError:
        pass
