from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.backtesting.strategy_certification_engine_v2 import (
    StrategyCertificationEngineV2,
    StrategyCertificationResultV2,
)
from backend.backtesting.strategy_validation_report_v2 import (
    StrategyValidationReportV2,
)
from backend.backtesting.strategy_validation_result_v2 import (
    StrategyValidationResultV2,
)
from backend.backtesting.validation_grade_engine_v2 import (
    ValidationGradeEngineV2,
    ValidationGradeResultV2,
)
from backend.backtesting.validation_score_engine_v2 import (
    ValidationScoreEngineV2,
    ValidationScoreResultV2,
)


@dataclass(slots=True)
class StrategyCertificationPipelineResultV2:
    """
    Resultado consolidado del pipeline maestro
    de certificación de estrategias.
    """

    validation_result: StrategyValidationResultV2
    validation_report: StrategyValidationReportV2
    score_result: ValidationScoreResultV2
    grade_result: ValidationGradeResultV2
    certification: StrategyCertificationResultV2
    performance_report: dict[str, Any]

    @property
    def validation_score(
        self,
    ) -> float:

        return self.score_result.score

    @property
    def validation_grade(
        self,
    ) -> str:

        return self.grade_result.grade

    def to_dict(
        self,
    ) -> dict[str, Any]:

        return {
            "validation": (
                self.validation_report.to_dict()
            ),
            "score": (
                self.score_result.to_dict()
            ),
            "grade": (
                self.grade_result.to_dict()
            ),
            "certification": (
                self.certification.to_dict()
            ),
        }


class StrategyCertificationPipelineV2:
    """
    Orquesta validación, scoring, grading
    y certificación final de una estrategia.
    """

    def __init__(
        self,
        *,
        validation_pipeline,
        score_engine=None,
        grade_engine=None,
        certification_engine=None,
        performance_report_provider=None,
        registry_service=None,
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

        if score_engine is None:
            score_engine = ValidationScoreEngineV2()

        if grade_engine is None:
            grade_engine = ValidationGradeEngineV2()

        if certification_engine is None:
            certification_engine = (
                StrategyCertificationEngineV2()
            )

        if not callable(
            getattr(
                score_engine,
                "calculate",
                None,
            )
        ):
            raise TypeError(
                "score_engine debe implementar calculate()."
            )

        if not callable(
            getattr(
                grade_engine,
                "calculate",
                None,
            )
        ):
            raise TypeError(
                "grade_engine debe implementar calculate()."
            )

        if not callable(
            getattr(
                certification_engine,
                "certify",
                None,
            )
        ):
            raise TypeError(
                "certification_engine debe implementar certify()."
            )


        if (
            performance_report_provider is not None
            and not callable(
                getattr(
                    performance_report_provider,
                    "get_report",
                    None,
                )
            )
        ):
            raise TypeError(
                "performance_report_provider debe implementar get_report()."
            )

        self.validation_pipeline = (
            validation_pipeline
        )

        self.score_engine = score_engine
        self.grade_engine = grade_engine
        self.certification_engine = (
            certification_engine
        )

        self.performance_report_provider = (
            performance_report_provider
        )


        if (
            registry_service is not None
            and not callable(
                getattr(
                    registry_service,
                    "register_certified_strategy",
                    None,
                )
            )
        ):
            raise TypeError(
                "registry_service debe implementar "
                "register_certified_strategy()."
            )


        self.registry_service = (
            registry_service
        )

    def run(
        self,
    ) -> StrategyCertificationPipelineResultV2:

        validation_pipeline_result = (
            self.validation_pipeline.run()
        )

        validation_result = getattr(
            validation_pipeline_result,
            "validation_result",
            None,
        )

        validation_report = getattr(
            validation_pipeline_result,
            "report",
            None,
        )

        if not isinstance(
            validation_result,
            StrategyValidationResultV2,
        ):
            raise TypeError(
                "validation_pipeline.run() debe exponer "
                "validation_result como "
                "StrategyValidationResultV2."
            )

        if not isinstance(
            validation_report,
            StrategyValidationReportV2,
        ):
            raise TypeError(
                "validation_pipeline.run() debe exponer "
                "report como StrategyValidationReportV2."
            )

        monte_carlo_summary = (
            validation_result
            .monte_carlo_report
            .summary()
        )

        starting_balance = float(
            monte_carlo_summary[
                "starting_balance"
            ]
        )

        average_final_equity = float(
            monte_carlo_summary[
                "average_final_equity"
            ]
        )

        if starting_balance <= 0.0:
            raise ValueError(
                "starting_balance debe ser mayor que cero."
            )

        monte_carlo_score = (
            average_final_equity
            / starting_balance
            * 100.0
        )

        score_result = (
            self.score_engine.calculate(
                backtest_score=(
                    validation_result
                    .backtest_score
                ),
                walk_forward_score=(
                    validation_result
                    .walk_forward_result
                    .average_testing_score
                ),
                monte_carlo_score=(
                    monte_carlo_score
                ),
            )
        )

        if not isinstance(
            score_result,
            ValidationScoreResultV2,
        ):
            raise TypeError(
                "score_engine.calculate() debe devolver "
                "ValidationScoreResultV2."
            )

        grade_result = (
            self.grade_engine.calculate(
                validation_score=(
                    score_result.score
                ),
            )
        )

        if not isinstance(
            grade_result,
            ValidationGradeResultV2,
        ):
            raise TypeError(
                "grade_engine.calculate() debe devolver "
                "ValidationGradeResultV2."
            )

        certification = (
            self.certification_engine.certify(
                validation_score=(
                    score_result.score
                ),
                validation_grade=(
                    grade_result.grade
                ),
            )
        )

        if not isinstance(
            certification,
            StrategyCertificationResultV2,
        ):
            raise TypeError(
                "certification_engine.certify() debe devolver "
                "StrategyCertificationResultV2."
            )


        if (
            self.registry_service is not None
            and certification.status == "CERTIFIED"
        ):

            self.registry_service.register_certified_strategy(
                {
                    "strategy_id": "STR-001",
                    "name": "Certified Strategy",
                    "version": "1.0",
                    "status": (
                        certification.status
                    ),
                    "grade": (
                        grade_result.grade
                    ),
                    "validation_score": (
                        score_result.score
                    ),
                    "performance_score": (
                        score_result.score
                    ),
                }
            )


        performance_report = {}

        if self.performance_report_provider is not None:
            performance_report = (
                self.performance_report_provider
                .get_report()
            )

        return StrategyCertificationPipelineResultV2(
            performance_report=performance_report,
            validation_result=(
                validation_result
            ),
            validation_report=(
                validation_report
            ),
            score_result=score_result,
            grade_result=grade_result,
            certification=certification,
        )
