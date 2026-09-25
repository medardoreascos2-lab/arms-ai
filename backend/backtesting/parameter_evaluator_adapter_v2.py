from __future__ import annotations

from typing import Any

from backend.backtesting.backtest_composite_score_v2 import (
    BacktestCompositeScoreV2,
)
from backend.backtesting.backtest_score_metrics_v2 import (
    build_backtest_score_metrics_v2,
)


class ParameterEvaluatorAdapterV2:
    """
    Adaptador entre WalkForwardOptimizerV2
    y ParameterEvaluator.

    Convierte las métricas del backtest
    en un score institucional.
    """

    def __init__(
        self,
        *,
        evaluator,
    ) -> None:

        self.evaluator = evaluator

        self.score_engine = (
            BacktestCompositeScoreV2(
                minimum_trades=10,
            )
        )


    def evaluate(
        self,
        *,
        testing_items,
        parameters,
        output_directory,
        testing_warmup_size: int = 0,
    ) -> dict[str, Any]:

        result = (
            self.evaluator.evaluate(
                parameters=parameters,
                candles=testing_items,
                warmup_count=(
                    testing_warmup_size
                ),
            )
        )


        statistics = getattr(
            result.result,
            "statistics",
            None,
        )


        score_metrics = (
            build_backtest_score_metrics_v2(
                statistics
            )
        )

        total_trades = int(
            score_metrics[
                "total_trades"
            ]
        )


        score_result = (
            self.score_engine.calculate(
                metrics=score_metrics
            )
        )


        return {
            "score": (
                score_result.score
            ),
            "net_pnl": (
                result.net_profit
            ),
            "win_rate": (
                result.win_rate
            ),
            "maximum_drawdown": (
                result.max_drawdown
            ),
            "profit_factor": (
                result.profit_factor
            ),
            "expectancy": (
                getattr(
                    statistics,
                    "expectancy",
                    0.0,
                )
                if statistics
                else 0.0
            ),
            "total_trades": (
                total_trades
            ),
            "score_components": (
                score_result.components
            ),
        }
