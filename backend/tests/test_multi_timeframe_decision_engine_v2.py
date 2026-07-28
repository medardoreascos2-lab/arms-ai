import pytest

from backend.intelligence.multi_timeframe_decision_engine_v2 import (
    MultiTimeframeDecisionEngineV2,
)


class FakeTrendEngine:
    def __init__(
        self,
        results,
    ):
        self.results = results
        self.calls = []

    def analyze(
        self,
        *,
        symbol,
        timeframe,
    ):
        self.calls.append(
            (
                symbol,
                timeframe,
            )
        )

        return dict(
            self.results[
                timeframe
            ]
        )


def build_engine(
    results,
    **kwargs,
):
    return MultiTimeframeDecisionEngineV2(
        trend_engine=FakeTrendEngine(
            results
        ),
        **kwargs,
    )


def bullish_result(
    confidence=0.90,
):
    return {
        "status": "READY",
        "direction": "BULLISH",
        "confidence": confidence,
    }


def bearish_result(
    confidence=0.90,
):
    return {
        "status": "READY",
        "direction": "BEARISH",
        "confidence": confidence,
    }


def sideways_result(
    confidence=0.90,
):
    return {
        "status": "READY",
        "direction": "SIDEWAYS",
        "confidence": confidence,
    }


def insufficient_result():
    return {
        "status": "INSUFFICIENT_DATA",
        "direction": (
            "INSUFFICIENT_DATA"
        ),
        "confidence": 0.0,
    }


def test_detects_full_bullish_alignment():
    result = build_engine(
        {
            "1M": bullish_result(),
            "5M": bullish_result(),
            "15M": bullish_result(),
            "1H": bullish_result(),
        }
    ).analyze(
        symbol="NQ"
    )

    assert result["status"] == "READY"
    assert result["direction"] == "BULLISH"
    assert result["confidence"] == pytest.approx(
        0.90
    )
    assert result["bullish_weight"] == 1.0
    assert result["aligned_timeframes"] == [
        "1M",
        "5M",
        "15M",
        "1H",
    ]
    assert result["blocking_reasons"] == []


def test_detects_full_bearish_alignment():
    result = build_engine(
        {
            "1M": bearish_result(),
            "5M": bearish_result(),
            "15M": bearish_result(),
            "1H": bearish_result(),
        }
    ).analyze(
        symbol="NQ"
    )

    assert result["direction"] == "BEARISH"
    assert result["weighted_score"] < 0
    assert result["bearish_weight"] == 1.0


def test_higher_timeframes_dominate_noise():
    result = build_engine(
        {
            "1M": bearish_result(),
            "5M": bullish_result(),
            "15M": bullish_result(),
            "1H": bullish_result(),
        }
    ).analyze(
        symbol="NQ"
    )

    assert result["direction"] == "BULLISH"
    assert result["bullish_weight"] == 0.90
    assert result["bearish_weight"] == 0.10
    assert result["conflicting_timeframes"] == [
        "1M"
    ]


def test_detects_directional_conflict():
    result = build_engine(
        {
            "1M": bullish_result(),
            "5M": bullish_result(),
            "15M": bearish_result(),
            "1H": bearish_result(),
        }
    ).analyze(
        symbol="NQ"
    )

    assert result["direction"] == "CONFLICT"
    assert (
        "timeframe_direction_conflict"
        in result["blocking_reasons"]
    )
    assert set(
        result[
            "conflicting_timeframes"
        ]
    ) == {
        "1M",
        "5M",
        "15M",
        "1H",
    }


def test_detects_neutral_market():
    result = build_engine(
        {
            "1M": sideways_result(),
            "5M": sideways_result(),
            "15M": sideways_result(),
            "1H": sideways_result(),
        }
    ).analyze(
        symbol="NQ"
    )

    assert result["direction"] == "NEUTRAL"
    assert result["confidence"] == 1.0
    assert result["sideways_weight"] == 1.0


def test_returns_insufficient_data():
    result = build_engine(
        {
            "1M": bullish_result(),
            "5M": insufficient_result(),
            "15M": insufficient_result(),
            "1H": insufficient_result(),
        }
    ).analyze(
        symbol="NQ"
    )

    assert (
        result["status"]
        == "INSUFFICIENT_DATA"
    )
    assert (
        result["direction"]
        == "INSUFFICIENT_DATA"
    )
    assert result["ready_weight"] == 0.10
    assert (
        "insufficient_timeframe_data"
        in result["blocking_reasons"]
    )


def test_can_analyze_with_partial_data():
    result = build_engine(
        {
            "1M": insufficient_result(),
            "5M": bullish_result(),
            "15M": bullish_result(),
            "1H": bullish_result(),
        }
    ).analyze(
        symbol="NQ"
    )

    assert result["status"] == "READY"
    assert result["direction"] == "BULLISH"
    assert result["ready_weight"] == 0.90
    assert result[
        "insufficient_timeframes"
    ] == [
        "1M"
    ]


def test_normalizes_percentage_confidence():
    result = build_engine(
        {
            "1M": bullish_result(90.0),
            "5M": bullish_result(90.0),
            "15M": bullish_result(90.0),
            "1H": bullish_result(90.0),
        }
    ).analyze(
        symbol="NQ"
    )

    assert result["confidence"] == 0.90


def test_normalizes_symbol():
    fake = FakeTrendEngine(
        {
            "1M": bullish_result(),
            "5M": bullish_result(),
            "15M": bullish_result(),
            "1H": bullish_result(),
        }
    )

    engine = (
        MultiTimeframeDecisionEngineV2(
            trend_engine=fake
        )
    )

    result = engine.analyze(
        symbol=" nq "
    )

    assert result["symbol"] == "NQ"

    assert fake.calls[0] == (
        "NQ",
        "1M",
    )


def test_normalizes_custom_weights():
    engine = build_engine(
        {
            "5M": bullish_result(),
            "1H": bullish_result(),
        },
        timeframe_weights={
            "5m": 1.0,
            "1h": 3.0,
        },
        minimum_ready_weight=1.0,
    )

    assert engine.timeframe_weights == {
        "5M": 0.25,
        "1H": 0.75,
    }


def test_rejects_invalid_trend_engine():
    with pytest.raises(
        TypeError,
        match="trend_engine",
    ):
        MultiTimeframeDecisionEngineV2(
            trend_engine=object()
        )


def test_rejects_empty_symbol():
    engine = build_engine(
        {
            "1M": bullish_result(),
            "5M": bullish_result(),
            "15M": bullish_result(),
            "1H": bullish_result(),
        }
    )

    with pytest.raises(
        ValueError,
        match="symbol",
    ):
        engine.analyze(
            symbol=" "
        )


def test_rejects_invalid_weights():
    with pytest.raises(
        ValueError,
        match="pesos",
    ):
        MultiTimeframeDecisionEngineV2(
            trend_engine=FakeTrendEngine(
                {}
            ),
            timeframe_weights={
                "1M": 0.0,
                "5M": 1.0,
            },
        )


def test_rejects_invalid_confidence():
    engine = build_engine(
        {
            "1M": bullish_result(101.0),
            "5M": bullish_result(),
            "15M": bullish_result(),
            "1H": bullish_result(),
        }
    )

    with pytest.raises(
        ValueError,
        match="confianza",
    ):
        engine.analyze(
            symbol="NQ"
        )
