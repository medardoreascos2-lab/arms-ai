import pytest

from backend.execution.position_sizing_engine_v2 import (
    PositionSizingEngineV2,
)
from backend.execution.risk_manager_v2 import (
    RiskManagerV2,
)


def build_manager() -> RiskManagerV2:
    return RiskManagerV2(
        position_sizing_engine=(
            PositionSizingEngineV2()
        ),
        maximum_daily_loss=3000.0,
        maximum_total_drawdown=4500.0,
        maximum_contracts=20,
        maximum_open_positions=1,
    )


def test_approves_valid_trade():
    manager = build_manager()

    result = manager.evaluate(
        account_balance=17000.0,
        risk_percent=0.5,
        stop_points=20.0,
        point_value=2.0,
        daily_pnl=-500.0,
        total_drawdown=1000.0,
        open_positions=0,
    )

    assert result["approved"] is True
    assert result["status"] == "APPROVED"
    assert result["decision"] == "ALLOW_TRADE"
    assert result["contracts"] == 2
    assert result["risk_amount"] == 85.0
    assert result["actual_risk"] == 80.0
    assert result["blocking_reasons"] == []


def test_blocks_when_daily_loss_limit_reached():
    manager = build_manager()

    result = manager.evaluate(
        account_balance=17000.0,
        risk_percent=0.5,
        stop_points=20.0,
        point_value=2.0,
        daily_pnl=-3000.0,
        total_drawdown=1000.0,
        open_positions=0,
    )

    assert result["approved"] is False
    assert result["status"] == "BLOCKED"
    assert (
        "daily_loss_limit_reached"
        in result["blocking_reasons"]
    )


def test_blocks_when_projected_daily_loss_exceeds_limit():
    manager = build_manager()

    result = manager.evaluate(
        account_balance=17000.0,
        risk_percent=0.5,
        stop_points=20.0,
        point_value=2.0,
        daily_pnl=-2950.0,
        total_drawdown=1000.0,
        open_positions=0,
    )

    assert result["approved"] is False
    assert (
        "projected_daily_loss_exceeded"
        in result["blocking_reasons"]
    )


def test_blocks_when_total_drawdown_limit_reached():
    manager = build_manager()

    result = manager.evaluate(
        account_balance=17000.0,
        risk_percent=0.5,
        stop_points=20.0,
        point_value=2.0,
        daily_pnl=-500.0,
        total_drawdown=4500.0,
        open_positions=0,
    )

    assert result["approved"] is False
    assert (
        "total_drawdown_limit_reached"
        in result["blocking_reasons"]
    )


def test_blocks_when_projected_drawdown_exceeds_limit():
    manager = build_manager()

    result = manager.evaluate(
        account_balance=17000.0,
        risk_percent=0.5,
        stop_points=20.0,
        point_value=2.0,
        daily_pnl=-500.0,
        total_drawdown=4450.0,
        open_positions=0,
    )

    assert result["approved"] is False
    assert (
        "projected_total_drawdown_exceeded"
        in result["blocking_reasons"]
    )


def test_blocks_when_open_position_limit_reached():
    manager = build_manager()

    result = manager.evaluate(
        account_balance=17000.0,
        risk_percent=0.5,
        stop_points=20.0,
        point_value=2.0,
        daily_pnl=-500.0,
        total_drawdown=1000.0,
        open_positions=1,
    )

    assert result["approved"] is False
    assert (
        "maximum_open_positions_reached"
        in result["blocking_reasons"]
    )


def test_blocks_when_position_sizing_not_approved():
    manager = build_manager()

    result = manager.evaluate(
        account_balance=500.0,
        risk_percent=0.25,
        stop_points=100.0,
        point_value=20.0,
        daily_pnl=0.0,
        total_drawdown=0.0,
        open_positions=0,
    )

    assert result["approved"] is False
    assert result["contracts"] == 0
    assert (
        "position_sizing_not_approved"
        in result["blocking_reasons"]
    )


def test_blocks_contracts_above_maximum():
    manager = RiskManagerV2(
        position_sizing_engine=(
            PositionSizingEngineV2()
        ),
        maximum_daily_loss=3000.0,
        maximum_total_drawdown=4500.0,
        maximum_contracts=2,
        maximum_open_positions=1,
    )

    result = manager.evaluate(
        account_balance=100000.0,
        risk_percent=1.0,
        stop_points=10.0,
        point_value=2.0,
        daily_pnl=0.0,
        total_drawdown=0.0,
        open_positions=0,
    )

    assert result["approved"] is False
    assert result["contracts"] > 2
    assert (
        "maximum_contracts_exceeded"
        in result["blocking_reasons"]
    )


def test_returns_remaining_daily_loss_capacity():
    manager = build_manager()

    result = manager.evaluate(
        account_balance=17000.0,
        risk_percent=0.5,
        stop_points=20.0,
        point_value=2.0,
        daily_pnl=-500.0,
        total_drawdown=1000.0,
        open_positions=0,
    )

    assert (
        result["remaining_daily_loss_capacity"]
        == 2500.0
    )

    assert (
        result["remaining_drawdown_capacity"]
        == 3500.0
    )


def test_positive_daily_pnl_does_not_count_as_loss():
    manager = build_manager()

    result = manager.evaluate(
        account_balance=17000.0,
        risk_percent=0.5,
        stop_points=20.0,
        point_value=2.0,
        daily_pnl=500.0,
        total_drawdown=1000.0,
        open_positions=0,
    )

    assert result["approved"] is True
    assert result["daily_loss_used"] == 0.0


def test_rejects_invalid_position_sizing_engine():
    with pytest.raises(
        TypeError,
        match="position_sizing_engine",
    ):
        RiskManagerV2(
            position_sizing_engine=object(),
            maximum_daily_loss=3000.0,
            maximum_total_drawdown=4500.0,
            maximum_contracts=20,
            maximum_open_positions=1,
        )


@pytest.mark.parametrize(
    (
        "parameter",
        "value",
    ),
    [
        (
            "maximum_daily_loss",
            0.0,
        ),
        (
            "maximum_total_drawdown",
            0.0,
        ),
        (
            "maximum_contracts",
            0,
        ),
        (
            "maximum_open_positions",
            0,
        ),
    ],
)
def test_rejects_invalid_configuration(
    parameter,
    value,
):
    configuration = {
        "position_sizing_engine": (
            PositionSizingEngineV2()
        ),
        "maximum_daily_loss": 3000.0,
        "maximum_total_drawdown": 4500.0,
        "maximum_contracts": 20,
        "maximum_open_positions": 1,
    }

    configuration[
        parameter
    ] = value

    with pytest.raises(
        ValueError,
        match=parameter,
    ):
        RiskManagerV2(
            **configuration,
        )


def test_rejects_negative_total_drawdown():
    manager = build_manager()

    with pytest.raises(
        ValueError,
        match="total_drawdown",
    ):
        manager.evaluate(
            account_balance=17000.0,
            risk_percent=0.5,
            stop_points=20.0,
            point_value=2.0,
            daily_pnl=0.0,
            total_drawdown=-1.0,
            open_positions=0,
        )


def test_rejects_negative_open_positions():
    manager = build_manager()

    with pytest.raises(
        ValueError,
        match="open_positions",
    ):
        manager.evaluate(
            account_balance=17000.0,
            risk_percent=0.5,
            stop_points=20.0,
            point_value=2.0,
            daily_pnl=0.0,
            total_drawdown=0.0,
            open_positions=-1,
        )
