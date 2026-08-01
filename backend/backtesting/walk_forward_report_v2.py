from __future__ import annotations

from copy import deepcopy
from typing import Any

from backend.backtesting.walk_forward_optimization_result_v2 import (
    WalkForwardOptimizationResultV2,
)


class WalkForwardReportV2:
    """
    Presenta un reporte estructurado a partir de un
    WalkForwardOptimizationResultV2.
    """

    def __init__(
        self,
        *,
        optimization_result: WalkForwardOptimizationResultV2,
    ) -> None:

        if not isinstance(
            optimization_result,
            WalkForwardOptimizationResultV2,
        ):
            raise TypeError(
                "optimization_result debe ser "
                "WalkForwardOptimizationResultV2."
            )

        self.optimization_result = (
            optimization_result
        )

    @property
    def total_windows(
        self,
    ) -> int:

        return (
            self.optimization_result
            .total_windows
        )

    @property
    def successful_windows(
        self,
    ) -> int:

        return (
            self.optimization_result
            .successful_windows
        )

    @property
    def failed_windows(
        self,
    ) -> int:

        return (
            self.optimization_result
            .failed_windows
        )

    def summary(
        self,
    ) -> dict[str, Any]:

        result = self.optimization_result

        return {
            "total_windows": (
                result.total_windows
            ),
            "successful_windows": (
                result.successful_windows
            ),
            "failed_windows": (
                result.failed_windows
            ),
            "average_training_score": (
                result.average_training_score
            ),
            "average_testing_score": (
                result.average_testing_score
            ),
            "average_testing_net_pnl": (
                result.average_testing_net_pnl
            ),
            "average_testing_win_rate": (
                result.average_testing_win_rate
            ),
            "average_testing_maximum_drawdown": (
                result
                .average_testing_maximum_drawdown
            ),
            "most_frequent_parameters": (
                result.most_frequent_parameters()
            ),
        }

    def best_window(
        self,
    ) -> dict[str, Any] | None:

        if not self.successful_windows:
            return None

        return deepcopy(
            self.optimization_result
            .best_window()
        )

    def worst_window(
        self,
    ) -> dict[str, Any] | None:

        if not self.successful_windows:
            return None

        return deepcopy(
            self.optimization_result
            .worst_window()
        )

    def to_dict(
        self,
    ) -> dict[str, Any]:

        return {
            "summary": deepcopy(
                self.summary()
            ),
            "best_window": (
                self.best_window()
            ),
            "worst_window": (
                self.worst_window()
            ),
            "window_results": deepcopy(
                self.optimization_result
                .window_results
            ),
        }
