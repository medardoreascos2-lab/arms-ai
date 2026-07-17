from dataclasses import dataclass
from statistics import mean, median

from backend.backtesting.monte_carlo_engine import (
    MonteCarloResult,
)


@dataclass(frozen=True)
class MonteCarloReport:
    total_simulations: int

    average_final_balance: float
    median_final_balance: float
    best_final_balance: float
    worst_final_balance: float

    average_max_drawdown: float
    worst_max_drawdown: float

    loss_probability: float
    ruin_probability: float

    final_balance_percentile_5: float
    final_balance_percentile_50: float
    final_balance_percentile_95: float

    drawdown_percentile_50: float
    drawdown_percentile_95: float
    drawdown_percentile_99: float
    method: str = "shuffle"

    @classmethod
    def from_result(
        cls,
        result: MonteCarloResult,
        ruin_balance: float,
    ) -> "MonteCarloReport":
        if not result.simulations:
            raise ValueError(
                "result requiere simulations."
            )

        if ruin_balance <= 0:
            raise ValueError(
                "ruin_balance debe ser mayor que cero."
            )

        final_balances = sorted(
            float(simulation.final_balance)
            for simulation in result.simulations
        )

        max_drawdowns = sorted(
            float(simulation.max_drawdown)
            for simulation in result.simulations
        )

        initial_balance = float(
            result.simulations[0].initial_balance
        )

        total_simulations = len(
            result.simulations
        )

        losing_simulations = sum(
            1
            for final_balance in final_balances
            if final_balance < initial_balance
        )

        ruined_simulations = sum(
            1
            for final_balance in final_balances
            if final_balance < ruin_balance
        )

        return cls(
            method=result.method,
            total_simulations=total_simulations,
            average_final_balance=round(
                mean(final_balances),
                2,
            ),
            median_final_balance=round(
                median(final_balances),
                2,
            ),
            best_final_balance=round(
                max(final_balances),
                2,
            ),
            worst_final_balance=round(
                min(final_balances),
                2,
            ),
            average_max_drawdown=round(
                mean(max_drawdowns),
                2,
            ),
            worst_max_drawdown=round(
                max(max_drawdowns),
                2,
            ),
            loss_probability=round(
                losing_simulations
                / total_simulations
                * 100,
                2,
            ),
            ruin_probability=round(
                ruined_simulations
                / total_simulations
                * 100,
                2,
            ),
            final_balance_percentile_5=(
                cls._percentile(
                    final_balances,
                    5,
                )
            ),
            final_balance_percentile_50=(
                cls._percentile(
                    final_balances,
                    50,
                )
            ),
            final_balance_percentile_95=(
                cls._percentile(
                    final_balances,
                    95,
                )
            ),
            drawdown_percentile_50=(
                cls._percentile(
                    max_drawdowns,
                    50,
                )
            ),
            drawdown_percentile_95=(
                cls._percentile(
                    max_drawdowns,
                    95,
                )
            ),
            drawdown_percentile_99=(
                cls._percentile(
                    max_drawdowns,
                    99,
                )
            ),
        )

    @staticmethod
    def _percentile(
        values: list[float],
        percentile: float,
    ) -> float:
        if len(values) == 1:
            return round(
                values[0],
                2,
            )

        position = (
            len(values) - 1
        ) * (
            percentile / 100
        )

        lower_index = int(position)
        upper_index = min(
            lower_index + 1,
            len(values) - 1,
        )

        weight = (
            position - lower_index
        )

        value = (
            values[lower_index]
            * (1 - weight)
            + values[upper_index]
            * weight
        )

        return round(
            value,
            2,
        )
