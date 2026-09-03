from __future__ import annotations

from types import SimpleNamespace

from backend.intelligence.confluence_engine_v2 import (
    ConfluenceEngineV2,
)
from backend.services.live_market_analysis_service import (
    LiveMarketAnalysisService,
)


class RecordingConfluenceEngineV2(
    ConfluenceEngineV2
):
    def __init__(self) -> None:
        self.last_inputs = None

    def evaluate(
        self,
        **kwargs,
    ):
        self.last_inputs = dict(kwargs)

        return {
            "score": 90.0,
            "grade": "A+",
            "approved": True,
            "status": "APPROVED",
            "blocking_reasons": [],
        }


def build_service():
    engine = RecordingConfluenceEngineV2()

    service = object.__new__(
        LiveMarketAnalysisService
    )

    service.confluence_engine_v2 = engine
    service.smart_money_engine_v2 = None

    return service, engine


def base_result():
    return {
        "trend": {
            "direction": "ALCISTA",
        },
        "structure": {
            "direction": "ALCISTA",
        },
        "probability": 0.95,
    }


def evaluate(
    *,
    trend_direction: str,
    ema_direction: str,
):
    service, engine = build_service()

    result = base_result()

    result["trend"] = {
        "direction": trend_direction,
    }

    result["ema_alignment"] = {
        "direction": ema_direction,
    }

    candles = [
        SimpleNamespace(
            volume=100.0,
        ),
        SimpleNamespace(
            volume=100.0,
        ),
        SimpleNamespace(
            volume=100.0,
        ),
    ]

    service._evaluate_confluence_v2(
        result=result,
        candles=candles,
        risk_approved=True,
        sizing_approved=True,
        market_regime_result=None,
    )

    assert engine.last_inputs is not None

    return engine.last_inputs[
        "ema_alignment_score"
    ]


def test_bullish_ema_aligned_with_bullish_trend_scores_full():
    assert evaluate(
        trend_direction="ALCISTA",
        ema_direction="BULLISH",
    ) == 1.0


def test_bearish_ema_aligned_with_bearish_trend_scores_full():
    assert evaluate(
        trend_direction="BAJISTA",
        ema_direction="BEARISH",
    ) == 1.0


def test_bearish_ema_opposed_to_bullish_trend_scores_zero():
    assert evaluate(
        trend_direction="ALCISTA",
        ema_direction="BEARISH",
    ) == 0.0


def test_bullish_ema_opposed_to_bearish_trend_scores_zero():
    assert evaluate(
        trend_direction="BAJISTA",
        ema_direction="BULLISH",
    ) == 0.0


def test_sideways_ema_preserves_neutral_baseline():
    assert evaluate(
        trend_direction="ALCISTA",
        ema_direction="SIDEWAYS",
    ) == 0.50


def test_missing_ema_preserves_neutral_baseline():
    service, engine = build_service()

    result = base_result()

    candles = [
        SimpleNamespace(volume=100.0),
        SimpleNamespace(volume=100.0),
        SimpleNamespace(volume=100.0),
    ]

    service._evaluate_confluence_v2(
        result=result,
        candles=candles,
        risk_approved=True,
        sizing_approved=True,
        market_regime_result=None,
    )

    assert engine.last_inputs is not None

    assert (
        engine.last_inputs[
            "ema_alignment_score"
        ]
        == 0.50
    )
