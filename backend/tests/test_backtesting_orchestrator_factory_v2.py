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


def test_validation_adapter_forwards_empirical_evidence_v17(
    tmp_path,
):
    """V17: certification must consume the current empirical dataset."""

    from backend.backtesting.backtesting_orchestrator_factory_v2 import (
        ValidationPipelineExecutionAdapterV2,
    )

    class CaptureValidationPipeline:

        def __init__(self):
            self.received = None

        def run(self, **kwargs):
            self.received = dict(kwargs)
            return object()

    validation_pipeline = CaptureValidationPipeline()

    items = [
        {"close": 100.0},
        {"close": 101.0},
    ]

    parameter_sets = [
        {
            "ema": 5,
            "stop_loss": 30,
            "take_profit": 60,
        }
    ]

    trade_pnls = [
        125.0,
        -25.0,
        200.0,
    ]

    adapter = ValidationPipelineExecutionAdapterV2(
        validation_pipeline=validation_pipeline,
        backtest_score=94.0,
        output_directory=tmp_path,
        items=items,
        parameter_sets=parameter_sets,
        trade_pnls=trade_pnls,
        starting_balance=17000.0,
    )

    adapter.run()

    assert validation_pipeline.received == {
        "backtest_score": 94.0,
        "output_directory": tmp_path,
        "items": items,
        "parameter_sets": parameter_sets,
        "trade_pnls": trade_pnls,
        "starting_balance": 17000.0,
    }
