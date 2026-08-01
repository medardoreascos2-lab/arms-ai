from __future__ import annotations

from copy import deepcopy
from typing import Any

from backend.backtesting.monte_carlo_simulator_v2 import (
    MonteCarloSimulationResultV2,
)


class MonteCarloReportV2:
    """
    Presenta un reporte estructurado a partir de un
    MonteCarloSimulationResultV2.
    """

    def __init__(
        self,
        *,
        simulation_result: MonteCarloSimulationResultV2,
    ) -> None:

        if not isinstance(
            simulation_result,
            MonteCarloSimulationResultV2,
        ):
            raise TypeError(
                "simulation_result debe ser "
                "MonteCarloSimulationResultV2."
            )

        self.simulation_result = simulation_result

    @property
    def total_simulations(
        self,
    ) -> int:

        return (
            self.simulation_result
            .total_simulations
        )

    def summary(
        self,
    ) -> dict[str, float | int]:

        return deepcopy(
            self.simulation_result.summary()
        )

    def best_final_equity(
        self,
    ) -> float:

        if not self.simulation_result.final_equities:
            raise ValueError(
                "No hay simulaciones disponibles."
            )

        return max(
            self.simulation_result.final_equities
        )

    def worst_final_equity(
        self,
    ) -> float:

        if not self.simulation_result.final_equities:
            raise ValueError(
                "No hay simulaciones disponibles."
            )

        return min(
            self.simulation_result.final_equities
        )

    def to_dict(
        self,
    ) -> dict[str, Any]:

        return {
            "summary": deepcopy(
                self.summary()
            ),
            "best_final_equity": (
                self.best_final_equity()
            ),
            "worst_final_equity": (
                self.worst_final_equity()
            ),
            "final_equities": deepcopy(
                self.simulation_result
                .final_equities
            ),
            "maximum_drawdowns": deepcopy(
                self.simulation_result
                .maximum_drawdowns
            ),
            "equity_curves": deepcopy(
                self.simulation_result
                .equity_curves
            ),
        }
