from datetime import datetime, timedelta, timezone
from copy import deepcopy
from unittest.mock import Mock

import pytest

from backend.account.account_state_manager_v2 import AccountStateManagerV2
from backend.dashboard.dashboard_live_data_service_v2 import DashboardLiveDataServiceV2
from backend.dashboard.performance_dashboard_engine_v2 import PerformanceDashboardEngineV2
from backend.portfolio.portfolio_manager_v2 import PortfolioManagerV2
from backend.services.live_position_monitor_v2 import LivePositionMonitorV2
from backend.tests.test_trade_lifecycle_service_v2 import (
    build_valid_signal, execution_state, observed_service,
)


START = 17000.0


def build_portfolio(*, maximum_daily_loss=500.0, maximum_total_drawdown=4500.0):
    account = AccountStateManagerV2(
        starting_balance=START,
        maximum_daily_loss=maximum_daily_loss,
        maximum_total_drawdown=maximum_total_drawdown,
    )
    portfolio = PortfolioManagerV2(
        starting_balance=START, account_state_manager_v2=account,
    )
    return account, portfolio


def add_position(portfolio, position_id, *, quantity=1.0):
    portfolio.add_position(position={
        "position_id": position_id, "symbol": "MNQ", "status": "OPEN",
        "direction": "LONG", "entry_price": 2000.0, "current_price": 2000.0,
        "quantity": quantity, "point_value": 1.0, "realized_pnl": 0.0,
    })


def close_trade(portfolio, position_id, pnl):
    add_position(portfolio, position_id)
    return portfolio.close_position(position_id=position_id, exit_price=2000.0 + pnl)


def assert_state(account, portfolio, *, realized, daily, unrealized=0.0):
    state = account.get_state()
    loss = max(0.0, -daily)
    assert state["realized_pnl"] == realized
    assert state["daily_pnl"] == daily
    assert state["daily_loss_used"] == loss
    assert state["remaining_daily_loss_capacity"] == max(0.0, 500.0 - loss)
    assert state["trading_blocked"] is (loss >= 500.0)
    assert state["blocking_reasons"] == (["daily_loss_limit_reached"] if loss >= 500 else [])
    assert state["balance"] == START + realized == portfolio.get_available_balance()
    assert state["unrealized_pnl"] == unrealized
    assert state["total_pnl"] == realized + unrealized
    assert state["equity"] == START + realized + unrealized == portfolio.get_account_equity()
    assert portfolio.get_summary()["account_state"] == state
    snapshot = DashboardLiveDataServiceV2(
        dashboard_engine_v2=PerformanceDashboardEngineV2(
            account_state_manager_v2=account, portfolio_manager_v2=portfolio,
        ),
    ).get_snapshot()
    assert snapshot["account_state"] == state
    assert snapshot["account_overview"]["daily_pnl"] == daily
    assert snapshot["account_overview"]["balance"] == state["balance"]
    assert snapshot["account_overview"]["equity"] == state["equity"]
    assert snapshot["risk_status"]["trading_blocked"] == state["trading_blocked"]


@pytest.mark.parametrize("pnls", [[500.0], [-400.0], [-500.0], [-1000.0], [300.0, -400.0, -500.0], []],
                         ids=["A_profit", "B_below_limit", "C_at_limit", "D_over_limit", "E_multiple", "F_no_trades"])
