import pytest

from backend.market_analysis.market_regime_engine import (
    MarketRegimeEngine,
)


def build_engine() -> MarketRegimeEngine:
    return MarketRegimeEngine(
        trend_threshold=0.60,
        high_volatility_threshold=0.80,
        low_volatility_threshold=0.20,
        compression_threshold=0.15,
    )


def test_detects_bullish_trend():
    engine = build_engine()

    result = engine.evaluate(
        directional_strength=0.80,
        volatility_score=0.50,
        compression_score=0.10,
    )

    assert result["regime"] == "TREND_UP"
    assert result["tradable"] is True
    assert result["direction"] == "LONG"
    assert result["confidence"] == 0.80


def test_detects_bearish_trend():
    engine = build_engine()

    result = engine.evaluate(
        directional_strength=-0.75,
        volatility_score=0.50,
        compression_score=0.10,
    )

    assert result["regime"] == "TREND_DOWN"
    assert result["tradable"] is True
    assert result["direction"] == "SHORT"
    assert result["confidence"] == 0.75


def test_detects_range():
    engine = build_engine()

    result = engine.evaluate(
        directional_strength=0.20,
        volatility_score=0.50,
        compression_score=0.10,
    )

    assert result["regime"] == "RANGE"
    assert result["tradable"] is True
    assert result["direction"] == "NEUTRAL"


def test_detects_high_volatility():
    engine = build_engine()

    result = engine.evaluate(
        directional_strength=0.30,
        volatility_score=0.90,
        compression_score=0.10,
    )

    assert result["regime"] == "HIGH_VOLATILITY"
    assert result["tradable"] is True
    assert result["direction"] == "NEUTRAL"
    assert result["risk_multiplier"] == 0.50


def test_detects_low_volatility():
    engine = build_engine()

    result = engine.evaluate(
        directional_strength=0.30,
        volatility_score=0.10,
        compression_score=0.10,
    )

    assert result["regime"] == "LOW_VOLATILITY"
    assert result["tradable"] is False
    assert result["direction"] == "NEUTRAL"


def test_detects_no_trade_during_compression():
    engine = build_engine()

    result = engine.evaluate(
        directional_strength=0.10,
        volatility_score=0.10,
        compression_score=0.90,
    )

    assert result["regime"] == "NO_TRADE"
    assert result["tradable"] is False
    assert result["direction"] == "NEUTRAL"
    assert result["risk_multiplier"] == 0.0


def test_high_volatility_has_priority_over_trend():
    engine = build_engine()

    result = engine.evaluate(
        directional_strength=0.90,
        volatility_score=0.95,
        compression_score=0.10,
    )

    assert result["regime"] == "HIGH_VOLATILITY"


def test_compression_has_highest_priority():
    engine = build_engine()

    result = engine.evaluate(
        directional_strength=0.90,
        volatility_score=0.95,
        compression_score=0.90,
    )

    assert result["regime"] == "NO_TRADE"


def test_confidence_is_between_zero_and_one():
    engine = build_engine()

    result = engine.evaluate(
        directional_strength=-1.0,
        volatility_score=0.50,
        compression_score=0.10,
    )

    assert 0.0 <= result["confidence"] <= 1.0


def test_rejects_invalid_directional_strength():
    engine = build_engine()

    with pytest.raises(
        ValueError,
        match="directional_strength",
    ):
        engine.evaluate(
            directional_strength=1.1,
            volatility_score=0.50,
            compression_score=0.10,
        )


def test_rejects_invalid_volatility_score():
    engine = build_engine()

    with pytest.raises(
        ValueError,
        match="volatility_score",
    ):
        engine.evaluate(
            directional_strength=0.20,
            volatility_score=1.1,
            compression_score=0.10,
        )


def test_rejects_invalid_compression_score():
    engine = build_engine()

    with pytest.raises(
        ValueError,
        match="compression_score",
    ):
        engine.evaluate(
            directional_strength=0.20,
            volatility_score=0.50,
            compression_score=-0.1,
        )


def test_rejects_invalid_trend_threshold():
    with pytest.raises(
        ValueError,
        match="trend_threshold",
    ):
        MarketRegimeEngine(
            trend_threshold=1.1,
            high_volatility_threshold=0.80,
            low_volatility_threshold=0.20,
            compression_threshold=0.15,
        )


def test_rejects_invalid_volatility_threshold_order():
    with pytest.raises(
        ValueError,
        match="volatility",
    ):
        MarketRegimeEngine(
            trend_threshold=0.60,
            high_volatility_threshold=0.20,
            low_volatility_threshold=0.80,
            compression_threshold=0.15,
        )
