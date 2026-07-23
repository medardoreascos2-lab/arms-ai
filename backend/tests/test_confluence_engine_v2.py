import pytest

from backend.intelligence.confluence_engine_v2 import (
    ConfluenceEngineV2,
)


def build_engine() -> ConfluenceEngineV2:
    return ConfluenceEngineV2()


def test_returns_a_plus_for_exceptional_setup():
    engine = build_engine()

    result = engine.evaluate(
        trend_score=1.0,
        structure_score=1.0,
        liquidity_score=1.0,
        fvg_score=1.0,
        ema_alignment_score=1.0,
        market_regime_score=1.0,
        probability_score=1.0,
        volume_score=1.0,
        risk_approved=True,
        sizing_approved=True,
        market_tradable=True,
    )

    assert result["approved"] is True
    assert result["status"] == "APPROVED"
    assert result["score"] == 100.0
    assert result["grade"] == "A+"
    assert result["decision"] == "EXECUTE"
    assert result["blocking_reasons"] == []


def test_returns_a_grade():
    engine = build_engine()

    result = engine.evaluate(
        trend_score=0.85,
        structure_score=0.85,
        liquidity_score=0.80,
        fvg_score=0.80,
        ema_alignment_score=0.80,
        market_regime_score=0.85,
        probability_score=0.85,
        volume_score=0.80,
        risk_approved=True,
        sizing_approved=True,
        market_tradable=True,
    )

    assert result["approved"] is True
    assert result["grade"] == "A"
    assert result["decision"] == "EXECUTE"
    assert 80.0 <= result["score"] < 90.0


def test_returns_b_and_waits_for_confirmation():
    engine = build_engine()

    result = engine.evaluate(
        trend_score=0.75,
        structure_score=0.75,
        liquidity_score=0.70,
        fvg_score=0.70,
        ema_alignment_score=0.70,
        market_regime_score=0.75,
        probability_score=0.75,
        volume_score=0.70,
        risk_approved=True,
        sizing_approved=True,
        market_tradable=True,
    )

    assert result["approved"] is False
    assert result["grade"] == "B"
    assert result["decision"] == "WAIT"
    assert 70.0 <= result["score"] < 80.0


def test_returns_c_and_rejects_low_quality_setup():
    engine = build_engine()

    result = engine.evaluate(
        trend_score=0.50,
        structure_score=0.50,
        liquidity_score=0.40,
        fvg_score=0.40,
        ema_alignment_score=0.50,
        market_regime_score=0.50,
        probability_score=0.50,
        volume_score=0.40,
        risk_approved=True,
        sizing_approved=True,
        market_tradable=True,
    )

    assert result["approved"] is False
    assert result["grade"] == "C"
    assert result["decision"] == "REJECT"
    assert result["score"] < 70.0


def test_blocks_when_risk_is_rejected():
    engine = build_engine()

    result = engine.evaluate(
        trend_score=1.0,
        structure_score=1.0,
        liquidity_score=1.0,
        fvg_score=1.0,
        ema_alignment_score=1.0,
        market_regime_score=1.0,
        probability_score=1.0,
        volume_score=1.0,
        risk_approved=False,
        sizing_approved=True,
        market_tradable=True,
    )

    assert result["approved"] is False
    assert result["status"] == "BLOCKED"
    assert result["decision"] == "BLOCK"
    assert (
        "account_risk_rejected"
        in result["blocking_reasons"]
    )


def test_blocks_when_sizing_is_rejected():
    engine = build_engine()

    result = engine.evaluate(
        trend_score=1.0,
        structure_score=1.0,
        liquidity_score=1.0,
        fvg_score=1.0,
        ema_alignment_score=1.0,
        market_regime_score=1.0,
        probability_score=1.0,
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
        trend_score=1.0,
        structure_score=1.0,
        liquidity_score=1.0,
        fvg_score=1.0,
        ema_alignment_score=1.0,
        market_regime_score=1.0,
        probability_score=1.0,
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


def test_reports_component_contributions():
    engine = build_engine()

    result = engine.evaluate(
        trend_score=1.0,
        structure_score=0.0,
        liquidity_score=0.0,
        fvg_score=0.0,
        ema_alignment_score=0.0,
        market_regime_score=0.0,
        probability_score=0.0,
        volume_score=0.0,
        risk_approved=True,
        sizing_approved=True,
        market_tradable=True,
    )

    assert result["score"] == 15.0
    assert result["contributions"]["trend"] == 15.0
    assert result["contributions"]["structure"] == 0.0


def test_score_is_rounded_to_two_decimals():
    engine = build_engine()

    result = engine.evaluate(
        trend_score=0.333,
        structure_score=0.333,
        liquidity_score=0.333,
        fvg_score=0.333,
        ema_alignment_score=0.333,
        market_regime_score=0.333,
        probability_score=0.333,
        volume_score=0.333,
        risk_approved=True,
        sizing_approved=True,
        market_tradable=True,
    )

    assert result["score"] == 33.3


@pytest.mark.parametrize(
    "field_name",
    [
        "trend_score",
        "structure_score",
        "liquidity_score",
        "fvg_score",
        "ema_alignment_score",
        "market_regime_score",
        "probability_score",
        "volume_score",
    ],
)
def test_rejects_component_score_above_one(
    field_name: str,
):
    engine = build_engine()

    values = {
        "trend_score": 1.0,
        "structure_score": 1.0,
        "liquidity_score": 1.0,
        "fvg_score": 1.0,
        "ema_alignment_score": 1.0,
        "market_regime_score": 1.0,
        "probability_score": 1.0,
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


def test_rejects_negative_component_score():
    engine = build_engine()

    with pytest.raises(
        ValueError,
        match="trend_score",
    ):
        engine.evaluate(
            trend_score=-0.1,
            structure_score=1.0,
            liquidity_score=1.0,
            fvg_score=1.0,
            ema_alignment_score=1.0,
            market_regime_score=1.0,
            probability_score=1.0,
            volume_score=1.0,
            risk_approved=True,
            sizing_approved=True,
            market_tradable=True,
        )
