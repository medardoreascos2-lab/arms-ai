from pathlib import Path
from typing import Any

from backend.backtesting.historical_data_loader import (
    HistoricalDataLoader,
)
from backend.backtesting.statistics_engine import StatisticsEngine
from backend.backtesting.metrics_engine import MetricsEngine
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

        self.metrics_engine = MetricsEngine()
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
                    "future_candles": candles[end_index:],
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

            self.metrics_engine.register_trade(
                simulated_trade.pnl
            )

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

        result.metrics = (
            self.metrics_engine.report()
        )

        return result

    def run_single_pass(
        self,
        candles: list[Candle],
        *,
        minimum_candles: int | None = None,
    ) -> BacktestResult:
        """Explicit production replay; legacy run() keeps its growing windows.

        Plan authorization counters retain their existing meaning and are not
        lifecycle acceptance counts. The session's simulated trade stream remains
        the result/equity PnL source; completed lifecycle trades are separate.
        Each output is accounted once, after chronological strategy processing,
        so future-resolved PnL cannot affect earlier decisions or risk state.
        Construct a fresh pipeline/session for every dataset run.
        """
        from backend.backtesting.backtest_engine_pipeline_adapter_v2 import (
            BacktestEnginePipelineAdapterV2,
        )

        if not isinstance(self.pipeline, BacktestEnginePipelineAdapterV2):
            raise TypeError("run_single_pass requires BacktestEnginePipelineAdapterV2.")
        if minimum_candles is None:
            effective_minimum_candles = (
                self.minimum_candles
            )
        else:
            if (
                not isinstance(
                    minimum_candles,
                    int,
                )
                or isinstance(
                    minimum_candles,
                    bool,
                )
            ):
                raise TypeError(
                    "minimum_candles debe ser int."
                )

            if minimum_candles <= 0:
                raise ValueError(
                    "minimum_candles debe ser "
                    "mayor que cero."
                )

            effective_minimum_candles = max(
                self.minimum_candles,
                minimum_candles,
            )

        context = self.pipeline.run_single_pass(
            candles=candles,
            minimum_candles=(
                effective_minimum_candles
            ),
        )
        result = BacktestResult(
            total_candles=len(candles), initial_balance=self.initial_balance,
        )
        for plan in context["trade_plans"]:
            result.total_signals += 1
            if plan.authorized:
                result.authorized_trades += 1
            else:
                result.blocked_signals += 1

        pnls = []
        metrics = MetricsEngine()
        for trade in context["simulated_trades"]:
            if trade is None:
                continue
            result.trades.append(trade)
            pnl = float(trade.pnl)
            pnls.append(pnl)
            metrics.register_trade(pnl)
            result.equity_curve.add_trade(pnl=pnl)
        result.statistics = self.statistics_engine.calculate(pnls)
        result.metrics = metrics.report()
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