def test_realized_closes_immediately_update_daily_risk_and_projections(pnls):
    account, portfolio = build_portfolio()
    cumulative = 0.0
    for index, pnl in enumerate(pnls):
        result = close_trade(portfolio, str(index), pnl)
        cumulative += pnl
        assert result["account_state"] == account.get_state()
        assert_state(account, portfolio, realized=cumulative, daily=cumulative)
        before = account.get_state()
        for _ in range(3):
            account.update_from_portfolio(portfolio_summary=portfolio.get_summary())
        assert account.get_state() == before
        with pytest.raises(KeyError):
            portfolio.close_position(position_id=str(index), exit_price=2000.0 + pnl)
        assert account.get_state() == before
    assert_state(account, portfolio, realized=cumulative, daily=cumulative)
    assert len(portfolio.get_closed_positions()) == len(pnls)
    # Repeated reads and price synchronization must not book the same close again.
    add_position(portfolio, "still-open")
    for _ in range(3):
        portfolio.update_position(position_id="still-open", updates={"current_price": 2010.0})
        assert_state(account, portfolio, realized=cumulative, daily=cumulative, unrealized=10.0)


@pytest.mark.parametrize("partial_pnl", [-600.0, 300.0])
def test_partial_realization_and_final_close_are_counted_once(partial_pnl):
    account, portfolio = build_portfolio()
    add_position(portfolio, "partial", quantity=2.0)
    portfolio.reduce_position(position_id="partial", remaining_quantity=1.0,
                              current_price=2000.0 + partial_pnl, realized_pnl=partial_pnl)
    assert_state(account, portfolio, realized=partial_pnl, daily=partial_pnl, unrealized=partial_pnl)
    for _ in range(3):
        portfolio.update_position(position_id="partial", updates={"current_price": 2000.0 + partial_pnl})
        assert_state(account, portfolio, realized=partial_pnl, daily=partial_pnl, unrealized=partial_pnl)
    portfolio.close_position(position_id="partial", exit_price=2000.0 + partial_pnl)
    assert_state(account, portfolio, realized=2 * partial_pnl, daily=2 * partial_pnl)


def test_reset_keeps_lifetime_pnl_and_counts_only_new_realizations():
    account, portfolio = build_portfolio()
    close_trade(portfolio, "yesterday", -1000.0)
    add_position(portfolio, "overnight", quantity=2.0)
    portfolio.reduce_position(position_id="overnight", remaining_quantity=1.0,
                              current_price=1900.0, realized_pnl=-100.0)
    before = account.get_state()
    account._clock = lambda: datetime.now(timezone.utc) + timedelta(days=7)
    account.reset_daily_state()
    assert_state(account, portfolio, realized=-1100.0, daily=0.0, unrealized=-100.0)
    for field in ("realized_pnl", "balance", "equity", "drawdown", "peak_equity"):
        assert account.get_state()[field] == before[field]
    for _ in range(3):
        account.update_from_portfolio(portfolio_summary=portfolio.get_summary())
        assert_state(account, portfolio, realized=-1100.0, daily=0.0, unrealized=-100.0)
    portfolio.close_position(position_id="overnight", exit_price=1800.0)
    assert_state(account, portfolio, realized=-1300.0, daily=-200.0)
    close_trade(portfolio, "today", -300.0)
    assert_state(account, portfolio, realized=-1600.0, daily=-500.0)


def test_reset_does_not_clear_drawdown_block():
    account, portfolio = build_portfolio(maximum_total_drawdown=1000.0)
    close_trade(portfolio, "loss", -1000.0)
    assert set(account.get_state()["blocking_reasons"]) == {
        "daily_loss_limit_reached", "maximum_total_drawdown_reached",
    }
    account._clock = lambda: datetime.now(timezone.utc) + timedelta(days=7)
    account.reset_daily_state()
    account.update_from_portfolio(portfolio_summary=portfolio.get_summary())
    assert account.get_state()["daily_pnl"] == 0.0
    assert account.get_state()["trading_blocked"] is True
    assert account.get_state()["blocking_reasons"] == ["maximum_total_drawdown_reached"]


def test_unconfigured_daily_limit_still_tracks_realized_loss():
    account, portfolio = build_portfolio(maximum_daily_loss=None)
    close_trade(portfolio, "loss", -1000.0)
    state = account.get_state()
    assert state["daily_pnl"] == -1000.0
    assert state["daily_loss_used"] == 1000.0
    assert state["remaining_daily_loss_capacity"] is None
    assert state["trading_blocked"] is False


