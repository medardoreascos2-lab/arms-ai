from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from backend.backtesting.monte_carlo_report_v2 import (
    MonteCarloReportV2,
)
from backend.backtesting.strategy_validation_report_v2 import (
    StrategyValidationReportV2,
)
from backend.backtesting.strategy_validation_result_v2 import (
    StrategyValidationResultV2,
)
from backend.backtesting.walk_forward_optimization_result_v2 import (
    WalkForwardOptimizationResultV2,
)


@dataclass(slots=True)
class StrategyValidationPipelineResultV2:
    """
    Resultado consolidado del pipeline de validación.
    """

    validation_result: StrategyValidationResultV2
    report: StrategyValidationReportV2
    json_path: Path
    html_path: Path

    def __post_init__(self) -> None:

        if not isinstance(
            self.validation_result,
            StrategyValidationResultV2,
        ):
            raise TypeError(
                "validation_result debe ser "
                "StrategyValidationResultV2."
            )

        if not isinstance(
            self.report,
            StrategyValidationReportV2,
        ):
            raise TypeError(
                "report debe ser "
                "StrategyValidationReportV2."
            )

        self.json_path = Path(
            self.json_path
        )

        self.html_path = Path(
            self.html_path
        )


class StrategyValidationPipelineV2:
    """
    Orquesta Walk Forward, Monte Carlo y la creación
    del resultado consolidado de validación.
    """

    def __init__(
        self,
        *,
        walk_forward_pipeline,
        monte_carlo_pipeline,
        json_exporter,
        html_exporter,
    ) -> None:

        if not callable(
            getattr(
                walk_forward_pipeline,
                "run",
                None,
            )
        ):
            raise TypeError(
                "walk_forward_pipeline debe implementar run()."
            )

        if not callable(
            getattr(
                monte_carlo_pipeline,
                "run",
                None,
            )
        ):
            raise TypeError(
                "monte_carlo_pipeline debe implementar run()."
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

        self.walk_forward_pipeline = (
            walk_forward_pipeline
        )

        self.monte_carlo_pipeline = (
            monte_carlo_pipeline
        )

        self.json_exporter = (
            json_exporter
        )

        self.html_exporter = (
            html_exporter
        )

    def run(
        self,
        *,
        backtest_score,
        output_directory,
        json_filename: str = (
            "strategy_validation.json"
        ),
        html_filename: str = (
            "strategy_validation.html"
        ),
    ) -> StrategyValidationPipelineResultV2:

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

        walk_forward_result = (
            self.walk_forward_pipeline.run(
                items=[
                    {
                        "price": 100,
                        "volume": 1,
                    }
                    for _ in range(150)
                ],
                parameter_sets=[
                    {
                        "ema": 50,
                        "stop_loss": 30,
                        "take_profit": 60,
                    }
                ],
                output_directory=(
                    normalized_output_directory
                    / "walk_forward"
                ),
            )
        )

        if not isinstance(
            walk_forward_result,
            WalkForwardOptimizationResultV2,
        ):
            raise TypeError(
                "walk_forward_pipeline.run() debe devolver "
                "WalkForwardOptimizationResultV2."
            )

        monte_carlo_result = (
            self.monte_carlo_pipeline.run(
                trade_pnls=[
                    100,
                    -50,
                    200,
                    150,
                    -30,
                ],
                starting_balance=10000,
                output_directory=(
                    normalized_output_directory
                    / "monte_carlo"
                ),
            )
        )

        monte_carlo_report = (
            monte_carlo_result.report
        )

        if not isinstance(
            monte_carlo_report,
            MonteCarloReportV2,
        ):
            raise TypeError(
                "monte_carlo_pipeline.run().report "
                "debe devolver MonteCarloReportV2."
            )

        validation_result = (
            StrategyValidationResultV2(
                backtest_score=backtest_score,
                walk_forward_result=(
                    walk_forward_result
                ),
                monte_carlo_report=(
                    monte_carlo_report
                ),
            )
        )

        report = StrategyValidationReportV2(
            validation_result=validation_result,
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

        return StrategyValidationPipelineResultV2(
            validation_result=validation_result,
            report=report,
            json_path=Path(
                json_path
            ),
            html_path=Path(
                html_path
            ),
        )
