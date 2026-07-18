from dataclasses import dataclass
from statistics import mean, median
from types import MappingProxyType
from typing import Mapping

from backend.portfolio.portfolio import Portfolio
from backend.portfolio.portfolio_stress_test import (
    PortfolioStressTest,
)


@dataclass(frozen=True)
class PortfolioScenarioAnalysis:
    """
    Ejecuta múltiples escenarios de estrés y
    compara sus resultados.
    """

    results: Mapping[str, PortfolioStressTest]
    scenario_count: int
    best_scenario: str
    best_change: float
    worst_scenario: str
    worst_change: float
    average_change: float
    median_change: float

    @classmethod
    def run(
        cls,
        *,
        portfolio: Portfolio,
        scenarios: dict[str, dict],
    ) -> "PortfolioScenarioAnalysis":
        if not isinstance(
            portfolio,
            Portfolio,
        ):
            raise TypeError(
                "portfolio debe ser Portfolio."
            )

        if not scenarios:
            raise ValueError(
                "scenarios no puede estar vacío."
            )

        results: dict[
            str,
            PortfolioStressTest,
        ] = {}

        for name, config in scenarios.items():
            if not isinstance(config, dict):
                raise ValueError(
                    "Cada scenario debe ser un diccionario."
                )

            if (
                "global_shock" not in config
                and "shocks" not in config
            ):
                raise ValueError(
                    "Cada scenario debe definir "
                    "global_shock o shocks."
                )

            results[name] = PortfolioStressTest.run(
                portfolio=portfolio,
                global_shock=config.get(
                    "global_shock"
                ),
                shocks=config.get(
                    "shocks"
                ),
            )

        changes = [
            report.absolute_change
            for report in results.values()
        ]

        best_scenario = max(
            results,
            key=lambda name: (
                results[name].absolute_change
            ),
        )

        worst_scenario = min(
            results,
            key=lambda name: (
                results[name].absolute_change
            ),
        )

        return cls(
            results=MappingProxyType(
                dict(results)
            ),
            scenario_count=len(results),
            best_scenario=best_scenario,
            best_change=results[
                best_scenario
            ].absolute_change,
            worst_scenario=worst_scenario,
            worst_change=results[
                worst_scenario
            ].absolute_change,
            average_change=round(
                mean(changes),
                2,
            ),
            median_change=round(
                median(changes),
                2,
            ),
        )