@pytest.mark.parametrize("pnls", [[-500.0], [-1000.0], [300.0, -400.0, -500.0]],
                         ids=["at_limit", "over_limit", "multiple_trades"])
@pytest.mark.parametrize("order_type", ["MARKET", "LIMIT"])
@pytest.mark.parametrize("risk_context", [None, {
    "account_balance": START, "risk_percent": 0.5, "point_value": 2.0,
    "daily_pnl": 0.0, "total_drawdown": 0.0, "current_price": 100.0,
}], ids=["missing_context", "stale_context"])
def test_daily_block_prevents_all_execution_side_effects(observed_service, order_type, risk_context, pnls):
    service, calls = observed_service
    portfolio = service.portfolio_manager_v2
    account = portfolio.account_state_manager_v2
    account.maximum_daily_loss = 500.0
    for index, pnl in enumerate(pnls):
        close_trade(portfolio, str(index), pnl)
    assert account.get_state()["trading_blocked"] is True
    for spy in calls.values():
        spy.reset_mock()
    signal = build_valid_signal()
    signal["symbol"] = "MNQ"
    original = deepcopy(signal)
    before = execution_state(service)
    result = service.submit_signal(signal=signal, order_type=order_type,
                                   risk_context=deepcopy(risk_context),
                                   order_context={"market_is_open": True})
    assert result["accepted"] is False
    assert result["reason"] == "account_trading_blocked"
    assert result["portfolio_summary"]["account_state"]["trading_blocked"] is True
    for field in ("prepared_order", "execution", "position", "active_position_id"):
        assert result[field] is None
    assert {name: spy.call_count for name, spy in calls.items()} == dict.fromkeys(calls, 0)
    assert execution_state(service) == before
    assert signal == original


def test_paper_monitor_close_updates_risk_before_next_signal(observed_service, monkeypatch):
    service, calls = observed_service
    portfolio = service.portfolio_manager_v2
    account = portfolio.account_state_manager_v2
    account.maximum_daily_loss = 500.0
    signal = build_valid_signal()
    signal.update(symbol="MNQ", entry_price=1000.0, stop_loss=990.0, take_profit=1020.0)
    opened = service.submit_signal(signal=signal, order_type="MARKET", risk_context={
        "account_balance": START, "risk_percent": 0.5, "point_value": 2.0,
        "daily_pnl": 0.0, "total_drawdown": 0.0, "current_price": 1000.0,
    }, order_context={"market_is_open": True})
    assert opened["accepted"] is True
    position = opened["position"]
    exit_price = position["entry_price"] - 1000.0 / (position["quantity"] * position["point_value"])
    monitor = LivePositionMonitorV2(trade_lifecycle_service=service, portfolio_manager_v2=portfolio)
    close_spy = Mock(wraps=portfolio.close_position)
    monkeypatch.setattr(portfolio, "close_position", close_spy)
    result = monitor.process_price(symbol="MNQ", current_price=exit_price)
    assert result["closed_positions"] == 1
    assert close_spy.call_count == 1
    assert_state(account, portfolio, realized=-1000.0, daily=-1000.0)
    assert service.get_active_positions() == []
    assert service.trade_journal_v2.get_summary()["closed_trades"] == 1
    monitor.process_price(symbol="MNQ", current_price=exit_price)
    assert close_spy.call_count == 1
    assert_state(account, portfolio, realized=-1000.0, daily=-1000.0)
    for spy in calls.values():
        spy.reset_mock()
    before = execution_state(service)
    rejected = service.submit_signal(signal=signal, order_type="MARKET")
    assert rejected["accepted"] is False
    assert rejected["reason"] == "account_trading_blocked"
    assert execution_state(service) == before
    assert {name: spy.call_count for name, spy in calls.items()} == dict.fromkeys(calls, 0)
