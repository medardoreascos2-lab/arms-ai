from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from backend.backtesting.monte_carlo_report_v2 import (
    MonteCarloReportV2,
)
from backend.backtesting.monte_carlo_simulator_v2 import (
    MonteCarloSimulationResultV2,
)


@dataclass(slots=True)
class MonteCarloPipelineResultV2:
    """
    Resultado consolidado del pipeline Monte Carlo.
    """

    report: MonteCarloReportV2
    json_path: Path
    html_path: Path

    def __post_init__(self) -> None:

        if not isinstance(
            self.report,
            MonteCarloReportV2,
        ):
            raise TypeError(
                "report debe ser MonteCarloReportV2."
            )

        self.json_path = Path(
            self.json_path
        )

        self.html_path = Path(
            self.html_path
        )


class MonteCarloPipelineV2:
    """
    Orquesta simulación, reporte y exportación
    JSON/HTML del análisis Monte Carlo.
    """

    def __init__(
        self,
        *,
        simulator,
        json_exporter,
        html_exporter,
    ) -> None:

        if not callable(
            getattr(
                simulator,
                "simulate",
                None,
            )
        ):
            raise TypeError(
                "simulator debe implementar simulate()."
            )

        if not callable(
            getattr(
                json_exporter,
                "export",
                None,
            )
        ):
            raise TypeError(
                "json_exporter debe implementar export()."
            )

        if not callable(
            getattr(
                html_exporter,
                "export",
                None,
            )
        ):
            raise TypeError(
                "html_exporter debe implementar export()."
            )

        self.simulator = simulator
        self.json_exporter = json_exporter
        self.html_exporter = html_exporter

    def run(
        self,
        *,
        trade_pnls,
        starting_balance,
        output_directory,
        json_filename: str = "monte_carlo.json",
        html_filename: str = "monte_carlo.html",
    ) -> MonteCarloPipelineResultV2:

        normalized_json_filename = str(
            json_filename
        ).strip()

        normalized_html_filename = str(
            html_filename
        ).strip()

        if not normalized_json_filename:
            raise ValueError(
                "json_filename no puede estar vacío."
            )

        if not normalized_html_filename:
            raise ValueError(
                "html_filename no puede estar vacío."
            )

        normalized_output_directory = Path(
            output_directory
        )

        simulation_result = self.simulator.simulate(
            trade_pnls=trade_pnls,
            starting_balance=starting_balance,
        )

        if not isinstance(
            simulation_result,
            MonteCarloSimulationResultV2,
        ):
            raise TypeError(
                "simulator.simulate() debe devolver "
                "MonteCarloSimulationResultV2."
            )

        report = MonteCarloReportV2(
            simulation_result=simulation_result,
        )

        json_output_path = (
            normalized_output_directory
            / normalized_json_filename
        )

        html_output_path = (
            normalized_output_directory
            / normalized_html_filename
        )

        json_path = self.json_exporter.export(
            report=report,
            output_path=json_output_path,
        )

        html_path = self.html_exporter.export(
            report=report,
            output_path=html_output_path,
        )

        return MonteCarloPipelineResultV2(
            report=report,
            json_path=Path(
                json_path
            ),
            html_path=Path(
                html_path
            ),
        )
