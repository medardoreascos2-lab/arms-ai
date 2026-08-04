from __future__ import annotations

from backend.backtesting.strategy_validation_html_exporter_v2 import (
    StrategyValidationHtmlExporterV2,
)
from backend.backtesting.strategy_validation_json_exporter_v2 import (
    StrategyValidationJsonExporterV2,
)
from backend.backtesting.strategy_validation_pipeline_v2 import (
    StrategyValidationPipelineV2,
)


def create_validation_pipeline_v2(
    *,
    walk_forward_pipeline,
    monte_carlo_pipeline,
    json_exporter=None,
    html_exporter=None,
) -> StrategyValidationPipelineV2:
    """
    Construye el pipeline institucional de validación.

    Los pipelines de Walk Forward y Monte Carlo deben
    llegar configurados con todos sus datos de ejecución.
    """

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

    if json_exporter is None:
        json_exporter = (
            StrategyValidationJsonExporterV2()
        )

    if html_exporter is None:
        html_exporter = (
            StrategyValidationHtmlExporterV2()
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

    return StrategyValidationPipelineV2(
        walk_forward_pipeline=(
            walk_forward_pipeline
        ),
        monte_carlo_pipeline=(
            monte_carlo_pipeline
        ),
        json_exporter=json_exporter,
        html_exporter=html_exporter,
    )
