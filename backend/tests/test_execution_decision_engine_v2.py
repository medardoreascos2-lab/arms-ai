import pytest

from backend.execution.execution_decision_engine_v2 import (
    ExecutionDecisionEngineV2,
)


def build_engine() -> ExecutionDecisionEngineV2:
    return ExecutionDecisionEngineV2(
        minimum_probability=0.80,
        minimum_confluence_score=0.80,
    )


def test_executes_long_when_all_conditions_align():
    engine = build_engine()

    result = engine.evaluate(
        signal_direction="LONG",
        probability=0.92,
        confluence_score=0.90,
        smart_money_direction="BULLISH",
        market_regime="TREND_UP",
        market_tradable=True,
        risk_approved=True,
        sizing_approved=True,
        contracts=2,
        has_open_position=False,
        daily_limit_reached=False,
        news_blocked=False,
    )

    assert result["approved"] is True
    assert result["decision"] == "EXECUTE_LONG"
    assert result["direction"] == "LONG"
    assert result["contracts"] == 2
    assert result["blocking_reasons"] == []
    assert result["waiting_reasons"] == []


def test_executes_short_when_all_conditions_align():
    engine = build_engine()

    result = engine.evaluate(
        signal_direction="SHORT",
        probability=0.90,
        confluence_score=0.88,
        smart_money_direction="BEARISH",
        market_regime="TREND_DOWN",
        market_tradable=True,
        risk_approved=True,
        sizing_approved=True,
        contracts=1,
        has_open_position=False,
        daily_limit_reached=False,
        news_blocked=False,
    )

    assert result["approved"] is True
    assert result["decision"] == "EXECUTE_SHORT"
    assert result["direction"] == "SHORT"


def test_waits_when_probability_is_too_low():
    engine = build_engine()

    result = engine.evaluate(
        signal_direction="LONG",
        probability=0.70,
        confluence_score=0.90,
        smart_money_direction="BULLISH",
        market_regime="TREND_UP",
        market_tradable=True,
        risk_approved=True,
        sizing_approved=True,
        contracts=2,
        has_open_position=False,
        daily_limit_reached=False,
        news_blocked=False,
    )

    assert result["approved"] is False
    assert result["decision"] == "WAIT"
    assert (
        "probability_below_threshold"
        in result["waiting_reasons"]
    )


def test_waits_when_confluence_is_too_low():
    engine = build_engine()

    result = engine.evaluate(
        signal_direction="LONG",
        probability=0.90,
        confluence_score=0.65,
        smart_money_direction="BULLISH",
        market_regime="TREND_UP",
        market_tradable=True,
        risk_approved=True,
        sizing_approved=True,
        contracts=2,
        has_open_position=False,
        daily_limit_reached=False,
        news_blocked=False,
    )

    assert result["approved"] is False
    assert result["decision"] == "WAIT"
    assert (
        "confluence_below_threshold"
        in result["waiting_reasons"]
    )


def test_waits_when_smart_money_conflicts_with_long():
    engine = build_engine()

    result = engine.evaluate(
        signal_direction="LONG",
        probability=0.92,
        confluence_score=0.90,
        smart_money_direction="BEARISH",
        market_regime="TREND_UP",
        market_tradable=True,
        risk_approved=True,
        sizing_approved=True,
        contracts=2,
        has_open_position=False,
        daily_limit_reached=False,
        news_blocked=False,
    )

    assert result["approved"] is False
    assert result["decision"] == "WAIT"
    assert (
        "smart_money_direction_conflict"
        in result["waiting_reasons"]
    )


def test_waits_when_market_regime_conflicts_with_short():
    engine = build_engine()

    result = engine.evaluate(
        signal_direction="SHORT",
        probability=0.92,
        confluence_score=0.90,
        smart_money_direction="BEARISH",
        market_regime="TREND_UP",
        market_tradable=True,
        risk_approved=True,
        sizing_approved=True,
        contracts=2,
        has_open_position=False,
        daily_limit_reached=False,
        news_blocked=False,
    )

    assert result["approved"] is False
    assert result["decision"] == "WAIT"
    assert (
        "market_regime_direction_conflict"
        in result["waiting_reasons"]
    )


