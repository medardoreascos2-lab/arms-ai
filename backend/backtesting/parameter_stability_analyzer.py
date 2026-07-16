from dataclasses import dataclass
from typing import Any

from backend.backtesting.walk_forward_optimization_report import (
    WalkForwardOptimizationReport,
)


@dataclass(frozen=True)
class ParameterStabilitySummary:
    name: str
    total_observations: int
    frequencies: dict[Any, int]
    dominant_value: Any
    dominant_count: int
    dominant_rate: float
    stability_score: float


@dataclass(frozen=True)
class ParameterStabilityAnalysis:
    total_windows: int
    parameters: dict[str, ParameterStabilitySummary]
    overall_stability_score: float


class ParameterStabilityAnalyzer:
    """
    Analiza la frecuencia y estabilidad de los parámetros
    seleccionados entre ventanas de optimización.
    """

    def analyze(
        self,
        report: WalkForwardOptimizationReport,
    ) -> ParameterStabilityAnalysis:
        if not report.windows:
            return ParameterStabilityAnalysis(
                total_windows=0,
                parameters={},
                overall_stability_score=0.0,
            )

        parameter_frequencies: dict[
            str,
            dict[Any, int],
        ] = {}

        for window in report.windows:
            for name, value in (
                window.selected_parameters.items()
            ):
                if name not in parameter_frequencies:
                    parameter_frequencies[name] = {}

                frequencies = parameter_frequencies[name]

                frequencies[value] = (
                    frequencies.get(value, 0)
                    + 1
                )

        summaries: dict[
            str,
            ParameterStabilitySummary,
        ] = {}

        for name, frequencies in (
            parameter_frequencies.items()
        ):
            total_observations = sum(
                frequencies.values()
            )

            dominant_value = max(
                frequencies,
                key=lambda value: frequencies[value],
            )

            dominant_count = frequencies[
                dominant_value
            ]

            dominant_rate = (
                dominant_count
                / total_observations
                * 100
            )

            stability_score = dominant_rate

            summaries[name] = (
                ParameterStabilitySummary(
                    name=name,
                    total_observations=(
                        total_observations
                    ),
                    frequencies=dict(frequencies),
                    dominant_value=dominant_value,
                    dominant_count=dominant_count,
                    dominant_rate=round(
                        dominant_rate,
                        2,
                    ),
                    stability_score=round(
                        stability_score,
                        2,
                    ),
                )
            )

        overall_stability_score = (
            sum(
                summary.stability_score
                for summary in summaries.values()
            )
            / len(summaries)
            if summaries
            else 0.0
        )

        return ParameterStabilityAnalysis(
            total_windows=report.total_windows,
            parameters=summaries,
            overall_stability_score=round(
                overall_stability_score,
                2,
            ),
        )
