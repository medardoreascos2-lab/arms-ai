from backend.config_settings import ArmsSettings
from backend.pipeline.arms_pipeline import ArmsPipeline
from backend.pipeline.pipeline_factory import PipelineFactory
from backend.services.data_collector import DataCollector


def test_pipeline_factory_builds_complete_pipeline():
    settings = ArmsSettings()

    collector = DataCollector(
        provider=settings.provider,
    )

    factory = PipelineFactory(
        settings=settings,
        collector=collector,
    )

    pipeline = factory.create()

    assert isinstance(pipeline, ArmsPipeline)
    assert len(pipeline.stages) == 9

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


def test_pipeline_factory_uses_settings_values():
    settings = ArmsSettings(
        symbol="ES",
        timeframe="5m",
        candle_limit=60,
        max_candles=200,
        account_balance=25000,
        risk_percent=1.0,
    )

    collector = DataCollector(
        provider=settings.provider,
    )

    pipeline = PipelineFactory(
        settings=settings,
        collector=collector,
    ).create()

    market_stage = pipeline.stages[0]
    risk_stage = pipeline.stages[4]

    assert market_stage.symbol == "ES"
    assert market_stage.timeframe == "5m"
    assert market_stage.candle_limit == 60
    assert market_stage.max_candles == 200

    assert risk_stage.account_balance == 25000
    assert risk_stage.risk_percent == 1.0


import pytest

from backend.pipeline.pipeline_mode import PipelineMode


def test_pipeline_factory_builds_simulation_mode():
    settings = ArmsSettings()
    collector = DataCollector(provider=settings.provider)

    pipeline = PipelineFactory(
        settings=settings,
        collector=collector,
    ).create(mode=PipelineMode.SIMULATION)

    assert isinstance(pipeline, ArmsPipeline)
    assert len(pipeline.stages) == 9


@pytest.mark.parametrize(
    "mode",
    [
        PipelineMode.BACKTEST,
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
