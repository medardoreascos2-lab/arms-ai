import pytest

from backend.signals.signal_engine import (
    SignalEngine,
)


def build_analysis(
    *,
    action="BUY",
    approved=True,
    probability_approved=True,
    risk_approved=True,
):
    return {
        "symbol": "NQ",
        "timeframe": "5m",
        "current_price": 21691.0,
        "decision": {
            "action": action,
            "score": 88.0,
            "grade": "A+",
            "approved": approved,
        },
        "probability": {
            "value": 84.0,
            "confidence": "MUY ALTA",
            "approved": probability_approved,
        },
        "risk": {
            "approved": risk_approved,
        },
        "trade": {
            "entry_price": 21691.0,
            "stop_loss": 21672.25,
            "take_profit": 21728.50,
        },
    }


def test_generates_buy_signal():
    signal = SignalEngine().generate(
        build_analysis()
    )

    assert signal["action"] == "BUY"
    assert signal["approved"] is True
    assert signal["grade"] == "A+"
    assert signal["score"] == 88.0


def test_generates_sell_signal():
    signal = SignalEngine().generate(
        build_analysis(
            action="SELL"
        )
    )

    assert signal["action"] == "SELL"


def test_wait_when_probability_is_rejected():
    signal = SignalEngine().generate(
        build_analysis(
            probability_approved=False
        )
    )

    assert signal["action"] == "WAIT"
    assert signal["approved"] is False


def test_wait_when_risk_is_rejected():
    signal = SignalEngine().generate(
        build_analysis(
            risk_approved=False
        )
    )

    assert signal["action"] == "WAIT"
    assert signal["approved"] is False


def test_wait_when_decision_is_rejected():
    signal = SignalEngine().generate(
        build_analysis(
            approved=False
        )
    )

    assert signal["action"] == "WAIT"
    assert signal["approved"] is False


def test_invalid_analysis():
    with pytest.raises(
        KeyError
    ):
        SignalEngine().generate({})
