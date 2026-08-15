from __future__ import annotations

from backend.backtesting.backtest_engine import (
    BacktestEngine,
)

from backend.backtesting.strategy_backtest_factory_v2 import (
    build_strategy_backtest_pipeline,
)

from backend.backtesting.backtest_engine_pipeline_adapter_v2 import (
    BacktestEnginePipelineAdapterV2,
)


class ParameterBacktestEngineFactoryV2:
    """
    Construye motores de backtest para Walk Forward.
    """

    def __init__(
        self,
        *,
        csv_path,
    ) -> None:

        self.csv_path = csv_path

    def __call__(
        self,
        parameters,
    ):

        pipeline = build_strategy_backtest_pipeline(
            parameters,
            csv_path=self.csv_path,
        )

        adapted_pipeline = (
            BacktestEnginePipelineAdapterV2(
                pipeline=pipeline
            )
        )

        return BacktestEngine(
            pipeline=adapted_pipeline,
            minimum_candles=5,
            initial_balance=17000.0,
        )
