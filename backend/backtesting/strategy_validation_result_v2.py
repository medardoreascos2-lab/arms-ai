from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from backend.backtesting.monte_carlo_report_v2 import (
    MonteCarloReportV2,
)
from backend.backtesting.walk_forward_optimization_result_v2 import (
    WalkForwardOptimizationResultV2,
)


@dataclass(slots=True)
class StrategyValidationResultV2:
    """
    Consolida los resultados principales de validación
    cuantitativa de una estrategia.
    """

    backtest_score: float
    walk_forward_result: WalkForwardOptimizationResultV2
    monte_carlo_report: MonteCarloReportV2

    def __post_init__(self) -> None:

        if not isinstance(
            self.backtest_score,
            (
                int,
                float,
            ),
        ):
            raise TypeError(
                "backtest_score debe ser numérico."
            )

        if isinstance(
            self.backtest_score,
            bool,
        ):
            raise TypeError(
                "backtest_score debe ser numérico."
            )

        if not isinstance(
            self.walk_forward_result,
            WalkForwardOptimizationResultV2,
        ):
            raise TypeError(
                "walk_forward_result debe ser "
                "WalkForwardOptimizationResultV2."
            )

        if not isinstance(
            self.monte_carlo_report,
            MonteCarloReportV2,
        ):
            raise TypeError(
                "monte_carlo_report debe ser "
                "MonteCarloReportV2."
            )

        self.backtest_score = float(
            self.backtest_score
        )

    @property
    def validation_score(
        self,
    ) -> float:

        walk_forward_score = (
            self.walk_forward_result
            .average_testing_score
        )

        monte_carlo_score = (
            self.monte_carlo_report
            .summary()[
                "average_final_equity"
            ]
            / 100.0
        )

        return (
            self.backtest_score
            + walk_forward_score
            + monte_carlo_score
        ) / 3.0

    def to_dict(
        self,
    ) -> dict[str, Any]:

        return {
            "backtest_score": (
                self.backtest_score
            ),
            "validation_score": (
                self.validation_score
            ),
            "walk_forward": deepcopy(
                self.walk_forward_result
                .to_dict()
            ),
            "monte_carlo": deepcopy(
                self.monte_carlo_report
                .to_dict()
            ),
        }
