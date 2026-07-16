from dataclasses import dataclass
from typing import Any

from backend.backtesting.walk_forward_optimizer import (
    WalkForwardOptimizationResult,
)


@dataclass(frozen=True)
class WalkForwardOptimizationWindowReport:
    window_number: int
    selected_parameters: dict[str, Any]

    training_net_profit: float
    testing_net_profit: float

    performance_degradation: float
    degradation_rate: float
    overfit_suspected: bool


@dataclass(frozen=True)
class WalkForwardOptimizationReport:
    total_windows: int

    profitable_testing_windows: int
    losing_testing_windows: int
    breakeven_testing_windows: int

    total_training_net_profit: float
    total_testing_net_profit: float

    average_training_net_profit: float
    average_testing_net_profit: float
    average_performance_degradation: float

    testing_profitable_rate: float

    overfit_windows: int
    overfit_rate: float

    windows: list[WalkForwardOptimizationWindowReport]

    @classmethod
    def from_results(
        cls,
        results: list[WalkForwardOptimizationResult],
    ) -> "WalkForwardOptimizationReport":
        if not results:
            return cls(
                total_windows=0,
                profitable_testing_windows=0,
                losing_testing_windows=0,
                breakeven_testing_windows=0,
                total_training_net_profit=0.0,
                total_testing_net_profit=0.0,
                average_training_net_profit=0.0,
                average_testing_net_profit=0.0,
                average_performance_degradation=0.0,
                testing_profitable_rate=0.0,
                overfit_windows=0,
                overfit_rate=0.0,
                windows=[],
            )

        windows: list[
            WalkForwardOptimizationWindowReport
        ] = []

        for window_number, result in enumerate(
            results,
            start=1,
        ):
            training_profit = float(
                result.training_evaluation.net_profit
            )
            testing_profit = float(
                result.testing_evaluation.net_profit
            )

            performance_degradation = (
                training_profit - testing_profit
            )

            degradation_rate = cls._calculate_degradation_rate(
                training_profit=training_profit,
                performance_degradation=performance_degradation,
            )

            overfit_suspected = cls._is_overfit_suspected(
                training_profit=training_profit,
                testing_profit=testing_profit,
                degradation_rate=degradation_rate,
            )

            windows.append(
                WalkForwardOptimizationWindowReport(
                    window_number=window_number,
                    selected_parameters=dict(
                        result.selected_parameters
                    ),
                    training_net_profit=round(
                        training_profit,
                        2,
                    ),
                    testing_net_profit=round(
                        testing_profit,
                        2,
                    ),
                    performance_degradation=round(
                        performance_degradation,
                        2,
                    ),
                    degradation_rate=round(
                        degradation_rate,
                        2,
                    ),
                    overfit_suspected=overfit_suspected,
                )
            )

        total_windows = len(windows)

        profitable_testing_windows = sum(
            1
            for window in windows
            if window.testing_net_profit > 0
        )

        losing_testing_windows = sum(
            1
            for window in windows
            if window.testing_net_profit < 0
        )

        breakeven_testing_windows = sum(
            1
            for window in windows
            if window.testing_net_profit == 0
        )

        total_training_net_profit = sum(
            window.training_net_profit
            for window in windows
        )

        total_testing_net_profit = sum(
            window.testing_net_profit
            for window in windows
        )

        average_training_net_profit = (
            total_training_net_profit
            / total_windows
        )

        average_testing_net_profit = (
            total_testing_net_profit
            / total_windows
        )

        average_performance_degradation = (
            sum(
                window.performance_degradation
                for window in windows
            )
            / total_windows
        )

        testing_profitable_rate = (
            profitable_testing_windows
            / total_windows
            * 100
        )

        overfit_windows = sum(
            1
            for window in windows
            if window.overfit_suspected
        )

        overfit_rate = (
            overfit_windows
            / total_windows
            * 100
        )

        return cls(
            total_windows=total_windows,
            profitable_testing_windows=(
                profitable_testing_windows
            ),
            losing_testing_windows=(
                losing_testing_windows
            ),
            breakeven_testing_windows=(
                breakeven_testing_windows
            ),
            total_training_net_profit=round(
                total_training_net_profit,
                2,
            ),
            total_testing_net_profit=round(
                total_testing_net_profit,
                2,
            ),
            average_training_net_profit=round(
                average_training_net_profit,
                2,
            ),
            average_testing_net_profit=round(
                average_testing_net_profit,
                2,
            ),
            average_performance_degradation=round(
                average_performance_degradation,
                2,
            ),
            testing_profitable_rate=round(
                testing_profitable_rate,
                2,
            ),
            overfit_windows=overfit_windows,
            overfit_rate=round(
                overfit_rate,
                2,
            ),
            windows=windows,
        )

    @staticmethod
    def _calculate_degradation_rate(
        training_profit: float,
        performance_degradation: float,
    ) -> float:
        if training_profit == 0:
            return 0.0

        return (
            performance_degradation
            / abs(training_profit)
            * 100
        )

    @staticmethod
    def _is_overfit_suspected(
        training_profit: float,
        testing_profit: float,
        degradation_rate: float,
    ) -> bool:
        if training_profit <= 0:
            return False

        if testing_profit < 0:
            return True

        return degradation_rate >= 70.0
