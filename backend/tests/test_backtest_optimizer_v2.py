import pytest

from backend.backtesting.backtest_optimizer_v2 import (
    BacktestOptimizationCandidateV2,
    BacktestOptimizationResultV2,
    BacktestOptimizerV2,
)


class FakeBatchRunner:

    def __init__(self):
        self.calls = []

    def run(
        self,
        *,
        items,
        output_directory,
    ):
        self.calls.append(
            {
                "items": items,
                "output_directory": output_directory,
            }
        )

        return {
            "results": items,
        }



class FakePipeline:

    def run(
        self,
        *,
        output_directory,
        json_filename="backtest.json",
        html_filename="backtest.html",
    ):
        return None


class FakeComparisonReport:

    def __init__(self):
        self.calls = 0

    def rank_by_score(
        self,
        scorer,
    ):
        self.calls += 1

        return [
            {
                "name": "EMA50",
                "score": 94.5,
                "grade": "A+",
            },
            {
                "name": "EMA20",
                "score": 88.1,
                "grade": "A",
            },
        ]


def test_candidate_requires_name():

    with pytest.raises(ValueError):
        BacktestOptimizationCandidateV2(
            name="",
            pipeline=FakePipeline(),
        )


def test_result_contains_best_strategy():

    result = BacktestOptimizationResultV2(
        ranking=[
            {
                "name": "EMA50",
                "score": 95.0,
            },
            {
                "name": "EMA20",
                "score": 80.0,
            },
        ]
    )

    assert result.best_strategy()["name"] == "EMA50"


def test_optimizer_returns_ranking(
    tmp_path,
):

    optimizer = BacktestOptimizerV2(
        batch_runner=FakeBatchRunner(),
        comparison_report_factory=(
            lambda batch: FakeComparisonReport()
        ),
        scorer=object(),
    )

    result = optimizer.optimize(
        candidates=[
            BacktestOptimizationCandidateV2(
                name="EMA20",
                pipeline=FakePipeline(),
            ),
            BacktestOptimizationCandidateV2(
                name="EMA50",
                pipeline=FakePipeline(),
            ),
        ],
        output_directory=tmp_path,
    )

    assert result.best_strategy()["name"] == "EMA50"
    assert len(result.ranking) == 2
