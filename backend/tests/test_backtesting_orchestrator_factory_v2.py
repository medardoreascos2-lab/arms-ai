import pytest

from backend.backtesting.backtest_composite_score_v2 import (
    BacktestCompositeScoreV2,
)
from backend.backtesting.backtest_engine import (
    BacktestEngine,
)
from backend.backtesting.backtesting_orchestrator_factory_v2 import (
    create_backtesting_orchestrator_v2,
)
from backend.backtesting.backtesting_orchestrator_v2 import (
    BacktestingOrchestratorV2,
)
from backend.backtesting.strategy_certification_pipeline_v2 import (
    StrategyCertificationPipelineV2,
)
from backend.config_settings import (
    ArmsSettings,
)


class FakeWalkForwardAdapter:

    def run(self):

        return None


class FakeMonteCarloAdapter:

    def run(self):

        return None


def build_orchestrator():

    return create_backtesting_orchestrator_v2(
        settings=ArmsSettings(),
        walk_forward_pipeline=(
            FakeWalkForwardAdapter()
        ),
        monte_carlo_pipeline=(
            FakeMonteCarloAdapter()
        ),
    )


def test_factory_creates_orchestrator():

    orchestrator = build_orchestrator()

    assert isinstance(
        orchestrator,
        BacktestingOrchestratorV2,
    )


def test_orchestrator_exposes_real_dependencies():

    orchestrator = build_orchestrator()

    assert isinstance(
        orchestrator.backtest_engine,
        BacktestEngine,
    )

    assert isinstance(
        orchestrator.score_engine,
        BacktestCompositeScoreV2,
    )

    assert callable(
        orchestrator
        .certification_pipeline_factory
    )


def test_certification_factory_builds_pipeline(
    tmp_path,
):

    orchestrator = build_orchestrator()

    pipeline = (
        orchestrator
        .certification_pipeline_factory(
            backtest_score=88.0,
            output_directory=tmp_path,
        )
    )

    assert isinstance(
        pipeline,
        StrategyCertificationPipelineV2,
    )

    assert callable(
        pipeline.validation_pipeline.run
    )


def test_uses_default_settings():

    orchestrator = (
        create_backtesting_orchestrator_v2(
            walk_forward_pipeline=(
                FakeWalkForwardAdapter()
            ),
            monte_carlo_pipeline=(
                FakeMonteCarloAdapter()
            ),
        )
    )

    assert isinstance(
        orchestrator.backtest_engine,
        BacktestEngine,
    )


def test_rejects_invalid_settings():

    with pytest.raises(
        TypeError,
        match="settings",
    ):
        create_backtesting_orchestrator_v2(
            settings=object(),
            walk_forward_pipeline=(
                FakeWalkForwardAdapter()
            ),
            monte_carlo_pipeline=(
                FakeMonteCarloAdapter()
            ),
        )


def test_rejects_invalid_walk_forward_pipeline():

    with pytest.raises(
        TypeError,
        match="walk_forward_pipeline",
    ):
        create_backtesting_orchestrator_v2(
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
        create_backtesting_orchestrator_v2(
            walk_forward_pipeline=(
                FakeWalkForwardAdapter()
            ),
            monte_carlo_pipeline=object(),
        )
