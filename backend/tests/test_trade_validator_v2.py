import pytest

from backend.execution.trade_validator_v2 import (
    TradeValidatorV2,
)


def build_validator() -> TradeValidatorV2:
    return TradeValidatorV2(
        minimum_reward_risk_ratio=2.0,
        minimum_stop_points=2.0,
        maximum_stop_points=50.0,
        maximum_spread_points=1.0,
        minimum_atr_points=3.0,
        maximum_signal_age_seconds=30,
    )


def build_valid_plan() -> dict[str, object]:
    return {
        "approved": True,
        "status": "ACTIVE",
        "direction": "LONG",
        "entry_price": 100.0,
        "stop_loss": 95.0,
        "take_profit": 110.0,
        "risk_points": 5.0,
        "reward_points": 10.0,
        "reward_risk_ratio": 2.0,
        "contracts": 2,
        "probability": 0.92,
        "confluence_score": 0.90,
        "grade": "A+",
    }


def test_approves_valid_trade_plan():
    validator = build_validator()

    result = validator.validate(
        trade_plan=build_valid_plan(),
        spread_points=0.50,
        atr_points=8.0,
        session_allowed=True,
        news_blocked=False,
        has_open_position=False,
        daily_limit_reached=False,
        signal_age_seconds=5,
    )

    assert result["approved"] is True
    assert result["status"] == "VALID"
    assert result["decision"] == "ALLOW_EXECUTION"
    assert result["blocking_reasons"] == []
    assert result["warnings"] == []


def test_blocks_inactive_trade_plan():
    validator = build_validator()

    plan = build_valid_plan()
    plan["approved"] = False
    plan["status"] = "INACTIVE"

    result = validator.validate(
        trade_plan=plan,
        spread_points=0.50,
        atr_points=8.0,
        session_allowed=True,
        news_blocked=False,
        has_open_position=False,
        daily_limit_reached=False,
        signal_age_seconds=5,
    )

    assert result["approved"] is False
    assert result["decision"] == "BLOCK"
    assert (
        "trade_plan_not_approved"
        in result["blocking_reasons"]
    )


def test_blocks_reward_risk_below_minimum():
    validator = build_validator()

    plan = build_valid_plan()
    plan["reward_risk_ratio"] = 1.5

    result = validator.validate(
        trade_plan=plan,
        spread_points=0.50,
        atr_points=8.0,
        session_allowed=True,
        news_blocked=False,
        has_open_position=False,
        daily_limit_reached=False,
        signal_age_seconds=5,
    )

    assert result["approved"] is False
    assert (
        "reward_risk_below_minimum"
        in result["blocking_reasons"]
    )


def test_blocks_stop_that_is_too_small():
    validator = build_validator()

    plan = build_valid_plan()
    plan["risk_points"] = 1.0

    result = validator.validate(
        trade_plan=plan,
        spread_points=0.50,
        atr_points=8.0,
        session_allowed=True,
        news_blocked=False,
        has_open_position=False,
        daily_limit_reached=False,
        signal_age_seconds=5,
    )

    assert result["approved"] is False
    assert (
        "stop_distance_too_small"
        in result["blocking_reasons"]
    )


def test_blocks_stop_that_is_too_large():
    validator = build_validator()

    plan = build_valid_plan()
    plan["risk_points"] = 60.0

    result = validator.validate(
        trade_plan=plan,
        spread_points=0.50,
        atr_points=8.0,
        session_allowed=True,
        news_blocked=False,
        has_open_position=False,
        daily_limit_reached=False,
        signal_age_seconds=5,
    )

    assert result["approved"] is False
    assert (
        "stop_distance_too_large"
        in result["blocking_reasons"]
    )


def test_blocks_excessive_spread():
    validator = build_validator()

    result = validator.validate(
        trade_plan=build_valid_plan(),
        spread_points=1.50,
        atr_points=8.0,
        session_allowed=True,
        news_blocked=False,
        has_open_position=False,
        daily_limit_reached=False,
        signal_age_seconds=5,
    )

    assert result["approved"] is False
    assert (
        "spread_too_high"
        in result["blocking_reasons"]
    )


def test_blocks_low_atr():
    validator = build_validator()

    result = validator.validate(
        trade_plan=build_valid_plan(),
        spread_points=0.50,
        atr_points=2.0,
        session_allowed=True,
        news_blocked=False,
        has_open_position=False,
        daily_limit_reached=False,
        signal_age_seconds=5,
    )

    assert result["approved"] is False
    assert (
        "atr_below_minimum"
        in result["blocking_reasons"]
    )


