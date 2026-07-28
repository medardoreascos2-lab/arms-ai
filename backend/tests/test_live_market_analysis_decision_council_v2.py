from backend.intelligence.decision_council_v2 import (
    DecisionCouncilV2,
)
from backend.services.live_analysis_store import (
    LiveAnalysisStore,
)
from backend.services.live_candle_store import (
    LiveCandleStore,
)
from backend.services.live_market_analysis_service import (
    LiveMarketAnalysisService,
)


def test_live_analysis_evaluates_decision_council_v2():
    service = LiveMarketAnalysisService(
        candle_store=LiveCandleStore(),
        analysis_store=LiveAnalysisStore(),
        decision_council_v2=(
            DecisionCouncilV2()
        ),
    )

    result = {
        "trend": "ALCISTA",
        "market_regime": {
            "regime": "TRENDING",
            "tradable": True,
            "confidence": 0.85,
        },
        "probability_v2": {
            "approved": True,
            "probability": 0.90,
            "inputs": {
                "trend_score": 0.92,
            },
        },
        "confluence_v2": {
            "approved": True,
            "status": "APPROVED",
            "score": 0.93,
            "blocking_reasons": [],
        },
        "execution_v2": {
            "approved": True,
            "status": "READY",
            "decision": "EXECUTE_LONG",
            "direction": "LONG",
            "confidence": 0.91,
            "blocking_reasons": [],
        },
    }

    council_result = (
        service._evaluate_decision_council_v2(
            result
        )
    )

    assert council_result["approved"] is True
    assert (
        council_result["decision"]
        == "EXECUTE_LONG"
    )
    assert council_result["direction"] == "BUY"
    assert (
        council_result[
            "vote_summary"
        ]["BUY"]
        == 5
    )


def test_live_analysis_rejects_invalid_council():
    try:
        LiveMarketAnalysisService(
            candle_store=LiveCandleStore(),
            analysis_store=LiveAnalysisStore(),
            decision_council_v2=object(),
        )
    except TypeError as error:
        assert (
            "decision_council_v2"
            in str(error)
        )
    else:
        raise AssertionError(
            "Se esperaba TypeError."
        )


def test_trade_planner_prefers_council_decision():
    service = LiveMarketAnalysisService(
        candle_store=LiveCandleStore(),
        analysis_store=LiveAnalysisStore(),
    )

    result = {
        "execution_v2": {
            "decision": "EXECUTE_LONG",
        },
        "decision_council_v2": {
            "decision": "BLOCK",
        },
    }

    decision = (
        service._select_trade_plan_decision(
            result
        )
    )

    assert decision == "BLOCK"


def test_trade_planner_falls_back_to_execution_v2():
    service = LiveMarketAnalysisService(
        candle_store=LiveCandleStore(),
        analysis_store=LiveAnalysisStore(),
    )

    result = {
        "execution_v2": {
            "decision": "EXECUTE_SHORT",
        },
    }

    decision = (
        service._select_trade_plan_decision(
            result
        )
    )

    assert decision == "EXECUTE_SHORT"


def test_trade_planner_defaults_to_wait():
    service = LiveMarketAnalysisService(
        candle_store=LiveCandleStore(),
        analysis_store=LiveAnalysisStore(),
    )

    decision = (
        service._select_trade_plan_decision(
            {}
        )
    )

    assert decision == "WAIT"


def test_trade_planner_rejects_unknown_decision():
    service = LiveMarketAnalysisService(
        candle_store=LiveCandleStore(),
        analysis_store=LiveAnalysisStore(),
    )

    result = {
        "decision_council_v2": {
            "decision": "UNKNOWN",
        },
    }

    decision = (
        service._select_trade_plan_decision(
            result
        )
    )

    assert decision == "WAIT"
