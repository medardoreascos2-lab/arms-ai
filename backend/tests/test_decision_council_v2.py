import pytest

from backend.intelligence.decision_council_v2 import (
    DecisionCouncilV2,
)


def build_council() -> DecisionCouncilV2:
    return DecisionCouncilV2()


def build_bullish_inputs():
    return {
        "trend_result": {
            "status": "READY",
            "direction": "BULLISH",
            "confidence": 92.0,
        },
        "market_regime_result": {
            "status": "READY",
            "direction": "BUY",
            "confidence": 82.0,
        },
        "probability_result": {
            "approved": True,
            "recommendation": "BUY",
            "probability": 88.0,
        },
        "confluence_result": {
            "approved": True,
            "status": "APPROVED",
            "decision": "EXECUTE",
            "direction": "BUY",
            "score": 94.0,
            "blocking_reasons": [],
        },
        "execution_result": {
            "approved": True,
            "status": "READY",
            "direction": "BUY",
            "confidence": 90.0,
            "blocking_reasons": [],
        },
        "risk_approved": True,
        "session_allowed": True,
    }


def test_approves_strong_long_consensus():
    result = build_council().evaluate(
        **build_bullish_inputs()
    )

    assert result["approved"] is True
    assert result["status"] == "APPROVED"
    assert (
        result["decision"]
        == "EXECUTE_LONG"
    )
    assert result["direction"] == "BUY"
    assert result["vote_summary"]["BUY"] == 5
    assert result["directional_votes"] == 5
    assert result["confidence"] == pytest.approx(
        89.9
    )
    assert result["blocking_reasons"] == []


def test_approves_strong_short_consensus():
    inputs = build_bullish_inputs()

    inputs["trend_result"]["direction"] = (
        "BEARISH"
    )
    inputs["market_regime_result"][
        "direction"
    ] = "SELL"
    inputs["probability_result"][
        "recommendation"
    ] = "SELL"
    inputs["confluence_result"][
        "direction"
    ] = "SELL"
    inputs["execution_result"][
        "direction"
    ] = "SELL"

    result = build_council().evaluate(
        **inputs
    )

    assert result["approved"] is True
    assert (
        result["decision"]
        == "EXECUTE_SHORT"
    )
    assert result["direction"] == "SELL"
    assert result["vote_summary"]["SELL"] == 5


def test_risk_gate_blocks_trade():
    inputs = build_bullish_inputs()
    inputs["risk_approved"] = False

    result = build_council().evaluate(
        **inputs
    )

    assert result["approved"] is False
    assert result["status"] == "BLOCKED"
    assert result["decision"] == "BLOCK"
    assert (
        "risk_not_approved"
        in result["blocking_reasons"]
    )


def test_session_gate_blocks_trade():
    inputs = build_bullish_inputs()
    inputs["session_allowed"] = False

    result = build_council().evaluate(
        **inputs
    )

    assert result["approved"] is False
    assert result["status"] == "BLOCKED"
    assert (
        "session_not_allowed"
        in result["blocking_reasons"]
    )


def test_execution_block_overrides_consensus():
    inputs = build_bullish_inputs()

    inputs["execution_result"] = {
        "approved": False,
        "status": "BLOCKED",
        "decision": "BLOCK",
        "confidence": 95.0,
        "blocking_reasons": [
            "spread_too_wide",
        ],
    }

    result = build_council().evaluate(
        **inputs
    )

    assert result["approved"] is False
    assert result["status"] == "BLOCKED"
    assert result["votes"]["execution"] == "BLOCK"
    assert (
        "spread_too_wide"
        in result["blocking_reasons"]
    )
    assert (
        "execution_blocked"
        in result["blocking_reasons"]
    )


def test_waits_when_consensus_is_insufficient():
    inputs = build_bullish_inputs()

    inputs["market_regime_result"] = {
        "status": "SIDEWAYS",
        "direction": "NEUTRAL",
        "confidence": 50.0,
    }
    inputs["probability_result"] = {
        "approved": False,
        "recommendation": "NO_TRADE",
        "probability": 62.0,
    }
    inputs["confluence_result"] = {
        "approved": False,
        "status": "WAITING",
        "decision": "WAIT",
        "direction": "BUY",
        "score": 72.0,
        "blocking_reasons": [],
    }
    inputs["execution_result"] = {
        "approved": False,
        "status": "WAITING",
        "decision": "WAIT",
        "confidence": 60.0,
        "blocking_reasons": [],
    }

    result = build_council().evaluate(
        **inputs
    )

    assert result["approved"] is False
    assert result["status"] == "WAITING"
    assert result["decision"] == "WAIT"
    assert result["direction"] == "BUY"
    assert (
        "insufficient_consensus"
        in result["warnings"]
    )


def test_rejects_when_no_direction_exists():
    neutral = {
        "status": "READY",
        "direction": "NEUTRAL",
        "confidence": 50.0,
    }

    result = build_council().evaluate(
        trend_result=dict(neutral),
        market_regime_result=dict(neutral),
        probability_result={
            "approved": False,
            "recommendation": "NO_TRADE",
            "probability": 40.0,
        },
        confluence_result={
            "approved": False,
            "status": "REJECTED",
            "decision": "REJECT",
            "direction": "NEUTRAL",
            "score": 45.0,
            "blocking_reasons": [],
        },
        execution_result={
            "approved": False,
            "status": "WAITING",
            "decision": "WAIT",
            "confidence": 50.0,
            "blocking_reasons": [],
        },
        risk_approved=True,
        session_allowed=True,
    )

    assert result["approved"] is False
    assert result["status"] == "REJECTED"
    assert result["decision"] == "REJECT"
    assert result["direction"] == "NEUTRAL"


def test_detects_direction_conflict():
    inputs = build_bullish_inputs()

    inputs["market_regime_result"][
        "direction"
    ] = "SELL"
    inputs["execution_result"][
        "direction"
    ] = "SELL"

    result = build_council().evaluate(
        **inputs
    )

    assert (
        "direction_conflict"
        in result["warnings"]
    )
    assert result["vote_summary"]["BUY"] == 3
    assert result["vote_summary"]["SELL"] == 2


def test_normalizes_scores_between_zero_and_one():
    inputs = build_bullish_inputs()

    inputs["trend_result"][
        "confidence"
    ] = 0.92
    inputs["market_regime_result"][
        "confidence"
    ] = 0.82
    inputs["probability_result"][
        "probability"
    ] = 0.88
    inputs["confluence_result"][
        "score"
    ] = 0.94
    inputs["execution_result"][
        "confidence"
    ] = 0.90

    result = build_council().evaluate(
        **inputs
    )

    assert result["confidence"] == pytest.approx(
        89.9
    )
    assert result["approved"] is True


@pytest.mark.parametrize(
    "field_name",
    [
        "trend_result",
        "market_regime_result",
        "probability_result",
        "confluence_result",
        "execution_result",
    ],
)
def test_requires_dictionary_results(
    field_name,
):
    inputs = build_bullish_inputs()
    inputs[field_name] = None

    with pytest.raises(
        TypeError,
        match="debe ser un diccionario",
    ):
        build_council().evaluate(
            **inputs
        )