def test_blocks_disallowed_session():
    validator = build_validator()

    result = validator.validate(
        trade_plan=build_valid_plan(),
        spread_points=0.50,
        atr_points=8.0,
        session_allowed=False,
        news_blocked=False,
        has_open_position=False,
        daily_limit_reached=False,
        signal_age_seconds=5,
    )

    assert result["approved"] is False
    assert (
        "session_not_allowed"
        in result["blocking_reasons"]
    )


def test_blocks_high_impact_news():
    validator = build_validator()

    result = validator.validate(
        trade_plan=build_valid_plan(),
        spread_points=0.50,
        atr_points=8.0,
        session_allowed=True,
        news_blocked=True,
        has_open_position=False,
        daily_limit_reached=False,
        signal_age_seconds=5,
    )

    assert result["approved"] is False
    assert (
        "high_impact_news"
        in result["blocking_reasons"]
    )


def test_blocks_existing_position():
    validator = build_validator()

    result = validator.validate(
        trade_plan=build_valid_plan(),
        spread_points=0.50,
        atr_points=8.0,
        session_allowed=True,
        news_blocked=False,
        has_open_position=True,
        daily_limit_reached=False,
        signal_age_seconds=5,
    )

    assert result["approved"] is False
    assert (
        "position_already_open"
        in result["blocking_reasons"]
    )


def test_blocks_daily_limit():
    validator = build_validator()

    result = validator.validate(
        trade_plan=build_valid_plan(),
        spread_points=0.50,
        atr_points=8.0,
        session_allowed=True,
        news_blocked=False,
        has_open_position=False,
        daily_limit_reached=True,
        signal_age_seconds=5,
    )

    assert result["approved"] is False
    assert (
        "daily_limit_reached"
        in result["blocking_reasons"]
    )


def test_blocks_stale_signal():
    validator = build_validator()

    result = validator.validate(
        trade_plan=build_valid_plan(),
        spread_points=0.50,
        atr_points=8.0,
        session_allowed=True,
        news_blocked=False,
        has_open_position=False,
        daily_limit_reached=False,
        signal_age_seconds=31,
    )

    assert result["approved"] is False
    assert (
        "signal_expired"
        in result["blocking_reasons"]
    )


def test_reports_multiple_blocking_reasons():
    validator = build_validator()

    plan = build_valid_plan()
    plan["reward_risk_ratio"] = 1.0
    plan["risk_points"] = 60.0

    result = validator.validate(
        trade_plan=plan,
        spread_points=2.0,
        atr_points=1.0,
        session_allowed=False,
        news_blocked=True,
        has_open_position=True,
        daily_limit_reached=True,
        signal_age_seconds=60,
    )

    assert result["approved"] is False
    assert result["decision"] == "BLOCK"
    assert len(result["blocking_reasons"]) >= 8


def test_warns_when_spread_is_near_limit():
    validator = build_validator()

    result = validator.validate(
        trade_plan=build_valid_plan(),
        spread_points=0.90,
        atr_points=8.0,
        session_allowed=True,
        news_blocked=False,
        has_open_position=False,
        daily_limit_reached=False,
        signal_age_seconds=5,
    )

    assert result["approved"] is True
    assert (
        "spread_near_limit"
        in result["warnings"]
    )


def test_rejects_invalid_trade_plan_type():
    validator = build_validator()

    with pytest.raises(
        TypeError,
        match="trade_plan",
    ):
        validator.validate(
            trade_plan=object(),
            spread_points=0.50,
            atr_points=8.0,
            session_allowed=True,
            news_blocked=False,
            has_open_position=False,
            daily_limit_reached=False,
            signal_age_seconds=5,
        )


def test_rejects_negative_spread():
    validator = build_validator()

    with pytest.raises(
        ValueError,
        match="spread_points",
    ):
        validator.validate(
            trade_plan=build_valid_plan(),
            spread_points=-0.1,
            atr_points=8.0,
            session_allowed=True,
            news_blocked=False,
            has_open_position=False,
            daily_limit_reached=False,
            signal_age_seconds=5,
        )


def test_rejects_negative_signal_age():
    validator = build_validator()

    with pytest.raises(
        ValueError,
        match="signal_age_seconds",
    ):
        validator.validate(
            trade_plan=build_valid_plan(),
            spread_points=0.50,
            atr_points=8.0,
            session_allowed=True,
            news_blocked=False,
            has_open_position=False,
            daily_limit_reached=False,
            signal_age_seconds=-1,
        )


def test_rejects_invalid_stop_threshold_order():
    with pytest.raises(
        ValueError,
        match="stop",
    ):
        TradeValidatorV2(
            minimum_reward_risk_ratio=2.0,
            minimum_stop_points=50.0,
            maximum_stop_points=10.0,
            maximum_spread_points=1.0,
            minimum_atr_points=3.0,
            maximum_signal_age_seconds=30,
        )
