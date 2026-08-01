import pytest

from backend.backtesting.backtest_candidate_factory_v2 import (
    BacktestCandidateFactoryV2,
)
from backend.backtesting.backtest_optimizer_v2 import (
    BacktestOptimizerV2,
)
from backend.backtesting.parameter_grid_generator_v2 import (
    ParameterGridGeneratorV2,
)


class FakePipeline:

    def __init__(self, parameters):
        self.parameters = parameters

    def run(
        self,
        *,
        output_directory,
        json_filename="backtest.json",
        html_filename="backtest.html",
    ):
        return None


def pipeline_factory(parameters):
    return FakePipeline(parameters)


class FakeBatchRunner:

    def run(
        self,
        *,
        items,
        output_directory,
    ):
        return {
            "results": items,
        }


class FakeComparisonReport:

    def rank_by_score(
        self,
        scorer,
    ):
        return [
            {
                "name": "EMA50_SL20_TP80",
                "score": 95.2,
                "grade": "A+",
            },
            {
                "name": "EMA20_SL20_TP40",
                "score": 82.0,
                "grade": "A",
            },
        ]


def comparison_factory(batch):
    return FakeComparisonReport()


def test_complete_optimizer_flow(tmp_path):

    grid = ParameterGridGeneratorV2().generate(
        {
            "ema": [20, 50],
            "stop_loss": [20],
            "take_profit": [40, 80],
        }
    )

    candidates = (
        BacktestCandidateFactoryV2(
            pipeline_factory=pipeline_factory,
        ).build(
            parameter_sets=grid,
        )
    )

    assert len(candidates) == 4

    optimizer = BacktestOptimizerV2(
        batch_runner=FakeBatchRunner(),
        comparison_report_factory=comparison_factory,
        scorer=object(),
    )

    result = optimizer.optimize(
        candidates=candidates,
        output_directory=tmp_path,
    )

    assert result.best_strategy()["name"] == (
        "EMA50_SL20_TP80"
    )

    assert result.best_strategy()["grade"] == "A+"

    assert len(result.ranking) == 2
