import pytest

from backend.account.account_state_manager_v2 import (
    AccountStateManagerV2,
)


def build_manager() -> AccountStateManagerV2:
    return AccountStateManagerV2(
        starting_balance=17000.0,
        maximum_daily_loss=3000.0,
        maximum_total_drawdown=4500.0,
    )


def test_starts_with_initial_state():
    manager = build_manager()

    state = manager.get_state()

    assert state["starting_balance"] == 17000.0
    assert state["balance"] == 17000.0
    assert state["equity"] == 17000.0
    assert state["realized_pnl"] == 0.0
    assert state["unrealized_pnl"] == 0.0
    assert state["total_pnl"] == 0.0
    assert state["daily_pnl"] == 0.0
    assert state["drawdown"] == 0.0
    assert state["open_positions"] == 0
    assert state["closed_positions"] == 0
    assert state["open_risk"] == 0.0
    assert state["trading_blocked"] is False


def test_updates_from_portfolio_summary():
    manager = build_manager()

    result = manager.update_from_portfolio(
        portfolio_summary={
            "starting_balance": 17000.0,
            "open_positions": 2,
            "closed_positions": 1,
            "total_realized_pnl": 150.0,
            "total_unrealized_pnl": -40.0,
            "total_pnl": 110.0,
            "account_equity": 17110.0,
        },
    )

    assert result["updated"] is True

    state = result["state"]

    assert state["balance"] == 17150.0
    assert state["equity"] == 17110.0
    assert state["realized_pnl"] == 150.0
    assert state["unrealized_pnl"] == -40.0
    assert state["total_pnl"] == 110.0
    assert state["open_positions"] == 2
    assert state["closed_positions"] == 1


def test_updates_open_risk():
    manager = build_manager()

    result = manager.update_open_risk(
        open_risk=850.0,
    )

    assert result["updated"] is True
    assert result["state"]["open_risk"] == 850.0


def test_records_daily_pnl():
    manager = build_manager()

    result = manager.record_daily_pnl(
        daily_pnl=-500.0,
    )

    assert result["updated"] is True
    assert result["state"]["daily_pnl"] == -500.0
    assert result["state"]["daily_loss_used"] == 500.0
    assert (
        result["state"]["remaining_daily_loss_capacity"]
        == 2500.0
    )


def test_calculates_drawdown():
    manager = build_manager()

    manager.update_from_portfolio(
        portfolio_summary={
            "starting_balance": 17000.0,
            "open_positions": 1,
            "closed_positions": 0,
            "total_realized_pnl": 0.0,
            "total_unrealized_pnl": -700.0,
            "total_pnl": -700.0,
            "account_equity": 16300.0,
        },
    )

    state = manager.get_state()

    assert state["drawdown"] == 700.0
    assert (
        state["remaining_drawdown_capacity"]
        == 3800.0
    )


def test_tracks_peak_equity():
    manager = build_manager()

    manager.update_from_portfolio(
        portfolio_summary={
            "starting_balance": 17000.0,
            "open_positions": 1,
            "closed_positions": 0,
            "total_realized_pnl": 0.0,
            "total_unrealized_pnl": 500.0,
            "total_pnl": 500.0,
            "account_equity": 17500.0,
        },
    )

    manager.update_from_portfolio(
        portfolio_summary={
            "starting_balance": 17000.0,
            "open_positions": 1,
            "closed_positions": 0,
            "total_realized_pnl": 0.0,
            "total_unrealized_pnl": 100.0,
            "total_pnl": 100.0,
            "account_equity": 17100.0,
        },
    )

    state = manager.get_state()

    assert state["peak_equity"] == 17500.0
    assert state["drawdown"] == 400.0


def test_blocks_when_daily_loss_limit_reached():
    manager = build_manager()

    result = manager.record_daily_pnl(
        daily_pnl=-3000.0,
    )

    state = result["state"]

    assert state["trading_blocked"] is True
    assert (
        "daily_loss_limit_reached"
        in state["blocking_reasons"]
    )


