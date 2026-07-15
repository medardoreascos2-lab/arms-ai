import pytest

from backend.config_settings import ArmsSettings
from backend.pipeline.pipeline_factory import PipelineFactory
from backend.pipeline.pipeline_mode import PipelineMode
from backend.services.data_collector import DataCollector


def test_pipeline_factory_builds_pipeline():
    settings = ArmsSettings()
    collector = DataCollector(provider=settings.provider)

    pipeline = PipelineFactory(
        settings=settings,
        collector=collector,
    ).create()

    assert pipeline is not None
    assert len(pipeline.stages) == 9


def test_pipeline_factory_stage_order():
    settings = ArmsSettings()
    collector = DataCollector(provider=settings.provider)

    pipeline = PipelineFactory(
        settings=settings,
        collector=collector,
    ).create()

    stage_names = [
        stage.__class__.__name__
        for stage in pipeline.stages
    ]

    assert stage_names == [
        "MarketStage",
        "IndicatorStage",
        "SmartMoneyStage",
        "IntelligenceStage",
        "RiskStage",
        "DecisionStage",
        "TradePlanStage",
        "ExecutionStage",
        "ReportingStage",
    ]


def test_pipeline_factory_builds_simulation_mode():
    settings = ArmsSettings()
    collector = DataCollector(provider=settings.provider)

    pipeline = PipelineFactory(
        settings=settings,
        collector=collector,
    ).create(
        mode=PipelineMode.SIMULATION,
    )

    assert pipeline is not None

    stage_names = [
        stage.__class__.__name__
        for stage in pipeline.stages
    ]

    assert stage_names[0] == "MarketStage"
    assert stage_names[-1] == "ReportingStage"


@pytest.mark.parametrize(
    "mode",
    [
        PipelineMode.PAPER,
        PipelineMode.LIVE,
    ],
)
def test_pipeline_factory_rejects_unimplemented_modes(mode):
    settings = ArmsSettings()
    collector = DataCollector(provider=settings.provider)

    factory = PipelineFactory(
        settings=settings,
        collector=collector,
    )

    with pytest.raises(
        NotImplementedError,
        match=mode.value,
    ):
        factory.create(mode=mode)


def test_pipeline_factory_builds_backtest_pipeline_without_collector():
    settings = ArmsSettings()

    pipeline = PipelineFactory(
        settings=settings,
        collector=None,
    ).create(
        mode=PipelineMode.BACKTEST,
    )

    stage_names = [
        stage.__class__.__name__
        for stage in pipeline.stages
    ]

    assert stage_names == [
        "BacktestMarketStage",
        "IndicatorStage",
        "SmartMoneyStage",
        "IntelligenceStage",
        "RiskStage",
        "DecisionStage",
        "TradePlanStage",
    ]


def test_backtest_pipeline_does_not_execute_or_report():
    settings = ArmsSettings()

    pipeline = PipelineFactory(
        settings=settings,
        collector=None,
    ).create(
        mode=PipelineMode.BACKTEST,
    )

    stage_names = {
        stage.__class__.__name__
        for stage in pipeline.stages
    }

    assert "MarketStage" not in stage_names
    assert "ExecutionStage" not in stage_names
    assert "ReportingStage" not in stage_names


def test_simulation_pipeline_requires_collector():
    settings = ArmsSettings()

    factory = PipelineFactory(
        settings=settings,
        collector=None,
    )

    with pytest.raises(
        ValueError,
        match="collector",
    ):
        factory.create(
            mode=PipelineMode.SIMULATION,
        )
