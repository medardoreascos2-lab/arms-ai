import pytest

from backend.pipeline.market_stage import MarketStage
from backend.pipeline.smart_money_stage import SmartMoneyStage
from backend.services.data_collector import DataCollector


def build_market_context(limit: int = 100):
    collector = DataCollector(provider="SIMULATED")

    stage = MarketStage(
        collector=collector,
        symbol="NASDAQ / NQ",
        timeframe="1m",
        candle_limit=limit,
        max_candles=500,
    )

    return stage.run({})


def test_smart_money_stage_adds_all_components():
    context = build_market_context()

    stage = SmartMoneyStage(
        liquidity_tolerance=1.0,
    )

    result = stage.run(context)

    assert "market_structure" in result
    assert "bos" in result
    assert "choch" in result
    assert "liquidity" in result

    assert result["market_structure"].structure is not None
    assert result["bos"].bos is not None
    assert result["bos"].direction is not None
    assert result["choch"].choch is not None
    assert result["choch"].direction is not None
    assert result["liquidity"].sweep_detected is not None
    assert result["liquidity"].sweep_direction is not None


def test_smart_money_stage_preserves_existing_context():
    context = build_market_context()
    context["session_allowed"] = True

    stage = SmartMoneyStage()

    result = stage.run(context)

    assert result["session_allowed"] is True
    assert result["latest_candle"] is not None
    assert result["current_price"] == result["latest_candle"].close


def test_smart_money_stage_requires_candles():
    stage = SmartMoneyStage()

    with pytest.raises(
        KeyError,
        match="candles",
    ):
        stage.run({})