def test_blocks_when_market_is_not_tradable():
    engine = build_engine()

    result = engine.evaluate(
        signal_direction="LONG",
        probability=0.95,
        confluence_score=0.95,
        smart_money_direction="BULLISH",
        market_regime="NO_TRADE",
        market_tradable=False,
        risk_approved=True,
        sizing_approved=True,
        contracts=2,
        has_open_position=False,
        daily_limit_reached=False,
        news_blocked=False,
    )

    assert result["approved"] is False
    assert result["decision"] == "BLOCK"
    assert (
        "market_not_tradable"
        in result["blocking_reasons"]
    )


def test_blocks_when_account_risk_rejects():
    engine = build_engine()

    result = engine.evaluate(
        signal_direction="LONG",
        probability=0.95,
        confluence_score=0.95,
        smart_money_direction="BULLISH",
        market_regime="TREND_UP",
        market_tradable=True,
        risk_approved=False,
        sizing_approved=True,
        contracts=2,
        has_open_position=False,
        daily_limit_reached=False,
        news_blocked=False,
    )

    assert result["approved"] is False
    assert result["decision"] == "BLOCK"
    assert (
        "account_risk_rejected"
        in result["blocking_reasons"]
    )


def test_blocks_when_position_sizing_rejects():
    engine = build_engine()

    result = engine.evaluate(
        signal_direction="LONG",
        probability=0.95,
        confluence_score=0.95,
        smart_money_direction="BULLISH",
        market_regime="TREND_UP",
        market_tradable=True,
        risk_approved=True,
        sizing_approved=False,
        contracts=0,
        has_open_position=False,
        daily_limit_reached=False,
        news_blocked=False,
    )

    assert result["approved"] is False
    assert result["decision"] == "BLOCK"
    assert (
        "position_sizing_rejected"
        in result["blocking_reasons"]
    )


def test_blocks_when_contracts_are_invalid():
    engine = build_engine()

    result = engine.evaluate(
        signal_direction="LONG",
        probability=0.95,
        confluence_score=0.95,
        smart_money_direction="BULLISH",
        market_regime="TREND_UP",
        market_tradable=True,
        risk_approved=True,
        sizing_approved=True,
        contracts=0,
        has_open_position=False,
        daily_limit_reached=False,
        news_blocked=False,
    )

    assert result["approved"] is False
    assert result["decision"] == "BLOCK"
    assert (
        "invalid_contracts"
        in result["blocking_reasons"]
    )


def test_blocks_when_position_is_already_open():
    engine = build_engine()

    result = engine.evaluate(
        signal_direction="LONG",
        probability=0.95,
        confluence_score=0.95,
        smart_money_direction="BULLISH",
        market_regime="TREND_UP",
        market_tradable=True,
        risk_approved=True,
        sizing_approved=True,
        contracts=2,
        has_open_position=True,
        daily_limit_reached=False,
        news_blocked=False,
    )

    assert result["approved"] is False
    assert result["decision"] == "BLOCK"
    assert (
        "position_already_open"
        in result["blocking_reasons"]
    )


def test_blocks_when_daily_limit_is_reached():
    engine = build_engine()

    result = engine.evaluate(
        signal_direction="LONG",
        probability=0.95,
        confluence_score=0.95,
        smart_money_direction="BULLISH",
        market_regime="TREND_UP",
        market_tradable=True,
        risk_approved=True,
        sizing_approved=True,
        contracts=2,
        has_open_position=False,
        daily_limit_reached=True,
        news_blocked=False,
    )

    assert result["approved"] is False
    assert result["decision"] == "BLOCK"
    assert (
        "daily_limit_reached"
        in result["blocking_reasons"]
    )


