from backend.backtesting.backtest_execution_simulator_v2 import (
    BacktestExecutionSimulatorV2,
)


class BacktestExecutionAdapterV2:

    def __init__(
        self,
        future_candles=None,
    ):
        self.simulator = (
            BacktestExecutionSimulatorV2()
        )

        self.future_candles = (
            future_candles
            if future_candles is not None
            else []
        )


    def execute(
        self,
        *,
        symbol,
        direction,
        entry,
        stop_loss,
        take_profit,
        contracts,
        risk_amount,
        approved,
    ):

        if not approved:
            return None


        simulated_trade = (
            self.simulator.simulate(
                symbol=symbol,
                direction=direction,
                entry=entry,
                stop_loss=stop_loss,
                take_profit=take_profit,
                contracts=contracts,
                risk_amount=risk_amount,
                candles=self.future_candles,
            )
        )


        simulated_trade.active_position_id = (
            f"{symbol}-{direction}-{entry}"
        )


        return simulated_trade
