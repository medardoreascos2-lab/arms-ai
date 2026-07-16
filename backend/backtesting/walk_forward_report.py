from dataclasses import dataclass
import math

from backend.backtesting.walk_forward_engine import (
    WalkForwardResult,
)


@dataclass(frozen=True)
class WalkForwardWindowReport:
    window_number: int
    training_start: int
    training_end: int
    testing_start: int
    testing_end: int
    net_profit: float


@dataclass(frozen=True)
class WalkForwardReport:
    total_windows: int
    profitable_windows: int
    losing_windows: int
    breakeven_windows: int

    total_net_profit: float
    average_net_profit: float
    profitable_window_rate: float
    net_profit_std_dev: float
    stability_score: float

    best_window_number: int | None
    best_window_profit: float | None
    worst_window_number: int | None
    worst_window_profit: float | None

    windows: list[WalkForwardWindowReport]

    @classmethod
    def from_result(
        cls,
        result: WalkForwardResult,
    ) -> "WalkForwardReport":
        window_reports: list[WalkForwardWindowReport] = []
        net_profits: list[float] = []

        for window_result in result.windows:
            backtest_result = window_result.result

            statistics = getattr(
                backtest_result,
                "statistics",
                None,
            )

            if statistics is None:
                raise ValueError(
                    "Cada resultado walk-forward requiere "
                    "statistics."
                )

            net_profit = float(
                getattr(
                    statistics,
                    "net_profit",
                    0.0,
                )
            )

            net_profits.append(net_profit)

            window_reports.append(
                WalkForwardWindowReport(
                    window_number=(
                        window_result.window_number
                    ),
                    training_start=(
                        window_result.training_start
                    ),
                    training_end=(
                        window_result.training_end
                    ),
                    testing_start=(
                        window_result.testing_start
                    ),
                    testing_end=(
                        window_result.testing_end
                    ),
                    net_profit=net_profit,
                )
            )

        total_windows = len(window_reports)

        if total_windows == 0:
            return cls(
                total_windows=0,
                profitable_windows=0,
                losing_windows=0,
                breakeven_windows=0,
                total_net_profit=0.0,
                average_net_profit=0.0,
                profitable_window_rate=0.0,
                net_profit_std_dev=0.0,
                stability_score=0.0,
                best_window_number=None,
                best_window_profit=None,
                worst_window_number=None,
                worst_window_profit=None,
                windows=[],
            )

        profitable_windows = sum(
            1
            for value in net_profits
            if value > 0
        )

        losing_windows = sum(
            1
            for value in net_profits
            if value < 0
        )

        breakeven_windows = sum(
            1
            for value in net_profits
            if value == 0
        )

        total_net_profit = sum(net_profits)

        average_net_profit = (
            total_net_profit
            / total_windows
        )

        profitable_window_rate = (
            profitable_windows
            / total_windows
            * 100
        )

        variance = sum(
            (
                value
                - average_net_profit
            ) ** 2
            for value in net_profits
        ) / total_windows

        net_profit_std_dev = math.sqrt(
            variance
        )

        stability_score = cls._calculate_stability_score(
            average_net_profit=average_net_profit,
            standard_deviation=net_profit_std_dev,
            profitable_window_rate=(
                profitable_window_rate
            ),
        )

        best_index = max(
            range(total_windows),
            key=lambda index: net_profits[index],
        )

        worst_index = min(
            range(total_windows),
            key=lambda index: net_profits[index],
        )

        best_window = window_reports[best_index]
        worst_window = window_reports[worst_index]

        return cls(
            total_windows=total_windows,
            profitable_windows=profitable_windows,
            losing_windows=losing_windows,
            breakeven_windows=breakeven_windows,
            total_net_profit=round(
                total_net_profit,
                2,
            ),
            average_net_profit=round(
                average_net_profit,
                2,
            ),
            profitable_window_rate=round(
                profitable_window_rate,
                2,
            ),
            net_profit_std_dev=(
                net_profit_std_dev
            ),
            stability_score=round(
                stability_score,
                2,
            ),
            best_window_number=(
                best_window.window_number
            ),
            best_window_profit=(
                best_window.net_profit
            ),
            worst_window_number=(
                worst_window.window_number
            ),
            worst_window_profit=(
                worst_window.net_profit
            ),
            windows=window_reports,
        )

    @staticmethod
    def _calculate_stability_score(
        average_net_profit: float,
        standard_deviation: float,
        profitable_window_rate: float,
    ) -> float:
        if standard_deviation == 0:
            consistency_score = (
                100.0
                if average_net_profit > 0
                else 0.0
            )
        else:
            scale = max(
                abs(average_net_profit),
                1.0,
            )

            normalized_volatility = (
                standard_deviation
                / scale
            )

            consistency_score = (
                100.0
                / (
                    1.0
                    + normalized_volatility
                )
            )

        profitability_score = (
            profitable_window_rate
        )

        score = (
            consistency_score * 0.6
            + profitability_score * 0.4
        )

        return max(
            0.0,
            min(100.0, score),
        )
