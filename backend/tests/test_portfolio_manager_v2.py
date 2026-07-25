import pytest

from backend.portfolio.portfolio_manager_v2 import (
    PortfolioManagerV2,
)


def build_manager() -> PortfolioManagerV2:
    return PortfolioManagerV2(
        starting_balance=17000.0,
    )


def build_open_position(
    *,
    position_id: str = "position-001",
    symbol: str = "NQ",
    direction: str = "LONG",
    quantity: float = 2.0,
    entry_price: float = 100.0,
    current_price: float = 105.0,
    point_value: float = 2.0,
) -> dict[str, object]:
    return {
        "position_id": position_id,
        "symbol": symbol,
        "status": "OPEN",
        "direction": direction,
        "quantity": quantity,
        "entry_price": entry_price,
        "current_price": current_price,
        "stop_loss": 90.0,
        "take_profit": 120.0,
        "point_value": point_value,
        "realized_pnl": 0.0,
        "unrealized_pnl": 0.0,
    }


def test_starts_with_empty_portfolio():
    manager = build_manager()

    assert manager.get_open_positions() == []
    assert manager.get_closed_positions() == []

    summary = manager.get_summary()

    assert summary["starting_balance"] == 17000.0
    assert summary["open_positions"] == 0
    assert summary["closed_positions"] == 0
    assert summary["total_realized_pnl"] == 0.0
    assert summary["total_unrealized_pnl"] == 0.0
    assert summary["total_pnl"] == 0.0
    assert summary["account_equity"] == 17000.0


def test_adds_open_position():
    manager = build_manager()

    result = manager.add_position(
        position=build_open_position(),
    )

    assert result["added"] is True
    assert result["status"] == "ADDED"
    assert result["position_id"] == "position-001"

    positions = manager.get_open_positions()

    assert len(positions) == 1
    assert positions[0]["symbol"] == "NQ"


def test_rejects_duplicate_position_id():
    manager = build_manager()

    position = build_open_position()

    manager.add_position(
        position=position,
    )

    with pytest.raises(
        ValueError,
        match="position_id",
    ):
        manager.add_position(
            position=position,
        )


def test_updates_position():
    manager = build_manager()

    manager.add_position(
        position=build_open_position(),
    )

    result = manager.update_position(
        position_id="position-001",
        updates={
            "current_price": 110.0,
            "stop_loss": 100.0,
        },
    )

    assert result["updated"] is True
    assert result["position"]["current_price"] == 110.0
    assert result["position"]["stop_loss"] == 100.0


def test_calculates_long_unrealized_pnl():
    manager = build_manager()

    manager.add_position(
        position=build_open_position(
            direction="LONG",
            quantity=2.0,
            entry_price=100.0,
            current_price=105.0,
            point_value=2.0,
        ),
    )

    assert (
        manager.get_total_unrealized_pnl()
        == 20.0
    )


def test_calculates_short_unrealized_pnl():
    manager = build_manager()

    manager.add_position(
        position=build_open_position(
            direction="SHORT",
            quantity=2.0,
            entry_price=100.0,
            current_price=95.0,
            point_value=2.0,
        ),
    )

    assert (
        manager.get_total_unrealized_pnl()
        == 20.0
    )


def test_closes_position():
    manager = build_manager()

    manager.add_position(
        position=build_open_position(),
    )

    result = manager.close_position(
        position_id="position-001",
        exit_price=110.0,
    )

    assert result["closed"] is True
    assert result["status"] == "CLOSED"

    position = result["position"]

    assert position["status"] == "CLOSED"
    assert position["exit_price"] == 110.0
    assert position["realized_pnl"] == 40.0

    assert manager.get_open_positions() == []
    assert len(manager.get_closed_positions()) == 1


def test_calculates_realized_pnl():
    manager = build_manager()

    manager.add_position(
        position=build_open_position(),
    )

    manager.close_position(
        position_id="position-001",
        exit_price=110.0,
    )

    assert (
        manager.get_total_realized_pnl()
        == 40.0
    )


def test_calculates_account_equity():
    manager = build_manager()

    manager.add_position(
        position=build_open_position(
            current_price=105.0,
        ),
    )

    assert manager.get_account_equity() == 17020.0

    manager.close_position(
        position_id="position-001",
        exit_price=110.0,
    )

    assert manager.get_account_equity() == 17040.0


def test_calculates_available_balance():
    manager = build_manager()

    manager.add_position(
        position=build_open_position(),
    )

    manager.close_position(
        position_id="position-001",
        exit_price=110.0,
    )

    assert (
        manager.get_available_balance()
        == 17040.0
    )


def test_returns_complete_summary():
    manager = build_manager()

    manager.add_position(
        position=build_open_position(
            position_id="position-001",
            symbol="NQ",
            current_price=105.0,
        ),
    )

    manager.add_position(
        position=build_open_position(
            position_id="position-002",
            symbol="ES",
            direction="SHORT",
            quantity=1.0,
            entry_price=100.0,
            current_price=96.0,
            point_value=5.0,
        ),
    )

    summary = manager.get_summary()

    assert summary["open_positions"] == 2
    assert summary["closed_positions"] == 0
    assert summary["total_unrealized_pnl"] == 40.0
    assert summary["total_realized_pnl"] == 0.0
    assert summary["total_pnl"] == 40.0
    assert summary["account_equity"] == 17040.0


def test_getters_do_not_expose_internal_state():
    manager = build_manager()

    manager.add_position(
        position=build_open_position(),
    )

    positions = manager.get_open_positions()

    positions[0]["symbol"] = "MODIFIED"

    fresh_positions = manager.get_open_positions()

    assert fresh_positions[0]["symbol"] == "NQ"


def test_rejects_invalid_position_type():
    manager = build_manager()

    with pytest.raises(
        TypeError,
        match="position",
    ):
        manager.add_position(
            position=object(),
        )


def test_rejects_missing_position_id():
    manager = build_manager()

    position = build_open_position()
    position.pop(
        "position_id"
    )

    with pytest.raises(
        ValueError,
        match="position_id",
    ):
        manager.add_position(
            position=position,
        )


def test_rejects_unknown_position_update():
    manager = build_manager()

    with pytest.raises(
        KeyError,
        match="position_id",
    ):
        manager.update_position(
            position_id="unknown",
            updates={
                "current_price": 110.0,
            },
        )


def test_rejects_unknown_position_close():
    manager = build_manager()

    with pytest.raises(
        KeyError,
        match="position_id",
    ):
        manager.close_position(
            position_id="unknown",
            exit_price=110.0,
        )


def test_rejects_invalid_exit_price():
    manager = build_manager()

    manager.add_position(
        position=build_open_position(),
    )

    with pytest.raises(
        ValueError,
        match="exit_price",
    ):
        manager.close_position(
            position_id="position-001",
            exit_price=0.0,
        )


def test_rejects_invalid_starting_balance():
    with pytest.raises(
        ValueError,
        match="starting_balance",
    ):
        PortfolioManagerV2(
            starting_balance=0.0,
        )
