from backend.backtesting.backtest_execution_simulator_v2 import (
    BacktestExecutionSimulatorV2,
)


class Candle:
    def __init__(
        self,
        high,
        low,
        close,
    ):
        self.high = high
        self.low = low
        self.close = close


def test_buy_win():

    simulator = BacktestExecutionSimulatorV2()

    candles = [
        Candle(
            high=21100,
            low=21050,
            close=21100,
        )
    ]

    result = simulator.simulate(
        direction="BUY",
        entry=21000,
        stop_loss=20950,
        take_profit=21100,
        candles=candles,
    )

    assert result["result"] == "WIN"
    assert result["rr"] == 2.0


def test_sell_win():

    simulator = BacktestExecutionSimulatorV2()

    candles = [
        Candle(
            high=21000,
            low=20900,
            close=20900,
        )
    ]

    result = simulator.simulate(
        direction="SELL",
        entry=21000,
        stop_loss=21050,
        take_profit=20900,
        candles=candles,
    )

    assert result["result"] == "WIN"
    assert result["rr"] == 2.0
