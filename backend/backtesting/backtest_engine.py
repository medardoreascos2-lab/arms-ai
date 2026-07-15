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
    Ejecuta una pipeline sobre ventanas históricas crecientes,
    usa la vela siguiente para simular operaciones y acumula
    estadísticas, trades y curva de equity.
    """

    def __init__(
        self,
        pipeline: Any,
        statistics_engine: StatisticsEngine | None = None,
        historical_data_loader: Any | None = None,
        minimum_candles: int = 1,
        initial_balance: float = 17000.0,
    ) -> None:
        if minimum_candles <= 0:
            raise ValueError(
                "minimum_candles debe ser mayor que cero."
            )

        if initial_balance <= 0:
            raise ValueError(
                "initial_balance debe ser mayor que cero."
            )

        self.pipeline = pipeline
        self.statistics_engine = (
            statistics_engine or StatisticsEngine()
        )
        self.historical_data_loader = (
            historical_data_loader or HistoricalDataLoader()
        )
        self.minimum_candles = minimum_candles
        self.initial_balance = float(initial_balance)

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
            initial_balance=self.initial_balance,
        )

        pnls: list[float] = []

        if len(candles) <= self.minimum_candles:
            result.statistics = (
                self.statistics_engine.calculate(pnls)
            )
            return result

        for end_index in range(
            self.minimum_candles,
            len(candles),
        ):
            historical_window = candles[:end_index]
            next_candle = candles[end_index]

            pipeline_context = self.pipeline.run(
                initial_context={
                    "backtest_candles": historical_window,
                    "backtest_candle": historical_window[-1],
                    "backtest_next_candle": next_candle,
                }
            )

            trade_plan = pipeline_context.get(
                "trade_plan"
            )

            if trade_plan is None:
                continue

            result.total_signals += 1

            if not bool(trade_plan.authorized):
                result.blocked_signals += 1
                continue

            result.authorized_trades += 1

            simulated_trade = pipeline_context.get(
                "simulated_trade"
            )

            if simulated_trade is None:
                continue

            result.trades.append(simulated_trade)

            pnl = getattr(
                simulated_trade,
                "pnl",
                None,
            )

            if isinstance(pnl, (int, float)):
                pnl_value = float(pnl)
                pnls.append(pnl_value)
                result.equity_curve.add_trade(
                    pnl=pnl_value,
                )

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
