import json

from backend.backtesting.monte_carlo_report_v2 import (
    MonteCarloReportV2,
)
from backend.backtesting.strategy_certification_pipeline_v2 import (
    StrategyCertificationPipelineResultV2,
    StrategyCertificationPipelineV2,
)
from backend.backtesting.strategy_validation_pipeline_v2 import (
    StrategyValidationPipelineV2,
)
from backend.backtesting.walk_forward_optimization_result_v2 import (
    WalkForwardOptimizationResultV2,
)


class FakeWalkForwardPipeline:

    def run(
        self,
        *,
        items=None,
        parameter_sets=None,
        output_directory=None,
        **kwargs,
    ):

        return WalkForwardOptimizationResultV2(
            window_results=[
                {
                    "window_index": 0,
                    "success": True,
                    "training_score": 96.0,
                    "testing_score": 94.0,
                    "testing_net_pnl": 820.0,
                    "testing_win_rate": 0.72,
                    "testing_maximum_drawdown": 85.0,
                    "best_parameters": {
                        "ema": 50,
                    },
                },
            ],
        )



class FakeMonteCarloPipeline:

    def run(
        self,
        *,
        trade_pnls=None,
        starting_balance=None,
        output_directory=None,
        **kwargs,
    ):

        from backend.backtesting.monte_carlo_simulator_v2 import (
            MonteCarloSimulationResultV2,
        )

        return type(
            "FakeMonteCarloResult",
            (),
            {
                "report": MonteCarloReportV2(
                    simulation_result=MonteCarloSimulationResultV2(
                        starting_balance=10000.0,
                        final_equities=[
                            10100.0,
                            10200.0,
                        ],
                        maximum_drawdowns=[
                            50.0,
                            75.0,
                        ],
                        equity_curves=[
                            [
                                10000.0,
                                10050.0,
                                10100.0,
                            ],
                            [
                                10000.0,
                                10100.0,
                                10200.0,
                            ],
                        ],
                    )
                )
            },
        )()



class RealJsonExporter:

    def export(
        self,
        *,
        report,
        output_path,
    ):

        from backend.backtesting.strategy_validation_json_exporter_v2 import (
            StrategyValidationJsonExporterV2,
        )

        return StrategyValidationJsonExporterV2().export(
            report=report,
            output_path=output_path,
        )


class RealHtmlExporter:

    def export(
        self,
        *,
        report,
        output_path,
    ):

        from backend.backtesting.strategy_validation_html_exporter_v2 import (
            StrategyValidationHtmlExporterV2,
        )

        return StrategyValidationHtmlExporterV2().export(
            report=report,
            output_path=output_path,
        )


class ValidationPipelineAdapter:

    def __init__(
        self,
        *,
        validation_pipeline,
        backtest_score,
        output_directory,
    ) -> None:

        self.validation_pipeline = validation_pipeline
        self.backtest_score = backtest_score
        self.output_directory = output_directory

    def run(self):

        self.last_result = self.validation_pipeline.run(
            backtest_score=self.backtest_score,
            output_directory=self.output_directory,
        )

        return self.last_result


def build_certification_pipeline(
    tmp_path,
):

    validation_pipeline = StrategyValidationPipelineV2(
        walk_forward_pipeline=FakeWalkForwardPipeline(),
        monte_carlo_pipeline=FakeMonteCarloPipeline(),
        json_exporter=RealJsonExporter(),
        html_exporter=RealHtmlExporter(),
    )

    adapter = ValidationPipelineAdapter(
        validation_pipeline=validation_pipeline,
        backtest_score=95.0,
        output_directory=tmp_path,
    )

    return StrategyCertificationPipelineV2(
        validation_pipeline=adapter,
    )


def test_real_strategy_certification_pipeline_e2e(
    tmp_path,
):

    pipeline = build_certification_pipeline(
        tmp_path,
    )

    result = pipeline.run()

    assert isinstance(
        result,
        StrategyCertificationPipelineResultV2,
    )

    assert result.validation_score == 96.33
    assert result.validation_grade == "A"

    assert result.certification.status == "CERTIFIED"
    assert result.certification.validation_score == 96.33
    assert result.certification.validation_grade == "A"

    payload = result.to_dict()

    assert payload["score"]["score"] == 96.33
    assert payload["grade"]["grade"] == "A"
    assert payload["certification"]["status"] == "CERTIFIED"

    validation_pipeline_result = (
        pipeline.validation_pipeline.last_result
    )

    json_path = (
        validation_pipeline_result.json_path
    )

    html_path = (
        validation_pipeline_result.html_path
    )

    assert json_path.exists()
    assert html_path.exists()

    json_payload = json.loads(
        json_path.read_text(
            encoding="utf-8",
        )
    )

    assert (
        json_payload["summary"]["backtest_score"]
        == 95.0
    )

    assert (
        json_payload["summary"]["walk_forward_score"]
        == 94.0
    )

    assert (
        json_payload["summary"]["total_simulations"]
        == 2
    )


def test_real_certification_pipeline_is_deterministic(
    tmp_path,
):

    pipeline = build_certification_pipeline(
        tmp_path,
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

    assert (
        first.to_dict()
        == second.to_dict()
    )
