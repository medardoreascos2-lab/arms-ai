from backend.account.account_state_manager_v2 import (
    AccountStateManagerV2,
)


def build_manager(
    profit_target=3000.0,
):
    return AccountStateManagerV2(
        starting_balance=50000.0,
        maximum_daily_loss=1000.0,
        maximum_total_drawdown=2000.0,
        profit_target=profit_target,
    )


def update_profit(
    manager,
    *,
    realized_pnl,
    unrealized_pnl=0.0,
):
    return manager.update_from_portfolio(
        portfolio_summary={
            "open_positions": 0,
            "closed_positions": 1,
            "total_realized_pnl":
                realized_pnl,
            "total_unrealized_pnl":
                unrealized_pnl,
            "total_pnl":
                realized_pnl
                + unrealized_pnl,
            "account_equity":
                50000.0
                + realized_pnl
                + unrealized_pnl,
        }
    )["state"]


def test_initial_profit_progress_state():
    state = build_manager().get_state()

    assert state["profit_target"] == 3000.0
    assert state["profit_achieved"] == 0.0
    assert state["profit_remaining"] == 3000.0
    assert (
        state["profit_progress_percent"]
        == 0.0
    )
    assert state["target_reached"] is False


def test_realized_profit_updates_progress():
    state = update_profit(
        build_manager(),
        realized_pnl=1500.0,
    )

    assert state["profit_achieved"] == 1500.0
    assert state["profit_remaining"] == 1500.0
    assert (
        state["profit_progress_percent"]
        == 50.0
    )
    assert state["target_reached"] is False


def test_unrealized_profit_does_not_advance_target():
    state = update_profit(
        build_manager(),
        realized_pnl=500.0,
        unrealized_pnl=2500.0,
    )

    assert state["profit_achieved"] == 500.0
    assert state["profit_remaining"] == 2500.0

    assert round(
        state["profit_progress_percent"],
        6,
    ) == round(
        500.0 / 3000.0 * 100.0,
        6,
    )

    assert state["target_reached"] is False


def test_profit_target_reached():
    state = update_profit(
        build_manager(),
        realized_pnl=3000.0,
    )

    assert state["profit_achieved"] == 3000.0
    assert state["profit_remaining"] == 0.0
    assert (
        state["profit_progress_percent"]
        == 100.0
    )
    assert state["target_reached"] is True


def test_profit_progress_caps_at_100_percent():
    state = update_profit(
        build_manager(),
        realized_pnl=4500.0,
    )

    assert state["profit_achieved"] == 4500.0
    assert state["profit_remaining"] == 0.0
    assert (
        state["profit_progress_percent"]
        == 100.0
    )
    assert state["target_reached"] is True


def test_negative_realized_pnl_does_not_make_negative_progress():
    state = update_profit(
        build_manager(),
        realized_pnl=-500.0,
    )

    assert state["profit_achieved"] == -500.0
    assert state["profit_remaining"] == 3500.0
    assert (
        state["profit_progress_percent"]
        == 0.0
    )
    assert state["target_reached"] is False


def test_account_without_profit_target_is_safe():
    state = update_profit(
        build_manager(
            profit_target=None,
        ),
        realized_pnl=1000.0,
    )

    assert state["profit_target"] is None
    assert state["profit_achieved"] == 1000.0
    assert state["profit_remaining"] is None
    assert (
        state["profit_progress_percent"]
        is None
    )
    assert state["target_reached"] is False
