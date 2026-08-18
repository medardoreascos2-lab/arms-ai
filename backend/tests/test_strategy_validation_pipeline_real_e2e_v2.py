import json

from backend.backtesting.monte_carlo_report_v2 import (
    MonteCarloReportV2,
)
from backend.backtesting.strategy_validation_report_v2 import (
    StrategyValidationReportV2,
)
from backend.backtesting.strategy_validation_pipeline_v2 import (
    StrategyValidationPipelineResultV2,
    StrategyValidationPipelineV2,
)
from backend.backtesting.strategy_validation_result_v2 import (
    StrategyValidationResultV2,
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


def test_real_strategy_validation_pipeline(
    tmp_path,
):

    pipeline = StrategyValidationPipelineV2(
        walk_forward_pipeline=FakeWalkForwardPipeline(),
        monte_carlo_pipeline=FakeMonteCarloPipeline(),
        json_exporter=RealJsonExporter(),
        html_exporter=RealHtmlExporter(),
    )

    result = pipeline.run(
        backtest_score=90.0,
        output_directory=tmp_path,
    )

    assert isinstance(
        result,
        StrategyValidationPipelineResultV2,
    )

    assert isinstance(
        result.validation_result,
        StrategyValidationResultV2,
    )

    assert isinstance(
        result.report,
        StrategyValidationReportV2,
    )

    assert result.json_path.exists()
    assert result.html_path.exists()

    payload = json.loads(
        result.json_path.read_text(
            encoding="utf-8",
        )
    )

    assert payload["summary"]["backtest_score"] == 90.0
    assert payload["summary"]["walk_forward_score"] == 83.0
    assert payload["summary"]["total_simulations"] == 2

    html = result.html_path.read_text(
        encoding="utf-8",
    )

    assert "Strategy Validation Report" in html
    assert "Summary" in html
    assert "Walk Forward" in html
    assert "Monte Carlo" in html
