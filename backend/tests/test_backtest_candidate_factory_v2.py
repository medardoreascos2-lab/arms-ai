import pytest

from backend.backtesting.backtest_candidate_factory_v2 import (
    BacktestCandidateFactoryV2,
)
from backend.backtesting.backtest_optimizer_v2 import (
    BacktestOptimizationCandidateV2,
)


class FakePipeline:

    def run(
        self,
        *,
        output_directory,
        json_filename="backtest.json",
        html_filename="backtest.html",
    ):
        return None


def pipeline_factory(parameters):

    return FakePipeline()


def test_build_candidates():

    factory = BacktestCandidateFactoryV2(
        pipeline_factory=pipeline_factory,
    )

    candidates = factory.build(
        parameter_sets=[
            {
                "ema": 20,
                "stop_loss": 20,
                "take_profit": 40,
            },
            {
                "ema": 50,
                "stop_loss": 30,
                "take_profit": 80,
            },
        ]
    )

    assert len(candidates) == 2

    assert isinstance(
        candidates[0],
        BacktestOptimizationCandidateV2,
    )

    assert candidates[0].name == (
        "EMA20_SL20_TP40"
    )

    assert candidates[1].name == (
        "EMA50_SL30_TP80"
    )


def test_build_empty():

    factory = BacktestCandidateFactoryV2(
        pipeline_factory=pipeline_factory,
    )

    assert factory.build(
        parameter_sets=[]
    ) == []


def test_rejects_invalid_parameter_sets():

    factory = BacktestCandidateFactoryV2(
        pipeline_factory=pipeline_factory,
    )

    with pytest.raises(TypeError):
        factory.build(
            parameter_sets=object(),
        )


def test_rejects_invalid_pipeline_factory():

    with pytest.raises(TypeError):
        BacktestCandidateFactoryV2(
            pipeline_factory=object(),
        )
