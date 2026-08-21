from backend.account.account_state_manager_v2 import (
    AccountStateManagerV2,
)
from backend.services.runtime_context_v2 import (
    build_runtime_context,
)


def build_manager(
    *,
    account_stage="TRADING_COMBINE",
    profit_target=3000.0,
):
    return AccountStateManagerV2(
        starting_balance=50000.0,
        maximum_daily_loss=1000.0,
        maximum_total_drawdown=2000.0,
        profit_target=profit_target,
        account_stage=account_stage,
    )


def apply_realized_pnl(
    manager,
    realized_pnl,
):
    result = manager.update_from_portfolio(
        portfolio_summary={
            "open_positions": 0,
            "closed_positions": 1,
            "total_realized_pnl":
                realized_pnl,
            "total_unrealized_pnl":
                0.0,
            "total_pnl":
                realized_pnl,
            "account_equity":
                50000.0
                + realized_pnl,
        }
    )

    return result["state"]


def test_trading_combine_starts_in_progress():
    state = build_manager().get_state()

    assert (
        state["account_stage"]
        == "TRADING_COMBINE"
    )

    assert (
        state["evaluation_status"]
        == "IN_PROGRESS"
    )

    assert state["target_reached"] is False
    assert state["trading_blocked"] is False


def test_trading_combine_passes_at_profit_target():
    manager = build_manager()

    state = apply_realized_pnl(
        manager,
        3000.0,
    )

    assert state["target_reached"] is True

    assert (
        state["evaluation_status"]
        == "PASSED"
    )

    assert state["trading_blocked"] is False

    assert (
        state["blocking_reasons"]
        == []
    )


def test_trading_combine_above_target_remains_passed():
    state = apply_realized_pnl(
        build_manager(),
        4500.0,
    )

    assert state["target_reached"] is True

    assert (
        state["evaluation_status"]
        == "PASSED"
    )


def test_non_evaluation_stage_is_not_applicable():
    state = apply_realized_pnl(
        build_manager(
            account_stage="FUNDED",
        ),
        4500.0,
    )

    assert (
        state["account_stage"]
        == "FUNDED"
    )

    assert (
        state["evaluation_status"]
        == "NOT_APPLICABLE"
    )

    assert state["trading_blocked"] is False


def test_none_stage_is_not_applicable():
    state = build_manager(
        account_stage=None,
    ).get_state()

    assert state["account_stage"] is None

    assert (
        state["evaluation_status"]
        == "NOT_APPLICABLE"
    )


def test_runtime_uses_active_account_stage():
    context = build_runtime_context()

    state = (
        context.account_state_manager_v2
        .get_state()
    )

    assert (
        state["account_stage"]
        == "TRADING_COMBINE"
    )

    assert (
        state["evaluation_status"]
        == "IN_PROGRESS"
    )


def test_trading_combine_fails_at_maximum_total_drawdown():
    manager = AccountStateManagerV2(
        starting_balance=50000.0,
        maximum_daily_loss=None,
        maximum_total_drawdown=2000.0,
        profit_target=3000.0,
        account_stage="TRADING_COMBINE",
    )

    result = manager.update_from_portfolio(
        portfolio_summary={
            "open_positions": 0,
            "closed_positions": 1,
            "total_realized_pnl": -2000.0,
            "total_unrealized_pnl": 0.0,
            "total_pnl": -2000.0,
            "account_equity": 48000.0,
        }
    )

    state = result["state"]

    assert state["evaluation_status"] == "FAILED"
    assert state["trading_blocked"] is True
    assert (
        "maximum_total_drawdown_reached"
        in state["blocking_reasons"]
    )


def test_trading_combine_stays_in_progress_before_drawdown_breach():
    manager = AccountStateManagerV2(
        starting_balance=50000.0,
        maximum_daily_loss=None,
        maximum_total_drawdown=2000.0,
        profit_target=3000.0,
        account_stage="TRADING_COMBINE",
    )

    result = manager.update_from_portfolio(
        portfolio_summary={
            "open_positions": 0,
            "closed_positions": 1,
            "total_realized_pnl": -1999.0,
            "total_unrealized_pnl": 0.0,
            "total_pnl": -1999.0,
            "account_equity": 48001.0,
        }
    )

    state = result["state"]

    assert state["evaluation_status"] == "IN_PROGRESS"
    assert state["trading_blocked"] is False


def test_trading_combine_passed_status_is_not_replaced_by_failure():
    manager = AccountStateManagerV2(
        starting_balance=50000.0,
        maximum_daily_loss=None,
        maximum_total_drawdown=2000.0,
        profit_target=3000.0,
        account_stage="TRADING_COMBINE",
    )

    result = manager.update_from_portfolio(
        portfolio_summary={
            "open_positions": 0,
            "closed_positions": 1,
            "total_realized_pnl": 3000.0,
            "total_unrealized_pnl": 0.0,
            "total_pnl": 3000.0,
            "account_equity": 53000.0,
        }
    )

    state = result["state"]

    assert state["evaluation_status"] == "PASSED"
    assert state["trading_blocked"] is False


def test_funded_account_does_not_become_evaluation_failed():
    manager = AccountStateManagerV2(
        starting_balance=50000.0,
        maximum_daily_loss=None,
        maximum_total_drawdown=2000.0,
        profit_target=3000.0,
        account_stage="FUNDED",
    )

    result = manager.update_from_portfolio(
        portfolio_summary={
            "open_positions": 0,
            "closed_positions": 1,
            "total_realized_pnl": -2000.0,
            "total_unrealized_pnl": 0.0,
            "total_pnl": -2000.0,
            "account_equity": 48000.0,
        }
    )

    state = result["state"]

    assert state["evaluation_status"] != "FAILED"
