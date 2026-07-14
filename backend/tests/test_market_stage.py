from backend.pipeline.market_stage import MarketStage
from backend.services.data_collector import DataCollector


def test_market_stage_populates_market_context():
    collector = DataCollector(provider="SIMULATED")

    stage = MarketStage(
        collector=collector,
        symbol="NASDAQ / NQ",
        timeframe="1m",
        candle_limit=100,
        max_candles=500,
    )

    result = stage.run({})

    assert "candles" in result
    assert "candle_manager" in result
    assert "latest_candle" in result
    assert "current_price" in result
    assert "current_volume" in result
    assert "market" in result
    assert "feed" in result

    assert len(result["candles"]) == 100
    assert result["latest_candle"] is not None
    assert result["current_price"] == result["latest_candle"].close
    assert result["current_volume"] == result["latest_candle"].volume


def test_market_stage_preserves_existing_context():
    collector = DataCollector(provider="SIMULATED")

    stage = MarketStage(
        collector=collector,
        symbol="NASDAQ / NQ",
        timeframe="1m",
        candle_limit=20,
        max_candles=100,
    )

    result = stage.run({"session_allowed": True})

    assert result["session_allowed"] is True
    assert len(result["candles"]) == 20
