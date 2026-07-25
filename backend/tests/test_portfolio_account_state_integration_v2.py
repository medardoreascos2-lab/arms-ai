import pytest

from backend.account.account_state_manager_v2 import (
    AccountStateManagerV2,
)
from backend.portfolio.portfolio_manager_v2 import (
    PortfolioManagerV2,
)


def build_account_state() -> AccountStateManagerV2:
    return AccountStateManagerV2(
        starting_balance=17000.0,
        maximum_daily_loss=3000.0,
        maximum_total_drawdown=4500.0,
    )


def build_manager(
    *,
    account_state_manager_v2=None,
) -> PortfolioManagerV2:
    return PortfolioManagerV2(
        starting_balance=17000.0,
        account_state_manager_v2=(
            account_state_manager_v2
        ),
    )


def build_position() -> dict[str, object]:
    return {
        "position_id": "pos-1",
        "symbol": "NQ",
        "status": "OPEN",
        "direction": "LONG",
        "quantity": 2.0,
        "entry_price": 100.0,
        "current_price": 105.0,
        "stop_loss": 90.0,
        "take_profit": 120.0,
        "point_value": 2.0,
        "realized_pnl": 0.0,
        "unrealized_pnl": 0.0,
    }


def test_accepts_none_account_state_manager():
    manager = build_manager(
        account_state_manager_v2=None,
    )

    assert (
        manager.account_state_manager_v2
        is None
    )


def test_accepts_valid_account_state_manager():
    account_state = build_account_state()

    manager = build_manager(
        account_state_manager_v2=account_state,
    )

    assert (
        manager.account_state_manager_v2
        is account_state
    )


def test_rejects_invalid_account_state_manager():
    with pytest.raises(
        TypeError,
        match="account_state_manager_v2",
    ):
        build_manager(
            account_state_manager_v2=object(),
        )


def test_add_position_updates_account_state():
    account_state = build_account_state()

    manager = build_manager(
        account_state_manager_v2=account_state,
    )

    manager.add_position(
        position=build_position(),
    )

    state = account_state.get_state()

    assert state["open_positions"] == 1
    assert state["closed_positions"] == 0
    assert state["unrealized_pnl"] == 20.0
    assert state["equity"] == 17020.0


def test_update_position_updates_account_state():
    account_state = build_account_state()

    manager = build_manager(
        account_state_manager_v2=account_state,
    )

    manager.add_position(
        position=build_position(),
    )

    manager.update_position(
        position_id="pos-1",
        updates={
            "current_price": 110.0,
        },
    )

    state = account_state.get_state()

    assert state["unrealized_pnl"] == 40.0
    assert state["equity"] == 17040.0


def test_close_position_updates_account_state():
    account_state = build_account_state()

    manager = build_manager(
        account_state_manager_v2=account_state,
    )

    manager.add_position(
        position=build_position(),
    )

    manager.close_position(
        position_id="pos-1",
        exit_price=110.0,
    )

    state = account_state.get_state()

    assert state["open_positions"] == 0
    assert state["closed_positions"] == 1
    assert state["realized_pnl"] == 40.0
    assert state["unrealized_pnl"] == 0.0
    assert state["balance"] == 17040.0
    assert state["equity"] == 17040.0


def test_returns_account_state_in_summary():
    account_state = build_account_state()

    manager = build_manager(
        account_state_manager_v2=account_state,
    )

    manager.add_position(
        position=build_position(),
    )

    summary = manager.get_summary()

    assert (
        summary["account_state"][
            "open_positions"
        ]
        == 1
    )

    assert (
        summary["account_state"][
            "equity"
        ]
        == 17020.0
    )


def test_without_account_state_returns_none():
    manager = build_manager(
        account_state_manager_v2=None,
    )

    summary = manager.get_summary()

    assert summary["account_state"] is None
