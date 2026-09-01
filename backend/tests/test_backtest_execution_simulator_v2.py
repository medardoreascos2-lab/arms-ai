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
        symbol="NQ",
        direction="BUY",
        entry=21000,
        stop_loss=20950,
        take_profit=21100,
        contracts=1,
        risk_amount=50.0,
        candles=candles,
    )

    assert result.status == "WIN"
    assert "RR=2.0" in result.reasoning


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
        symbol="NQ",
        direction="SELL",
        entry=21000,
        stop_loss=21050,
        take_profit=20900,
        contracts=1,
        risk_amount=50.0,
        candles=candles,
    )

    assert result.status == "WIN"
    assert "RR=2.0" in result.reasoning