def test_blocks_during_high_impact_news():
    engine = build_engine()

    result = engine.evaluate(
        signal_direction="SHORT",
        probability=0.95,
        confluence_score=0.95,
        smart_money_direction="BEARISH",
        market_regime="TREND_DOWN",
        market_tradable=True,
        risk_approved=True,
        sizing_approved=True,
        contracts=2,
        has_open_position=False,
        daily_limit_reached=False,
        news_blocked=True,
    )

    assert result["approved"] is False
    assert result["decision"] == "BLOCK"
    assert (
        "high_impact_news"
        in result["blocking_reasons"]
    )


def test_blocking_reasons_have_priority_over_waiting_reasons():
    engine = build_engine()

    result = engine.evaluate(
        signal_direction="LONG",
        probability=0.40,
        confluence_score=0.40,
        smart_money_direction="BEARISH",
        market_regime="NO_TRADE",
        market_tradable=False,
        risk_approved=False,
        sizing_approved=False,
        contracts=0,
        has_open_position=True,
        daily_limit_reached=True,
        news_blocked=True,
    )

    assert result["approved"] is False
    assert result["decision"] == "BLOCK"
    assert len(result["blocking_reasons"]) >= 6
    assert len(result["waiting_reasons"]) >= 2


def test_normalizes_directions():
    engine = build_engine()

    result = engine.evaluate(
        signal_direction="  long  ",
        probability=0.90,
        confluence_score=0.90,
        smart_money_direction=" bullish ",
        market_regime=" trend_up ",
        market_tradable=True,
        risk_approved=True,
        sizing_approved=True,
        contracts=1,
        has_open_position=False,
        daily_limit_reached=False,
        news_blocked=False,
    )

    assert result["approved"] is True
    assert result["decision"] == "EXECUTE_LONG"


def test_rejects_invalid_signal_direction():
    engine = build_engine()

    with pytest.raises(
        ValueError,
        match="signal_direction",
    ):
        engine.evaluate(
            signal_direction="SIDEWAYS",
            probability=0.90,
            confluence_score=0.90,
            smart_money_direction="BULLISH",
            market_regime="TREND_UP",
            market_tradable=True,
            risk_approved=True,
            sizing_approved=True,
            contracts=1,
            has_open_position=False,
            daily_limit_reached=False,
            news_blocked=False,
        )


def test_rejects_invalid_probability():
    engine = build_engine()

    with pytest.raises(
        ValueError,
        match="probability",
    ):
        engine.evaluate(
            signal_direction="LONG",
            probability=1.1,
            confluence_score=0.90,
            smart_money_direction="BULLISH",
            market_regime="TREND_UP",
            market_tradable=True,
            risk_approved=True,
            sizing_approved=True,
            contracts=1,
            has_open_position=False,
            daily_limit_reached=False,
            news_blocked=False,
        )


def test_rejects_invalid_confluence_score():
    engine = build_engine()

    with pytest.raises(
        ValueError,
        match="confluence_score",
    ):
        engine.evaluate(
            signal_direction="LONG",
            probability=0.90,
            confluence_score=-0.1,
            smart_money_direction="BULLISH",
            market_regime="TREND_UP",
            market_tradable=True,
            risk_approved=True,
            sizing_approved=True,
            contracts=1,
            has_open_position=False,
            daily_limit_reached=False,
            news_blocked=False,
        )


def test_rejects_negative_contracts():
    engine = build_engine()

    with pytest.raises(
        ValueError,
        match="contracts",
    ):
        engine.evaluate(
            signal_direction="LONG",
            probability=0.90,
            confluence_score=0.90,
            smart_money_direction="BULLISH",
            market_regime="TREND_UP",
            market_tradable=True,
            risk_approved=True,
            sizing_approved=True,
            contracts=-1,
            has_open_position=False,
            daily_limit_reached=False,
            news_blocked=False,
        )


def test_rejects_invalid_thresholds():
    with pytest.raises(
        ValueError,
        match="minimum_probability",
    ):
        ExecutionDecisionEngineV2(
            minimum_probability=1.1,
            minimum_confluence_score=0.80,
        )
