from pathlib import Path

import pytest

from backend.backtesting.strategy_certification_pipeline_v2 import (
    StrategyCertificationPipelineResultV2,
    StrategyCertificationPipelineV2,
)
from backend.backtesting.strategy_certification_engine_v2 import (
    StrategyCertificationResultV2,
)


class FakeValidationPipeline:

    def run(self):

        from backend.backtesting.strategy_validation_result_v2 import (
            StrategyValidationResultV2,
        )
        from backend.backtesting.strategy_validation_report_v2 import (
            StrategyValidationReportV2,
        )
        from backend.backtesting.walk_forward_optimization_result_v2 import (
            WalkForwardOptimizationResultV2,
        )
        from backend.backtesting.monte_carlo_report_v2 import (
            MonteCarloReportV2,
        )
        from backend.backtesting.monte_carlo_simulator_v2 import (
            MonteCarloSimulationResultV2,
        )

        walk_forward = WalkForwardOptimizationResultV2(
            window_results=[
                {
                    "window_index": 0,
                    "success": True,
                    "training_score": 91.0,
                    "testing_score": 83.0,
                    "testing_net_pnl": 420.0,
                    "testing_win_rate": 0.65,
                    "testing_maximum_drawdown": 110.0,
                    "best_parameters": {
                        "ema": 50,
                    },
                },
            ],
        )

        monte_carlo = MonteCarloReportV2(
            simulation_result=MonteCarloSimulationResultV2(
                starting_balance=10000.0,
                final_equities=[
                    10150.0,
                    10050.0,
                ],
                maximum_drawdowns=[
                    60.0,
                    120.0,
                ],
                equity_curves=[
                    [
                        10000.0,
                        10100.0,
                        10150.0,
                    ],
                    [
                        10000.0,
                        10020.0,
                        10050.0,
                    ],
                ],
            )
        )

        validation_result = StrategyValidationResultV2(
            backtest_score=90.0,
            walk_forward_result=walk_forward,
            monte_carlo_report=monte_carlo,
        )

        report = StrategyValidationReportV2(
            validation_result=validation_result,
        )

        class Result:
            pass

        result = Result()
        result.validation_result = validation_result
        result.report = report
        return result


def test_runs_complete_certification_pipeline():

    pipeline = StrategyCertificationPipelineV2(
        validation_pipeline=FakeValidationPipeline(),
    )

    result = pipeline.run()

    assert isinstance(
        result,
        StrategyCertificationPipelineResultV2,
    )

    assert isinstance(
        result.certification,
        StrategyCertificationResultV2,
    )

    assert result.validation_score > 0
    assert result.validation_grade != ""

    assert result.certification.status in {
        "CERTIFIED",
        "PROVISIONAL",
        "REJECTED",
    }


def test_pipeline_is_deterministic():

    pipeline = StrategyCertificationPipelineV2(
        validation_pipeline=FakeValidationPipeline(),
    )

    first = pipeline.run()
    second = pipeline.run()

    assert (
        first.validation_score
        == second.validation_score
    )

    assert (
        first.validation_grade
        == second.validation_grade
    )

    assert (
        first.certification.status
        == second.certification.status
    )


def test_rejects_invalid_validation_pipeline():

    with pytest.raises(
        TypeError,
        match="run",
    ):
        StrategyCertificationPipelineV2(
            validation_pipeline=object(),
        )
