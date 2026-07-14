from typing import Any

from backend.models.backtest_result import BacktestResult
from backend.models.candle import Candle


class BacktestEngine:
    """
    Primera versión del motor de backtesting.

    Recorre todas las velas recibidas, ejecuta la pipeline
    una vez por vela y acumula estadísticas básicas.
    """

    def __init__(
        self,
        pipeline: Any,
    ) -> None:
        self.pipeline = pipeline

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
            else:
                result.blocked_signals += 1

        return result
