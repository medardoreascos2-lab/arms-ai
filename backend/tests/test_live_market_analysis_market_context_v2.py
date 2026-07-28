from datetime import datetime
from datetime import timedelta
from datetime import timezone

import pytest

from backend.context.market_context_engine_v2 import (
    MarketContextEngineV2,
)
from backend.intelligence.decision_council_v2 import (
    DecisionCouncilV2,
)
from backend.models.candle import Candle
from backend.services.live_analysis_store import (
    LiveAnalysisStore,
)
from backend.services.live_candle_store import (
    LiveCandleStore,
)
from backend.services.live_market_analysis_service import (
    LiveMarketAnalysisService,
)


def build_candles() -> list[Candle]:
    start = datetime(
        2026,
        7,
        27,
        20,
        0,
        tzinfo=timezone.utc,
    )

    closes = [
        100.0,
        105.0,
        110.0,
        115.0,
        102.0,
    ]

    return [
        Candle(
            symbol="NQ",
            timeframe="5M",
            open=close,
            high=close + 2.0,
            low=close - 2.0,
            close=close,
            volume=1000.0,
            timestamp=(
                start
                + timedelta(
                    minutes=index * 5
                )
            ),
        )
        for index, close in enumerate(
            closes
        )
    ]


def test_live_service_evaluates_market_context_v2():
    service = LiveMarketAnalysisService(
        candle_store=LiveCandleStore(),
        analysis_store=LiveAnalysisStore(),
        market_context_engine_v2=(
            MarketContextEngineV2()
        ),
    )

    result = {
        "trend": "ALCISTA",
        "multi_timeframe_v2": {
            "status": "READY",
            "direction": "BULLISH",
        },
        "smart_money_v2": {
            "structure": {
                "direction": "BULLISH",
            },
        },
    }

    context = (
        service._evaluate_market_context_v2(
            candles=build_candles(),
            result=result,
        )
    )

    assert context["status"] == "READY"
    assert context["context"] == "BUY"
    assert context["price_zone"] == "DISCOUNT"


def test_market_context_conflict_blocks_council():
    service = LiveMarketAnalysisService(
        candle_store=LiveCandleStore(),
        analysis_store=LiveAnalysisStore(),
        decision_council_v2=(
            DecisionCouncilV2()
        ),
    )

    result = {
        "trend": "ALCISTA",
        "market_context_v2": {
            "status": "READY",
            "context": "SELL",
            "context_strength": 0.90,
            "blocking_reasons": [],
        },
        "market_regime": {
            "regime": "TRENDING",
            "tradable": True,
            "confidence": 0.90,
        },
        "probability_v2": {
            "approved": True,
            "probability": 0.90,
            "direction": "BUY",
            "inputs": {
                "trend_score": 0.90,
            },
        },
        "confluence_v2": {
            "approved": True,
            "direction": "BUY",
            "score": 0.90,
            "blocking_reasons": [],
        },
        "execution_v2": {
            "approved": True,
            "status": "READY",
            "decision": "EXECUTE_LONG",
            "direction": "LONG",
            "confidence": 0.90,
            "blocking_reasons": [],
        },
    }

    council = (
        service._evaluate_decision_council_v2(
            result
        )
    )

    assert council["approved"] is False
    assert council["decision"] == "BLOCK"

    assert (
        "market_context_conflict"
        in council["blocking_reasons"]
    )


def test_neutral_market_context_does_not_force_block():
    service = LiveMarketAnalysisService(
        candle_store=LiveCandleStore(),
        analysis_store=LiveAnalysisStore(),
        decision_council_v2=(
            DecisionCouncilV2()
        ),
    )

    result = {
        "trend": "ALCISTA",
        "market_context_v2": {
            "status": "READY",
            "context": "NEUTRAL",
            "context_strength": 0.10,
            "blocking_reasons": [],
        },
        "market_regime": {
            "regime": "TRENDING",
            "tradable": True,
            "confidence": 0.90,
        },
        "probability_v2": {
            "approved": True,
            "probability": 0.90,
            "direction": "BUY",
            "inputs": {
                "trend_score": 0.90,
            },
        },
        "confluence_v2": {
            "approved": True,
            "direction": "BUY",
            "score": 0.90,
            "blocking_reasons": [],
        },
        "execution_v2": {
            "approved": True,
            "status": "READY",
            "decision": "EXECUTE_LONG",
            "direction": "LONG",
            "confidence": 0.90,
            "blocking_reasons": [],
        },
    }

    council = (
        service._evaluate_decision_council_v2(
            result
        )
    )

    assert (
        "market_context_conflict"
        not in council["blocking_reasons"]
    )


def test_live_service_rejects_invalid_market_context():
    with pytest.raises(
        TypeError,
        match="market_context_engine_v2",
    ):
        LiveMarketAnalysisService(
            candle_store=LiveCandleStore(),
            analysis_store=LiveAnalysisStore(),
            market_context_engine_v2=object(),
        )
