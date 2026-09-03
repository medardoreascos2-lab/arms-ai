from __future__ import annotations

from types import SimpleNamespace

import pytest

from backend.intelligence.confluence_engine_v2 import (
    ConfluenceEngineV2,
)
from backend.services.live_market_analysis_service import (
    LiveMarketAnalysisService,
)


def _candle(
    volume: float = 100.0,
) -> SimpleNamespace:
    return SimpleNamespace(
        open=100.0,
        high=101.0,
        low=99.0,
        close=100.0,
        volume=volume,
    )


def _service() -> LiveMarketAnalysisService:
    service = object.__new__(
        LiveMarketAnalysisService
    )

    service.confluence_engine_v2 = (
        ConfluenceEngineV2()
    )

    service.smart_money_engine_v2 = None

    service._evaluate_smart_money_v2 = (
        lambda candles: {
            "structure": {
                "bos": False,
                "choch": False,
                "direction": "RANGE",
            },
            "liquidity": {
                "liquidity_sweep": False,
                "equal_highs": False,
                "equal_lows": False,
                "liquidity_type": "NONE",
            },
            "fvg": {
                "fvg": False,
                "direction": "NONE",
            },
            "order_block": {
                "order_block": False,
                "direction": "NONE",
            },
        }
    )

    return service


def _result() -> dict[str, object]:
    return {
        "trend": {
            "direction": "SIDEWAYS",
        },
        "ema_alignment": {
            "direction": "SIDEWAYS",
        },
        "probability": 0.50,
        "risk_approved": True,
        "sizing_approved": True,
    }


def _regime_contribution(
    regime: dict[str, object],
) -> float:
    service = _service()

    candles = [
        _candle()
        for _ in range(20)
    ]

    confluence = (
        service._evaluate_confluence_v2(
            result=_result(),
            candles=candles,
            market_regime_result=regime,
            risk_approved=True,
            sizing_approved=True,
        )
    )

    return (
        service
        ._calculate_market_regime_quality_score(
            regime
        )
    )


@pytest.mark.parametrize(
    (
        "regime",
        "expected_quality",
    ),
    [
        (
            {
                "regime": "TREND_UP",
                "tradable": True,
                "direction": "LONG",
                "confidence": 0.90,
                "risk_multiplier": 1.0,
            },
            0.90,
        ),
        (
            {
                "regime": "TREND_DOWN",
                "tradable": True,
                "direction": "SHORT",
                "confidence": 0.90,
                "risk_multiplier": 1.0,
            },
            0.90,
        ),
        (
            {
                "regime": "RANGE",
                "tradable": True,
                "direction": "NEUTRAL",
                "confidence": 0.90,
                "risk_multiplier": 0.75,
            },
            0.50,
        ),
        (
            {
                "regime": "HIGH_VOLATILITY",
                "tradable": True,
                "direction": "NEUTRAL",
                "confidence": 0.90,
                "risk_multiplier": 0.50,
            },
            0.50,
        ),
        (
            {
                "regime": "LOW_VOLATILITY",
                "tradable": False,
                "direction": "NEUTRAL",
                "confidence": 0.90,
                "risk_multiplier": 0.0,
            },
            0.0,
        ),
        (
            {
                "regime": "NO_TRADE",
                "tradable": False,
                "direction": "NEUTRAL",
                "confidence": 0.90,
                "risk_multiplier": 0.0,
            },
            0.0,
        ),
    ],
)
def test_market_regime_quality_is_not_classifier_confidence(
    regime: dict[str, object],
    expected_quality: float,
) -> None:
    actual = _regime_contribution(
        regime
    )

    assert actual == pytest.approx(
        expected_quality,
        abs=1e-4,
    )


def test_high_confidence_trend_scores_above_high_confidence_range(
) -> None:
    trend_quality = _regime_contribution(
        {
            "regime": "TREND_UP",
            "tradable": True,
            "direction": "LONG",
            "confidence": 0.90,
            "risk_multiplier": 1.0,
        }
    )

    range_quality = _regime_contribution(
        {
            "regime": "RANGE",
            "tradable": True,
            "direction": "NEUTRAL",
            "confidence": 0.90,
            "risk_multiplier": 0.75,
        }
    )

    assert trend_quality > range_quality


def test_high_confidence_trend_scores_above_high_volatility(
) -> None:
    trend_quality = _regime_contribution(
        {
            "regime": "TREND_DOWN",
            "tradable": True,
            "direction": "SHORT",
            "confidence": 0.90,
            "risk_multiplier": 1.0,
        }
    )

    volatility_quality = (
        _regime_contribution(
            {
                "regime": "HIGH_VOLATILITY",
                "tradable": True,
                "direction": "NEUTRAL",
                "confidence": 0.90,
                "risk_multiplier": 0.50,
            }
        )
    )

    assert (
        trend_quality
        > volatility_quality
    )