def test_blocks_when_drawdown_limit_reached():
    manager = build_manager()

    manager.update_from_portfolio(
        portfolio_summary={
            "starting_balance": 17000.0,
            "open_positions": 0,
            "closed_positions": 1,
            "total_realized_pnl": -4500.0,
            "total_unrealized_pnl": 0.0,
            "total_pnl": -4500.0,
            "account_equity": 12500.0,
        },
    )

    state = manager.get_state()

    assert state["trading_blocked"] is True
    assert (
        "maximum_total_drawdown_reached"
        in state["blocking_reasons"]
    )


def test_resets_daily_state():
    manager = build_manager()

    manager.record_daily_pnl(
        daily_pnl=-500.0,
    )

    result = manager.reset_daily_state()

    assert result["reset"] is True
    assert result["state"]["daily_pnl"] == 0.0
    assert result["state"]["daily_loss_used"] == 0.0
    assert (
        result["state"]["remaining_daily_loss_capacity"]
        == 3000.0
    )


def test_get_state_does_not_expose_internal_state():
    manager = build_manager()

    state = manager.get_state()
    state["balance"] = 1.0
    state["blocking_reasons"].append(
        "modified"
    )

    fresh_state = manager.get_state()

    assert fresh_state["balance"] == 17000.0
    assert "modified" not in fresh_state[
        "blocking_reasons"
    ]


def test_rejects_invalid_portfolio_summary_type():
    manager = build_manager()

    with pytest.raises(
        TypeError,
        match="portfolio_summary",
    ):
        manager.update_from_portfolio(
            portfolio_summary=object(),
        )


@pytest.mark.parametrize(
    (
        "field",
        "value",
    ),
    [
        (
            "open_positions",
            -1,
        ),
        (
            "closed_positions",
            -1,
        ),
        (
            "account_equity",
            0.0,
        ),
    ],
)
def test_rejects_invalid_portfolio_values(
    field,
    value,
):
    manager = build_manager()

    summary = {
        "starting_balance": 17000.0,
        "open_positions": 0,
        "closed_positions": 0,
        "total_realized_pnl": 0.0,
        "total_unrealized_pnl": 0.0,
        "total_pnl": 0.0,
        "account_equity": 17000.0,
    }

    summary[field] = value

    with pytest.raises(
        ValueError,
        match=field,
    ):
        manager.update_from_portfolio(
            portfolio_summary=summary,
        )


def test_rejects_negative_open_risk():
    manager = build_manager()

    with pytest.raises(
        ValueError,
        match="open_risk",
    ):
        manager.update_open_risk(
            open_risk=-1.0,
        )


@pytest.mark.parametrize(
    (
        "parameter",
        "value",
    ),
    [
        (
            "starting_balance",
            0.0,
        ),
        (
            "maximum_daily_loss",
            0.0,
        ),
        (
            "maximum_total_drawdown",
            0.0,
        ),
    ],
)
def test_rejects_invalid_configuration(
    parameter,
    value,
):
    configuration = {
        "starting_balance": 17000.0,
        "maximum_daily_loss": 3000.0,
        "maximum_total_drawdown": 4500.0,
    }

    configuration[
        parameter
    ] = value

    with pytest.raises(
        ValueError,
        match=parameter,
    ):
        AccountStateManagerV2(
            **configuration,
        )


def test_none_maximum_daily_loss_does_not_block():
    manager = AccountStateManagerV2(
        starting_balance=150000.0,
        maximum_daily_loss=None,
        maximum_total_drawdown=4500.0,
    )

    result = manager.record_daily_pnl(
        daily_pnl=-5000.0,
    )

    state = result["state"]

    assert state["daily_loss_used"] == 5000.0
    assert (
        state["remaining_daily_loss_capacity"]
        is None
    )
    assert (
        "daily_loss_limit_reached"
        not in state["blocking_reasons"]
    )
