from __future__ import annotations

from pathlib import Path

from backend.backtesting.backtest_composite_score_v2 import (
    BacktestCompositeScoreV2,
)
from backend.backtesting.backtesting_builder_v2 import (
    build_backtest_engine,
)
from backend.backtesting.backtesting_orchestrator_v2 import (
    BacktestingOrchestratorV2,
)
from backend.backtesting.strategy_certification_pipeline_v2 import (
    StrategyCertificationPipelineV2,
)
from backend.backtesting.validation_pipeline_factory_v2 import (
    create_validation_pipeline_v2,
)
from backend.config_settings import (
    ArmsSettings,
)


class ValidationPipelineExecutionAdapterV2:
    """
    Adapta StrategyValidationPipelineV2 al contrato
    run() requerido por StrategyCertificationPipelineV2.
    """

    def __init__(
        self,
        *,
        validation_pipeline,
        backtest_score: float,
        output_directory,
    ) -> None:

        if not callable(
            getattr(
                validation_pipeline,
                "run",
                None,
            )
        ):
            raise TypeError(
                "validation_pipeline debe implementar run()."
            )

        self.validation_pipeline = (
            validation_pipeline
        )

        self.backtest_score = float(
            backtest_score
        )

        self.output_directory = Path(
            output_directory
        )

        self.last_result = None

    def run(self):

        self.last_result = (
            self.validation_pipeline.run(
                backtest_score=(
                    self.backtest_score
                ),
                output_directory=(
                    self.output_directory
                ),
            )
        )

        return self.last_result


def create_backtesting_orchestrator_v2(
    *,
    walk_forward_pipeline,
    monte_carlo_pipeline,
    settings: ArmsSettings | None = None,
    collector=None,
    minimum_trades: int = 10,
) -> BacktestingOrchestratorV2:
    """
    Construye el orquestador institucional completo.

    Walk Forward y Monte Carlo deben llegar configurados
    para la ejecución concreta que será certificada.
    """

    if settings is None:
        settings = ArmsSettings()

    if not isinstance(
        settings,
        ArmsSettings,
    ):
        raise TypeError(
            "settings debe ser ArmsSettings."
        )

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

    backtest_engine = build_backtest_engine(
        settings=settings,
        collector=collector,
    )

    score_engine = BacktestCompositeScoreV2(
        minimum_trades=minimum_trades,
    )

    def certification_pipeline_factory(
        *,
        backtest_score,
        output_directory,
    ) -> StrategyCertificationPipelineV2:

        validation_pipeline = (
            create_validation_pipeline_v2(
                walk_forward_pipeline=(
                    walk_forward_pipeline
                ),
                monte_carlo_pipeline=(
                    monte_carlo_pipeline
                ),
            )
        )

        validation_adapter = (
            ValidationPipelineExecutionAdapterV2(
                validation_pipeline=(
                    validation_pipeline
                ),
                backtest_score=(
                    backtest_score
                ),
                output_directory=(
                    output_directory
                ),
            )
        )

        return StrategyCertificationPipelineV2(
            validation_pipeline=(
                validation_adapter
            ),
        )

    return BacktestingOrchestratorV2(
        backtest_engine=backtest_engine,
        score_engine=score_engine,
        certification_pipeline_factory=(
            certification_pipeline_factory
        ),
    )
