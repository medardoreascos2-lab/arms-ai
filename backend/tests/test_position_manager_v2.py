import pytest

from backend.execution.position_manager_v2 import (
    PositionManagerV2,
)


def build_manager() -> PositionManagerV2:
    return PositionManagerV2(
        point_value=2.0,
    )


def build_filled_buy_execution() -> dict[str, object]:
    return {
        "accepted": True,
        "status": "FILLED",
        "execution_mode": "PAPER",
        "order_id": "order-123",
        "symbol": "NQ",
        "side": "BUY",
        "order_type": "MARKET",
        "quantity": 2,
        "requested_price": 100.0,
        "filled_price": 100.25,
        "stop_loss": 95.0,
        "take_profit": 110.0,
        "rejection_reasons": [],
    }


def test_opens_long_position_from_filled_buy():
    manager = build_manager()

    result = manager.open_position(
        execution=build_filled_buy_execution(),
    )

    assert result["opened"] is True
    assert result["status"] == "OPEN"
    assert result["symbol"] == "NQ"
    assert result["direction"] == "LONG"
    assert result["quantity"] == 2
    assert result["entry_price"] == 100.25
    assert result["current_price"] == 100.25
    assert result["stop_loss"] == 95.0
    assert result["take_profit"] == 110.0
    assert result["unrealized_pnl"] == 0.0
    assert result["order_id"] == "order-123"
    assert result["position_id"]


def test_opens_short_position_from_filled_sell():
    manager = build_manager()

    execution = build_filled_buy_execution()

    execution.update(
        {
            "side": "SELL",
            "filled_price": 99.75,
            "stop_loss": 105.0,
            "take_profit": 90.0,
        }
    )

    result = manager.open_position(
        execution=execution,
    )

    assert result["opened"] is True
    assert result["direction"] == "SHORT"
    assert result["entry_price"] == 99.75


def test_does_not_open_submitted_order():
    manager = build_manager()

    execution = build_filled_buy_execution()
    execution["status"] = "SUBMITTED"
    execution["filled_price"] = None

    result = manager.open_position(
        execution=execution,
    )

    assert result["opened"] is False
    assert result["status"] == "INACTIVE"
    assert result["reason"] == "execution_not_filled"


def test_does_not_open_rejected_execution():
    manager = build_manager()

    execution = build_filled_buy_execution()
    execution["accepted"] = False
    execution["status"] = "REJECTED"

    result = manager.open_position(
        execution=execution,
    )

    assert result["opened"] is False
    assert result["status"] == "INACTIVE"
    assert result["reason"] == "execution_not_accepted"


def test_updates_long_position_profit():
    manager = build_manager()

    position = manager.open_position(
        execution=build_filled_buy_execution(),
    )

    result = manager.update_position(
        position=position,
        current_price=105.25,
    )

    assert result["current_price"] == 105.25
    assert result["unrealized_points"] == 5.0
    assert result["unrealized_pnl"] == 20.0
    assert result["status"] == "OPEN"


def test_updates_short_position_profit():
    manager = build_manager()

    execution = build_filled_buy_execution()

    execution.update(
        {
            "side": "SELL",
            "filled_price": 100.0,
            "stop_loss": 105.0,
            "take_profit": 90.0,
        }
    )

    position = manager.open_position(
        execution=execution,
    )

    result = manager.update_position(
        position=position,
        current_price=95.0,
    )

    assert result["unrealized_points"] == 5.0
    assert result["unrealized_pnl"] == 20.0


def test_closes_long_position_at_take_profit():
    manager = build_manager()

    position = manager.open_position(
        execution=build_filled_buy_execution(),
    )

    result = manager.update_position(
        position=position,
        current_price=110.0,
    )

    assert result["status"] == "CLOSED"
    assert result["close_reason"] == "TAKE_PROFIT"
    assert result["exit_price"] == 110.0
    assert result["realized_pnl"] > 0


def test_closes_long_position_at_stop_loss():
    manager = build_manager()

    position = manager.open_position(
        execution=build_filled_buy_execution(),
    )

    result = manager.update_position(
        position=position,
        current_price=95.0,
    )

    assert result["status"] == "CLOSED"
    assert result["close_reason"] == "STOP_LOSS"
    assert result["exit_price"] == 95.0
    assert result["realized_pnl"] < 0


def test_closes_short_position_at_take_profit():
    manager = build_manager()

    execution = build_filled_buy_execution()

    execution.update(
        {
            "side": "SELL",
            "filled_price": 100.0,
            "stop_loss": 105.0,
            "take_profit": 90.0,
        }
    )

    position = manager.open_position(
        execution=execution,
    )

    result = manager.update_position(
        position=position,
        current_price=90.0,
    )

    assert result["status"] == "CLOSED"
    assert result["close_reason"] == "TAKE_PROFIT"
    assert result["realized_pnl"] > 0


def test_closes_short_position_at_stop_loss():
    manager = build_manager()

    execution = build_filled_buy_execution()

    execution.update(
        {
            "side": "SELL",
            "filled_price": 100.0,
            "stop_loss": 105.0,
            "take_profit": 90.0,
        }
    )

    position = manager.open_position(
        execution=execution,
    )

    result = manager.update_position(
        position=position,
        current_price=105.0,
    )

    assert result["status"] == "CLOSED"
    assert result["close_reason"] == "STOP_LOSS"
    assert result["realized_pnl"] < 0


def test_rejects_invalid_execution_type():
    manager = build_manager()

    with pytest.raises(
        TypeError,
        match="execution",
    ):
        manager.open_position(
            execution=object(),
        )


def test_rejects_invalid_execution_side():
    manager = build_manager()

    execution = build_filled_buy_execution()
    execution["side"] = "HOLD"

    with pytest.raises(
        ValueError,
        match="side",
    ):
        manager.open_position(
            execution=execution,
        )


def test_rejects_missing_filled_price():
    manager = build_manager()

    execution = build_filled_buy_execution()
    execution["filled_price"] = None

    with pytest.raises(
        ValueError,
        match="filled_price",
    ):
        manager.open_position(
            execution=execution,
        )


def test_rejects_invalid_position_type():
    manager = build_manager()

    with pytest.raises(
        TypeError,
        match="position",
    ):
        manager.update_position(
            position=object(),
            current_price=105.0,
        )


def test_rejects_update_of_closed_position():
    manager = build_manager()

    position = manager.open_position(
        execution=build_filled_buy_execution(),
    )

    closed = manager.update_position(
        position=position,
        current_price=110.0,
    )

    with pytest.raises(
        ValueError,
        match="position",
    ):
        manager.update_position(
            position=closed,
            current_price=111.0,
        )


def test_rejects_invalid_current_price():
    manager = build_manager()

    position = manager.open_position(
        execution=build_filled_buy_execution(),
    )

    with pytest.raises(
        ValueError,
        match="current_price",
    ):
        manager.update_position(
            position=position,
            current_price=0.0,
        )


def test_rejects_invalid_point_value():
    with pytest.raises(
        ValueError,
        match="point_value",
    ):
        PositionManagerV2(
            point_value=0.0,
        )
