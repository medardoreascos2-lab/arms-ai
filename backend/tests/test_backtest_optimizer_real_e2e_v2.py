from pathlib import Path

from backend.backtesting.backtest_batch_runner_v2 import (
    BacktestBatchRunnerV2,
)
from backend.backtesting.backtest_candidate_factory_v2 import (
    BacktestCandidateFactoryV2,
)
from backend.backtesting.backtest_comparison_report_v2 import (
    BacktestComparisonReportV2,
)
from backend.backtesting.backtest_composite_score_v2 import (
    BacktestCompositeScoreV2,
)
from backend.backtesting.backtest_optimizer_v2 import (
    BacktestOptimizerV2,
)
from backend.backtesting.backtest_pipeline_v2 import (
    BacktestPipelineResultV2,
)
from backend.backtesting.backtest_report_v2 import (
    BacktestReportV2,
)
from backend.backtesting.parameter_grid_generator_v2 import (
    ParameterGridGeneratorV2,
)


class ParameterizedPipelineV2:

    def __init__(
        self,
        parameters,
    ) -> None:

        self.parameters = dict(
            parameters
        )

    def run(
        self,
        *,
        output_directory,
        json_filename="backtest.json",
        html_filename="backtest.html",
    ) -> BacktestPipelineResultV2:

        ema = int(
            self.parameters["ema"]
        )

        if ema == 50:
            metrics = {
                "total_trades": 20,
                "net_pnl": 1200.0,
                "win_rate": 0.70,
                "profit_factor": 2.40,
                "expectancy": 100.0,
                "maximum_drawdown": 150.0,
            }
        else:
            metrics = {
                "total_trades": 20,
                "net_pnl": 350.0,
                "win_rate": 0.55,
                "profit_factor": 1.30,
                "expectancy": 20.0,
                "maximum_drawdown": 350.0,
            }

        report = BacktestReportV2(
            candles_processed=500,
            trade_history=[
                {
                    "trade_id": (
                        f"{ema}-{index + 1}"
                    ),
                }
                for index in range(
                    metrics["total_trades"]
                )
            ],
            performance_metrics=metrics,
        )

        normalized_output_directory = Path(
            output_directory
        )

        return BacktestPipelineResultV2(
            candles_processed=500,
            report=report,
            json_path=(
                normalized_output_directory
                / json_filename
            ),
            html_path=(
                normalized_output_directory
                / html_filename
            ),
        )


def pipeline_factory(
    parameters,
):

    return ParameterizedPipelineV2(
        parameters
    )


def comparison_factory(
    batch_result,
):

    return (
        BacktestComparisonReportV2
        .from_batch_result(
            batch_result
        )
    )


def test_optimizer_real_components_select_best_parameters(
    tmp_path,
):

    grid = ParameterGridGeneratorV2().generate(
        {
            "ema": [
                20,
                50,
            ],
            "stop_loss": [
                20,
            ],
            "take_profit": [
                40,
            ],
        }
    )

    candidates = (
        BacktestCandidateFactoryV2(
            pipeline_factory=pipeline_factory,
        ).build(
            parameter_sets=grid,
        )
    )

    optimizer = BacktestOptimizerV2(
        batch_runner=BacktestBatchRunnerV2(
            continue_on_error=False,
        ),
        comparison_report_factory=(
            comparison_factory
        ),
        scorer=BacktestCompositeScoreV2(
            minimum_trades=10,
        ),
    )

    result = optimizer.optimize(
        candidates=candidates,
        output_directory=tmp_path,
    )

    assert len(result.ranking) == 2

    best = result.best_strategy()

    assert best["name"] == (
        "EMA50_SL20_TP40"
    )

    assert best["parameters"] == {
        "ema": 50,
        "stop_loss": 20,
        "take_profit": 40,
    }

    assert best["score"] >= 80.0

    assert best["grade"] in {
        "A",
        "A+",
    }

    assert (
        result.ranking[0]["score"]
        > result.ranking[1]["score"]
    )

    assert (
        result.ranking[1]["name"]
        == "EMA20_SL20_TP40"
    )

    assert (
        result.batch_result.total_runs
        == 2
    )

    assert (
        result.batch_result.successful_runs
        == 2
    )

    assert (
        result.batch_result.failed_runs
        == 0
    )
