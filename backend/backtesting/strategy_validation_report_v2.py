from __future__ import annotations

from copy import deepcopy
from typing import Any

from backend.backtesting.strategy_validation_result_v2 import (
    StrategyValidationResultV2,
)


class StrategyValidationReportV2:
    """
    Presenta un reporte ejecutivo a partir de un
    StrategyValidationResultV2.
    """

    def __init__(
        self,
        *,
        validation_result: StrategyValidationResultV2,
    ) -> None:

        if not isinstance(
            validation_result,
            StrategyValidationResultV2,
        ):
            raise TypeError(
                "validation_result debe ser "
                "StrategyValidationResultV2."
            )

        self.validation_result = validation_result

    def summary(
        self,
    ) -> dict[str, float | int]:

        walk_forward_result = (
            self.validation_result
            .walk_forward_result
        )

        monte_carlo_summary = (
            self.validation_result
            .monte_carlo_report
            .summary()
        )

        return {
            "backtest_score": (
                self.validation_result
                .backtest_score
            ),
            "walk_forward_score": (
                walk_forward_result
                .average_testing_score
            ),
            "validation_score": (
                self.validation_result
                .validation_score
            ),
            "total_windows": (
                walk_forward_result
                .total_windows
            ),
            "successful_windows": (
                walk_forward_result
                .successful_windows
            ),
            "failed_windows": (
                walk_forward_result
                .failed_windows
            ),
            "total_simulations": int(
                monte_carlo_summary[
                    "total_simulations"
                ]
            ),
            "average_final_equity": float(
                monte_carlo_summary[
                    "average_final_equity"
                ]
            ),
            "worst_maximum_drawdown": float(
                monte_carlo_summary[
                    "worst_maximum_drawdown"
                ]
            ),
        }

    def to_dict(
        self,
    ) -> dict[str, Any]:

        validation_payload = (
            self.validation_result
            .to_dict()
        )

        return {
            "summary": deepcopy(
                self.summary()
            ),
            "walk_forward": deepcopy(
                validation_payload[
                    "walk_forward"
                ]
            ),
            "monte_carlo": deepcopy(
                validation_payload[
                    "monte_carlo"
                ]
            ),
        }
