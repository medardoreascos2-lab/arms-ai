from pathlib import Path
from typing import Any

from backend.backtesting.historical_data_loader import (
    HistoricalDataLoader,
)
from backend.backtesting.statistics_engine import StatisticsEngine
from backend.models.backtest_result import BacktestResult
from backend.models.candle import Candle


class BacktestEngine:
    """
    Ejecuta una pipeline sobre velas históricas y acumula
    señales, operaciones y métricas de rendimiento.
    """

    def __init__(
        self,
        pipeline: Any,
        statistics_engine: StatisticsEngine | None = None,
        historical_data_loader: Any | None = None,
    ) -> None:
        self.pipeline = pipeline
        self.statistics_engine = (
            statistics_engine or StatisticsEngine()
        )
        self.historical_data_loader = (
            historical_data_loader or HistoricalDataLoader()
        )

    def run(
        self,
        candles: list[Candle],
    ) -> BacktestResult:
        if not candles:
            raise ValueError(
                "BacktestEngine requiere una lista de candles."
            )

        result = BacktestResult(
            total_candles=len(candles),
        )

        pnls: list[float] = []

        for candle in candles:
            pipeline_context = self.pipeline.run(
                initial_context={
                    "backtest_candle": candle,
                }
            )

            trade_plan = pipeline_context.get("trade_plan")

            if trade_plan is None:
                continue

            result.total_signals += 1

            if bool(trade_plan.authorized):
                result.authorized_trades += 1

                simulated_trade = pipeline_context.get(
                    "simulated_trade"
                )

                if simulated_trade is not None:
                    pnl = getattr(
                        simulated_trade,
                        "pnl",
                        None,
                    )

                    if isinstance(pnl, (int, float)):
                        pnls.append(float(pnl))
            else:
                result.blocked_signals += 1

        result.statistics = (
            self.statistics_engine.calculate(pnls)
        )

        return result

    def run_from_csv(
        self,
        file_path: str | Path,
    ) -> BacktestResult:
        candles = self.historical_data_loader.load_csv(
            file_path=file_path,
        )

        return self.run(
            candles=candles,
        )
