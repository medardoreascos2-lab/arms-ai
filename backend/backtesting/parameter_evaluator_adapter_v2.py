from __future__ import annotations

from typing import Any

from backend.backtesting.backtest_composite_score_v2 import (
    BacktestCompositeScoreV2,
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
    ) -> dict[str, Any]:

        result = (
            self.evaluator.evaluate(
                parameters=parameters,
                candles=testing_items,
            )
        )


        statistics = getattr(
            result.result,
            "statistics",
            None,
        )


        total_trades = 0

        if statistics is not None:
            total_trades = int(
                getattr(
                    statistics,
                    "total_trades",
                    0,
                )
            )


        score_result = (
            self.score_engine.calculate(
                metrics={
                    "net_pnl": (
                        result.net_profit
                    ),
                    "win_rate": (
                        result.win_rate
                    ),
                    "profit_factor": (
                        result.profit_factor
                        or 0.0
                    ),
                    "expectancy": float(
                        getattr(
                            statistics,
                            "expectancy",
                            0.0,
                        )
                    )
                    if statistics
                    else 0.0,
                    "maximum_drawdown": (
                        result.max_drawdown
                    ),
                    "total_trades": (
                        total_trades
                    ),
                }
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
