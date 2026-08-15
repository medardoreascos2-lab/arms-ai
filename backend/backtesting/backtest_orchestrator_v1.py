from backend.backtesting.backtest_execution_simulator_v2 import (
    BacktestExecutionSimulatorV2,
)

from backend.backtesting.strategy_backtest_engine_v2 import (
    StrategyBacktestEngineV2,
)


class BacktestOrchestratorV1:
    """
    Coordina ejecución completa
    de backtesting ARMS AI.
    """

    def __init__(
        self,
        pipeline,
    ):

        self.pipeline = pipeline

        self.simulator = (
            BacktestExecutionSimulatorV2()
        )

        self.engine = (
            StrategyBacktestEngineV2()
        )


    def run(
        self,
        candles,
    ):

        context = (
            self.pipeline.run(
                initial_context={
                    "backtest_candles": candles[:-1],
                    "backtest_candle": candles[-2],
                    "backtest_next_candle": candles[-1],
                }
            )
        )


        council = (
            context["council_result"]
        )


        if council.action == "NO_TRADE":
            return {
                "action": "NO_TRADE",
                "metrics": (
                    self.engine.calculate_metrics()
                ),
            }


        plan = (
            context["trade_plan"]
        )


        trade = (
            self.simulator.simulate(
                direction=plan.decision,
                entry=plan.entry_price,
                stop_loss=plan.stop_loss,
                take_profit=plan.take_profit,
                candles=candles[-5:],
            )
        )


        self.engine.add_trade(
            trade
        )


        return {
            "action": council.action,
            "trade": trade,
            "metrics": (
                self.engine.calculate_metrics()
            ),
        }
