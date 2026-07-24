import pytest

from backend.execution.trade_planner_v2 import (
    TradePlannerV2,
)


def build_planner() -> TradePlannerV2:
    return TradePlannerV2(
        minimum_reward_risk_ratio=2.0,
    )


def test_builds_long_trade_plan():
    planner = build_planner()

    result = planner.build(
        decision="EXECUTE_LONG",
        current_price=100.0,
        stop_loss=95.0,
        contracts=2,
        probability=0.92,
        confluence_score=0.90,
        grade="A+",
    )

    assert result["approved"] is True
    assert result["direction"] == "LONG"
    assert result["entry_price"] == 100.0
    assert result["stop_loss"] == 95.0
    assert result["take_profit"] == 110.0
    assert result["risk_points"] == 5.0
    assert result["reward_points"] == 10.0
    assert result["reward_risk_ratio"] == 2.0
    assert result["contracts"] == 2
    assert result["probability"] == 0.92
    assert result["confluence_score"] == 0.90
    assert result["grade"] == "A+"


def test_builds_short_trade_plan():
    planner = build_planner()

    result = planner.build(
        decision="EXECUTE_SHORT",
        current_price=100.0,
        stop_loss=105.0,
        contracts=1,
        probability=0.88,
        confluence_score=0.85,
        grade="A",
    )

    assert result["approved"] is True
    assert result["direction"] == "SHORT"
    assert result["entry_price"] == 100.0
    assert result["stop_loss"] == 105.0
    assert result["take_profit"] == 90.0
    assert result["risk_points"] == 5.0
    assert result["reward_points"] == 10.0
    assert result["reward_risk_ratio"] == 2.0


def test_supports_custom_reward_risk_ratio():
    planner = build_planner()

    result = planner.build(
        decision="EXECUTE_LONG",
        current_price=100.0,
        stop_loss=96.0,
        contracts=1,
        probability=0.90,
        confluence_score=0.90,
        grade="A+",
        reward_risk_ratio=3.0,
    )

    assert result["risk_points"] == 4.0
    assert result["reward_points"] == 12.0
    assert result["take_profit"] == 112.0
    assert result["reward_risk_ratio"] == 3.0


def test_returns_inactive_plan_for_wait():
    planner = build_planner()

    result = planner.build(
        decision="WAIT",
        current_price=100.0,
        stop_loss=95.0,
        contracts=2,
        probability=0.70,
        confluence_score=0.70,
        grade="B",
    )

    assert result["approved"] is False
    assert result["status"] == "INACTIVE"
    assert result["direction"] is None
    assert result["entry_price"] is None
    assert result["stop_loss"] is None
    assert result["take_profit"] is None
    assert result["reason"] == "execution_not_approved"


def test_returns_inactive_plan_for_block():
    planner = build_planner()

    result = planner.build(
        decision="BLOCK",
        current_price=100.0,
        stop_loss=95.0,
        contracts=2,
        probability=0.95,
        confluence_score=0.95,
        grade="A+",
    )

    assert result["approved"] is False
    assert result["status"] == "INACTIVE"
    assert result["reason"] == "execution_not_approved"


def test_rejects_long_stop_above_entry():
    planner = build_planner()

    with pytest.raises(
        ValueError,
        match="stop_loss",
    ):
        planner.build(
            decision="EXECUTE_LONG",
            current_price=100.0,
            stop_loss=105.0,
            contracts=1,
            probability=0.90,
            confluence_score=0.90,
            grade="A",
        )


def test_rejects_short_stop_below_entry():
    planner = build_planner()

    with pytest.raises(
        ValueError,
        match="stop_loss",
    ):
        planner.build(
            decision="EXECUTE_SHORT",
            current_price=100.0,
            stop_loss=95.0,
            contracts=1,
            probability=0.90,
            confluence_score=0.90,
            grade="A",
        )


def test_rejects_invalid_contracts_for_execution():
    planner = build_planner()

    with pytest.raises(
        ValueError,
        match="contracts",
    ):
        planner.build(
            decision="EXECUTE_LONG",
            current_price=100.0,
            stop_loss=95.0,
            contracts=0,
            probability=0.90,
            confluence_score=0.90,
            grade="A",
        )


def test_rejects_invalid_probability():
    planner = build_planner()

    with pytest.raises(
        ValueError,
        match="probability",
    ):
        planner.build(
            decision="EXECUTE_LONG",
            current_price=100.0,
            stop_loss=95.0,
            contracts=1,
            probability=1.1,
            confluence_score=0.90,
            grade="A",
        )


def test_rejects_invalid_confluence_score():
    planner = build_planner()

    with pytest.raises(
        ValueError,
        match="confluence_score",
    ):
        planner.build(
            decision="EXECUTE_LONG",
            current_price=100.0,
            stop_loss=95.0,
            contracts=1,
            probability=0.90,
            confluence_score=-0.1,
            grade="A",
        )


def test_rejects_reward_risk_below_minimum():
    planner = build_planner()

    with pytest.raises(
        ValueError,
        match="reward_risk_ratio",
    ):
        planner.build(
            decision="EXECUTE_LONG",
            current_price=100.0,
            stop_loss=95.0,
            contracts=1,
            probability=0.90,
            confluence_score=0.90,
            grade="A",
            reward_risk_ratio=1.5,
        )


def test_rejects_invalid_default_reward_risk_ratio():
    with pytest.raises(
        ValueError,
        match="minimum_reward_risk_ratio",
    ):
        TradePlannerV2(
            minimum_reward_risk_ratio=0.0,
        )
