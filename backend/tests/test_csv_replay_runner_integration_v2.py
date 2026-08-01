from datetime import datetime

from backend.backtesting.backtest_runner_v2 import (
    BacktestRunnerV2,
)
from backend.backtesting.csv_candle_loader_v2 import (
    CsvCandleLoaderV2,
)
from backend.backtesting.replay_engine_v2 import (
    ReplayEngineV2,
)


class FakeReplayMarketDataBridgeV2:

    def __init__(self) -> None:
        self.calls = []

    def publish(self, candle):
        self.calls.append(candle)

        return {
            "processed": True,
            "symbol": candle.symbol,
            "timestamp": candle.timestamp,
        }


def write_csv(tmp_path):

    csv_path = tmp_path / "historical_nq.csv"

    csv_path.write_text(
        (
            "timestamp,open,high,low,close,volume\n"
            "2026-01-01T09:32:00,102,103,101,102.5,1400\n"
            "2026-01-01T09:30:00,100,101,99,100.5,1000\n"
            "2026-01-01T09:31:00,101,102,100,101.5,1200\n"
        ),
        encoding="utf-8",
    )

    return csv_path


def test_csv_candles_are_replayed_in_chronological_order(
    tmp_path,
):

    loader = CsvCandleLoaderV2(
        csv_path=write_csv(tmp_path),
        symbol="NQ",
        timeframe="1m",
    )

    candles = loader.load()

    replay_engine = ReplayEngineV2()
    replay_engine.load(candles)

    bridge = FakeReplayMarketDataBridgeV2()

    runner = BacktestRunnerV2(
        replay_engine_v2=replay_engine,
        replay_market_data_bridge_v2=bridge,
    )

    processed = runner.run()

    assert processed == 3
    assert len(bridge.calls) == 3

    assert [
        candle.timestamp
        for candle in bridge.calls
    ] == [
        datetime(2026, 1, 1, 9, 30),
        datetime(2026, 1, 1, 9, 31),
        datetime(2026, 1, 1, 9, 32),
    ]

    assert [
        candle.close
        for candle in bridge.calls
    ] == [
        100.5,
        101.5,
        102.5,
    ]

    assert all(
        candle.symbol == "NQ"
        for candle in bridge.calls
    )

    assert all(
        candle.timeframe == "1m"
        for candle in bridge.calls
    )


def test_replay_engine_finishes_at_last_csv_candle(
    tmp_path,
):

    loader = CsvCandleLoaderV2(
        csv_path=write_csv(tmp_path),
        symbol="NQ",
        timeframe="1m",
    )

    replay_engine = ReplayEngineV2()
    replay_engine.load(
        loader.load()
    )

    runner = BacktestRunnerV2(
        replay_engine_v2=replay_engine,
        replay_market_data_bridge_v2=(
            FakeReplayMarketDataBridgeV2()
        ),
    )

    processed = runner.run()

    assert processed == 3
    assert replay_engine.total() == 3
    assert replay_engine.position() == 2
    assert replay_engine.has_next() is False

    assert (
        replay_engine.current().timestamp
        == datetime(2026, 1, 1, 9, 32)
    )
