import pytest

from backend.intelligence.probability_engine_v2 import (
    ProbabilityEngineV2,
)


def build_engine() -> ProbabilityEngineV2:
    return ProbabilityEngineV2(
        minimum_approval_probability=0.80,
        very_high_threshold=0.90,
        high_threshold=0.80,
        medium_threshold=0.65,
    )


def test_returns_very_high_probability():
    engine = build_engine()

    result = engine.evaluate(
        smart_money_score=1.0,
        trend_score=1.0,
        market_regime_score=1.0,
        confluence_score=1.0,
        volume_score=1.0,
        risk_approved=True,
        sizing_approved=True,
        market_tradable=True,
    )

    assert result["probability"] == 1.0
    assert result["confidence"] == "VERY_HIGH"
    assert result["grade"] == "A+"
    assert result["approved"] is True
    assert result["decision"] == "EXECUTE"


def test_returns_high_probability():
    engine = build_engine()

    result = engine.evaluate(
        smart_money_score=0.85,
        trend_score=0.85,
        market_regime_score=0.80,
        confluence_score=0.85,
        volume_score=0.80,
        risk_approved=True,
        sizing_approved=True,
        market_tradable=True,
    )

    assert result["confidence"] == "HIGH"
    assert result["grade"] == "A"
    assert result["approved"] is True
    assert result["decision"] == "EXECUTE"
    assert 0.80 <= result["probability"] < 0.90


def test_returns_medium_probability_and_waits():
    engine = build_engine()

    result = engine.evaluate(
        smart_money_score=0.70,
        trend_score=0.70,
        market_regime_score=0.65,
        confluence_score=0.70,
        volume_score=0.65,
        risk_approved=True,
        sizing_approved=True,
        market_tradable=True,
    )

    assert result["confidence"] == "MEDIUM"
    assert result["grade"] == "B"
    assert result["approved"] is False
    assert result["decision"] == "WAIT"
    assert 0.65 <= result["probability"] < 0.80


def test_returns_low_probability_and_rejects():
    engine = build_engine()

    result = engine.evaluate(
        smart_money_score=0.40,
        trend_score=0.50,
        market_regime_score=0.40,
        confluence_score=0.45,
        volume_score=0.40,
        risk_approved=True,
        sizing_approved=True,
        market_tradable=True,
    )

    assert result["confidence"] == "LOW"
    assert result["grade"] == "C"
    assert result["approved"] is False
    assert result["decision"] == "REJECT"
    assert result["probability"] < 0.65


def test_uses_expected_weights():
    engine = build_engine()

    result = engine.evaluate(
        smart_money_score=1.0,
        trend_score=0.0,
        market_regime_score=0.0,
        confluence_score=0.0,
        volume_score=0.0,
        risk_approved=True,
        sizing_approved=True,
        market_tradable=True,
    )

    assert result["probability"] == 0.40
    assert result["contributions"]["smart_money"] == 0.40
    assert result["weights"] == {
        "smart_money": 0.40,
        "trend": 0.20,
        "market_regime": 0.15,
        "confluence": 0.15,
        "volume": 0.10,
    }


def test_blocks_when_risk_is_rejected():
    engine = build_engine()

    result = engine.evaluate(
        smart_money_score=1.0,
        trend_score=1.0,
        market_regime_score=1.0,
        confluence_score=1.0,
        volume_score=1.0,
        risk_approved=False,
        sizing_approved=True,
        market_tradable=True,
    )

    assert result["approved"] is False
    assert result["decision"] == "BLOCK"
    assert result["status"] == "BLOCKED"
    assert (
        "account_risk_rejected"
        in result["blocking_reasons"]
    )


def test_blocks_when_sizing_is_rejected():
    engine = build_engine()

    result = engine.evaluate(
        smart_money_score=1.0,
        trend_score=1.0,
        market_regime_score=1.0,
        confluence_score=1.0,
        volume_score=1.0,
        risk_approved=True,
        sizing_approved=False,
        market_tradable=True,
    )

    assert result["approved"] is False
    assert result["decision"] == "BLOCK"
    assert (
        "position_sizing_rejected"
        in result["blocking_reasons"]
    )


def test_blocks_when_market_is_not_tradable():
    engine = build_engine()

    result = engine.evaluate(
        smart_money_score=1.0,
        trend_score=1.0,
        market_regime_score=1.0,
        confluence_score=1.0,
        volume_score=1.0,
        risk_approved=True,
        sizing_approved=True,
        market_tradable=False,
    )

    assert result["approved"] is False
    assert result["decision"] == "BLOCK"
    assert (
        "market_not_tradable"
        in result["blocking_reasons"]
    )


@pytest.mark.parametrize(
    "field_name",
    [
        "smart_money_score",
        "trend_score",
        "market_regime_score",
        "confluence_score",
        "volume_score",
    ],
)
def test_rejects_component_above_one(
    field_name: str,
):
    engine = build_engine()

    values = {
        "smart_money_score": 1.0,
        "trend_score": 1.0,
        "market_regime_score": 1.0,
        "confluence_score": 1.0,
        "volume_score": 1.0,
    }

    values[field_name] = 1.1

    with pytest.raises(
        ValueError,
        match=field_name,
    ):
        engine.evaluate(
            **values,
            risk_approved=True,
            sizing_approved=True,
            market_tradable=True,
        )


def test_rejects_negative_component():
    engine = build_engine()

    with pytest.raises(
        ValueError,
        match="smart_money_score",
    ):
        engine.evaluate(
            smart_money_score=-0.1,
            trend_score=1.0,
            market_regime_score=1.0,
            confluence_score=1.0,
            volume_score=1.0,
            risk_approved=True,
            sizing_approved=True,
            market_tradable=True,
        )


def test_rejects_invalid_threshold_order():
    with pytest.raises(
        ValueError,
        match="threshold",
    ):
        ProbabilityEngineV2(
            minimum_approval_probability=0.80,
            very_high_threshold=0.75,
            high_threshold=0.85,
            medium_threshold=0.65,
        )
