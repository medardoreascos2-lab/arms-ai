from pathlib import Path

import pytest

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
from backend.backtesting.monte_carlo_report_v2 import (
    MonteCarloReportV2,
)
from backend.backtesting.monte_carlo_simulator_v2 import (
    MonteCarloSimulationResultV2,
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
                }
            ]
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



class FakeJsonExporter:

    def export(self, *, report, output_path):
        return Path(output_path)


class FakeHtmlExporter:

    def export(self, *, report, output_path):
        return Path(output_path)


def test_runs_complete_strategy_validation_pipeline(tmp_path):

    pipeline = StrategyValidationPipelineV2(
        walk_forward_pipeline=FakeWalkForwardPipeline(),
        monte_carlo_pipeline=FakeMonteCarloPipeline(),
        json_exporter=FakeJsonExporter(),
        html_exporter=FakeHtmlExporter(),
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

    assert result.json_path == (
        tmp_path / "strategy_validation.json"
    )

    assert result.html_path == (
        tmp_path / "strategy_validation.html"
    )

    assert (
        result.validation_result.backtest_score
        == 90.0
    )


def test_supports_custom_filenames(tmp_path):

    pipeline = StrategyValidationPipelineV2(
        walk_forward_pipeline=FakeWalkForwardPipeline(),
        monte_carlo_pipeline=FakeMonteCarloPipeline(),
        json_exporter=FakeJsonExporter(),
        html_exporter=FakeHtmlExporter(),
    )

    result = pipeline.run(
        backtest_score=90.0,
        output_directory=tmp_path,
        json_filename="validation.json",
        html_filename="validation.html",
    )

    assert result.json_path == (
        tmp_path / "validation.json"
    )

    assert result.html_path == (
        tmp_path / "validation.html"
    )


@pytest.mark.parametrize(
    "filename",
    [
        "",
        "   ",
    ],
)
def test_rejects_empty_json_filename(
    filename,
    tmp_path,
):

    pipeline = StrategyValidationPipelineV2(
        walk_forward_pipeline=FakeWalkForwardPipeline(),
        monte_carlo_pipeline=FakeMonteCarloPipeline(),
        json_exporter=FakeJsonExporter(),
        html_exporter=FakeHtmlExporter(),
    )

    with pytest.raises(ValueError):
        pipeline.run(
            backtest_score=90.0,
            output_directory=tmp_path,
            json_filename=filename,
        )


@pytest.mark.parametrize(
    "filename",
    [
        "",
        "   ",
    ],
)
def test_rejects_empty_html_filename(
    filename,
    tmp_path,
):

    pipeline = StrategyValidationPipelineV2(
        walk_forward_pipeline=FakeWalkForwardPipeline(),
        monte_carlo_pipeline=FakeMonteCarloPipeline(),
        json_exporter=FakeJsonExporter(),
        html_exporter=FakeHtmlExporter(),
    )

    with pytest.raises(ValueError):
        pipeline.run(
            backtest_score=90.0,
            output_directory=tmp_path,
            html_filename=filename,
        )
