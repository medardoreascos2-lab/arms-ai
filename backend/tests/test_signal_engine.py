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


def test_wait_signal_allows_missing_trade_levels():
    analysis = build_analysis()

    analysis["decision"]["approved"] = False
    analysis["decision"]["action"] = "ESPERAR"
    analysis["probability"]["approved"] = False
    analysis["risk"]["approved"] = False

    analysis["trade"]["stop_loss"] = None
    analysis["trade"]["take_profit"] = None

    result = SignalEngine().generate(
        analysis
    )

    assert result["action"] == "WAIT"
    assert result["approved"] is False
    assert result["entry_price"] is not None
    assert result["stop_loss"] is None
    assert result["take_profit"] is None


def test_approved_signal_rejects_missing_levels():
    analysis = build_analysis()

    analysis["decision"]["approved"] = True
    analysis["decision"]["action"] = "BUY"
    analysis["probability"]["approved"] = True
    analysis["risk"]["approved"] = True

    analysis["trade"]["stop_loss"] = None

    with pytest.raises(
        ValueError,
        match="señal aprobada requiere",
    ):
        SignalEngine().generate(
            analysis
        )
