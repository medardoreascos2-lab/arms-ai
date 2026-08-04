import pytest

from backend.backtesting.strategy_validation_pipeline_v2 import (
    StrategyValidationPipelineV2,
)
from backend.backtesting.validation_pipeline_factory_v2 import (
    create_validation_pipeline_v2,
)


class FakeWalkForwardAdapter:

    def run(self):

        return None


class FakeMonteCarloAdapter:

    def run(self):

        return None


def build_pipeline():

    return create_validation_pipeline_v2(
        walk_forward_pipeline=(
            FakeWalkForwardAdapter()
        ),
        monte_carlo_pipeline=(
            FakeMonteCarloAdapter()
        ),
    )


def test_factory_creates_pipeline():

    pipeline = build_pipeline()

    assert isinstance(
        pipeline,
        StrategyValidationPipelineV2,
    )


def test_pipeline_exposes_components():

    pipeline = build_pipeline()

    assert callable(
        pipeline.walk_forward_pipeline.run
    )

    assert callable(
        pipeline.monte_carlo_pipeline.run
    )

    assert callable(
        pipeline.json_exporter.export
    )

    assert callable(
        pipeline.html_exporter.export
    )


def test_rejects_invalid_walk_forward_pipeline():

    with pytest.raises(
        TypeError,
        match="walk_forward_pipeline",
    ):
        create_validation_pipeline_v2(
            walk_forward_pipeline=object(),
            monte_carlo_pipeline=(
                FakeMonteCarloAdapter()
            ),
        )


def test_rejects_invalid_monte_carlo_pipeline():

    with pytest.raises(
        TypeError,
        match="monte_carlo_pipeline",
    ):
        create_validation_pipeline_v2(
            walk_forward_pipeline=(
                FakeWalkForwardAdapter()
            ),
            monte_carlo_pipeline=object(),
        )
