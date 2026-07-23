import pytest

from backend.execution.execution_decision_engine import (
    ExecutionDecisionEngine,
)


def build_engine() -> ExecutionDecisionEngine:
    return ExecutionDecisionEngine(
        minimum_confidence=0.70,
    )


def test_executes_when_all_conditions_are_approved():
    engine = build_engine()

    result = engine.evaluate(
        signal_accepted=True,
        signal_confidence=0.85,
        risk_approved=True,
        sizing_approved=True,
        contracts=2,
    )

    assert result["approved"] is True
    assert result["decision"] == "EXECUTE"
    assert result["contracts"] == 2
    assert result["reasons"] == []


def test_waits_when_signal_is_not_accepted():
    engine = build_engine()

    result = engine.evaluate(
        signal_accepted=False,
        signal_confidence=0.85,
        risk_approved=True,
        sizing_approved=True,
        contracts=2,
    )

    assert result["approved"] is False
    assert result["decision"] == "WAIT"
    assert "signal_not_accepted" in result["reasons"]


def test_waits_when_confidence_is_too_low():
    engine = build_engine()

    result = engine.evaluate(
        signal_accepted=True,
        signal_confidence=0.60,
        risk_approved=True,
        sizing_approved=True,
        contracts=2,
    )

    assert result["approved"] is False
    assert result["decision"] == "WAIT"
    assert "low_confidence" in result["reasons"]


def test_blocks_when_account_risk_rejects():
    engine = build_engine()

    result = engine.evaluate(
        signal_accepted=True,
        signal_confidence=0.90,
        risk_approved=False,
        sizing_approved=True,
        contracts=2,
    )

    assert result["approved"] is False
    assert result["decision"] == "BLOCK"
    assert "account_risk_rejected" in result["reasons"]


def test_blocks_when_position_sizing_rejects():
    engine = build_engine()

    result = engine.evaluate(
        signal_accepted=True,
        signal_confidence=0.90,
        risk_approved=True,
        sizing_approved=False,
        contracts=0,
    )

    assert result["approved"] is False
    assert result["decision"] == "BLOCK"
    assert "position_sizing_rejected" in result["reasons"]


def test_blocks_when_contracts_are_zero():
    engine = build_engine()

    result = engine.evaluate(
        signal_accepted=True,
        signal_confidence=0.90,
        risk_approved=True,
        sizing_approved=True,
        contracts=0,
    )

    assert result["approved"] is False
    assert result["decision"] == "BLOCK"
    assert "invalid_contracts" in result["reasons"]


def test_reports_multiple_reasons():
    engine = build_engine()

    result = engine.evaluate(
        signal_accepted=False,
        signal_confidence=0.40,
        risk_approved=False,
        sizing_approved=False,
        contracts=0,
    )

    assert result["approved"] is False
    assert result["decision"] == "BLOCK"
    assert len(result["reasons"]) >= 4


def test_accepts_confidence_at_threshold():
    engine = build_engine()

    result = engine.evaluate(
        signal_accepted=True,
        signal_confidence=0.70,
        risk_approved=True,
        sizing_approved=True,
        contracts=1,
    )

    assert result["approved"] is True
    assert result["decision"] == "EXECUTE"


def test_rejects_invalid_confidence():
    engine = build_engine()

    with pytest.raises(
        ValueError,
        match="signal_confidence",
    ):
        engine.evaluate(
            signal_accepted=True,
            signal_confidence=1.1,
            risk_approved=True,
            sizing_approved=True,
            contracts=1,
        )


def test_rejects_negative_contracts():
    engine = build_engine()

    with pytest.raises(
        ValueError,
        match="contracts",
    ):
        engine.evaluate(
            signal_accepted=True,
            signal_confidence=0.90,
            risk_approved=True,
            sizing_approved=True,
            contracts=-1,
        )


def test_rejects_invalid_minimum_confidence():
    with pytest.raises(
        ValueError,
        match="minimum_confidence",
    ):
        ExecutionDecisionEngine(
            minimum_confidence=1.5,
        )


def test_blocks_when_market_is_not_tradable():
    engine = build_engine()

    result = engine.evaluate(
        signal_accepted=True,
        signal_confidence=0.90,
        risk_approved=True,
        sizing_approved=True,
        contracts=2,
        market_tradable=False,
        market_regime="NO_TRADE",
    )

    assert result["approved"] is False
    assert result["decision"] == "BLOCK"
    assert (
        "market_not_tradable"
        in result["reasons"]
    )
    assert result["market_regime"] == "NO_TRADE"


def test_waits_when_market_is_ranging():
    engine = build_engine()

    result = engine.evaluate(
        signal_accepted=True,
        signal_confidence=0.90,
        risk_approved=True,
        sizing_approved=True,
        contracts=2,
        market_tradable=True,
        market_regime="RANGE",
    )

    assert result["approved"] is False
    assert result["decision"] == "WAIT"
    assert (
        "market_range"
        in result["reasons"]
    )


def test_executes_in_trending_market():
    engine = build_engine()

    result = engine.evaluate(
        signal_accepted=True,
        signal_confidence=0.90,
        risk_approved=True,
        sizing_approved=True,
        contracts=2,
        market_tradable=True,
        market_regime="TREND_UP",
    )

    assert result["approved"] is True
    assert result["decision"] == "EXECUTE"
    assert result["market_regime"] == "TREND_UP"


def test_allows_high_volatility_with_warning():
    engine = build_engine()

    result = engine.evaluate(
        signal_accepted=True,
        signal_confidence=0.90,
        risk_approved=True,
        sizing_approved=True,
        contracts=2,
        market_tradable=True,
        market_regime="HIGH_VOLATILITY",
    )

    assert result["approved"] is True
    assert result["decision"] == "EXECUTE"
    assert (
        "high_volatility"
        in result["warnings"]
    )


def test_keeps_backward_compatibility_without_market_regime():
    engine = build_engine()

    result = engine.evaluate(
        signal_accepted=True,
        signal_confidence=0.90,
        risk_approved=True,
        sizing_approved=True,
        contracts=2,
    )

    assert result["approved"] is True
    assert result["decision"] == "EXECUTE"
    assert result["market_regime"] is None
