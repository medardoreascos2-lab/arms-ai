from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime
from unittest.mock import Mock

import pytest

from backend.account.account_state_manager_v2 import AccountStateManagerV2
from backend.portfolio.portfolio_manager_v2 import PortfolioManagerV2
from backend.services.market_hours_service_v2 import MarketHoursServiceV2
from backend.services.state_recovery_service_v2 import StateRecoveryServiceV2
from backend.services.startup_coordinator_v2 import StartupCoordinatorV2
from backend.tests.test_daily_pnl_safety_v2 import add_position, close_trade
from backend.tests.test_execution_state_store_v2 import build_store, populate_store
from backend.tests.test_trade_lifecycle_service_v2 import (
    build_valid_signal, execution_state, observed_service,
)


class Clock:
    def __init__(self, value="2026-09-10T21:59:59+00:00"):
        self.set(value)

    def set(self, value):
        self.value = datetime.fromisoformat(value)

    def __call__(self):
        return self.value


def build_account(clock, *, drawdown=4500.0):
    return AccountStateManagerV2(
        starting_balance=17000.0, maximum_daily_loss=500.0,
        maximum_total_drawdown=drawdown, clock=clock,
    )


def build_portfolio(clock, *, drawdown=4500.0):
    account = build_account(clock, drawdown=drawdown)
    return account, PortfolioManagerV2(starting_balance=17000.0, account_state_manager_v2=account)


def attach_clock(service, clock):
    account = service.portfolio_manager_v2.account_state_manager_v2
    snapshot = account.capture_state()
    snapshot["state"]["trading_day"] = MarketHoursServiceV2.trading_day_for(clock()).isoformat()
    account.restore_state(snapshot=snapshot)
    account._clock = clock
    account.maximum_daily_loss = 500.0
    account.record_daily_pnl(daily_pnl=0.0)
    return account


def advance(clock):
    clock.set("2026-09-10T22:00:00+00:00")


@pytest.mark.parametrize("timestamp,day", [
    ("2026-09-10T21:59:59+00:00", "2026-09-10"),
    ("2026-09-10T22:00:00+00:00", "2026-09-11"),
    ("2026-09-11T05:00:00+00:00", "2026-09-11"),
    ("2026-09-11T22:00:00+00:00", "2026-09-11"),
    ("2026-09-12T22:00:00+00:00", "2026-09-11"),
    ("2026-09-13T21:59:59+00:00", "2026-09-11"),
    ("2026-09-13T22:00:00+00:00", "2026-09-14"),
    ("2026-01-08T22:59:59+00:00", "2026-01-08"),
    ("2026-01-08T23:00:00+00:00", "2026-01-09"),
    ("2026-03-08T21:59:59+00:00", "2026-03-06"),
    ("2026-03-08T22:00:00+00:00", "2026-03-09"),
    ("2026-11-01T22:59:59+00:00", "2026-10-30"),
    ("2026-11-01T23:00:00+00:00", "2026-11-02"),
])
def test_existing_chicago_session_boundary_and_dst(timestamp, day):
    assert MarketHoursServiceV2.trading_day_for(datetime.fromisoformat(timestamp)).isoformat() == day


def test_naive_clock_is_rejected():
    with pytest.raises(ValueError, match="timezone"):
        build_account(lambda: datetime(2026, 9, 10))


def test_a_same_day_never_resets():
    clock = Clock()
    account = build_account(clock)
    account.record_daily_pnl(daily_pnl=-600.0)
    before = account.get_state()
    for _ in range(3):
        assert account.ensure_trading_day()["reset"] is False
        assert account.reset_daily_state()["reset"] is False
    assert account.get_state() == before


def test_b_c_new_day_resets_once_even_with_concurrent_calls():
    clock = Clock()
    account = build_account(clock)
    account.record_daily_pnl(daily_pnl=-600.0)
    advance(clock)
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _: account.ensure_trading_day(), range(32)))
    assert sum(result["reset"] for result in results) == 1
    assert account.get_state()["daily_pnl"] == 0.0
    account.record_daily_pnl(daily_pnl=-100.0)
    for _ in range(5):
        assert account.ensure_trading_day()["reset"] is False
    assert account.get_state()["daily_pnl"] == -100.0
    assert account.get_state()["daily_loss_used"] == 100.0


@pytest.mark.parametrize("drawdown,blocked", [(4500.0, False), (500.0, True)])
def test_d_e_f_g_reset_preserves_finances_portfolio_and_structural_block(drawdown, blocked):
    clock = Clock()
    account, portfolio = build_portfolio(clock, drawdown=drawdown)
    close_trade(portfolio, "yesterday", -600.0)
    add_position(portfolio, "overnight", quantity=2.0)
    portfolio.reduce_position(position_id="overnight", remaining_quantity=1.0,
                              current_price=1900.0, realized_pnl=-100.0)
    before = account.get_state()
    positions = (portfolio.get_open_positions(), portfolio.get_closed_positions())
    advance(clock)
    assert account.ensure_trading_day()["reset"] is True
    state = account.get_state()
    assert state["daily_pnl"] == state["daily_loss_used"] == 0.0
    assert state["trading_blocked"] is blocked
    assert state["blocking_reasons"] == (["maximum_total_drawdown_reached"] if blocked else [])
    for key in before.keys() - {"trading_day", "daily_pnl", "daily_loss_used", "remaining_daily_loss_capacity", "blocking_reasons", "trading_blocked"}:
        assert state[key] == before[key]
    assert (portfolio.get_open_positions(), portfolio.get_closed_positions()) == positions
    account.update_from_portfolio(portfolio_summary=portfolio.get_summary())
    assert account.get_state() == state
    portfolio.close_position(position_id="overnight", exit_price=1800.0)
    assert account.get_state()["daily_pnl"] == -200.0
    assert account.get_state()["realized_pnl"] == -900.0
    assert portfolio.get_available_balance() == account.get_state()["balance"]
    assert portfolio.get_account_equity() == account.get_state()["equity"]


def test_first_portfolio_realization_of_new_day_resets_before_adding_delta():
    clock = Clock()
    account, portfolio = build_portfolio(clock)
    close_trade(portfolio, "yesterday", -600.0)
    add_position(portfolio, "overnight")
    advance(clock)
    portfolio.close_position(position_id="overnight", exit_price=1950.0)
    assert account.get_state()["daily_pnl"] == -50.0
    assert account.get_state()["realized_pnl"] == -650.0
    assert account.get_state()["trading_blocked"] is False


@pytest.mark.parametrize("reasons", [["invalid_state"], ["daily_loss_limit_reached", "structural_risk"], []])
def test_unknown_structural_blocks_survive_reset_and_next_sync(reasons):
    clock = Clock()
    account, portfolio = build_portfolio(clock)
    account._state.update(trading_blocked=True, blocking_reasons=reasons)
    advance(clock)
    account.ensure_trading_day()
    account.update_from_portfolio(portfolio_summary=portfolio.get_summary())
    assert account.get_state()["trading_blocked"] is True
    assert "daily_loss_limit_reached" not in account.get_state()["blocking_reasons"]


def test_clock_rollback_never_reopens_risk_capacity():
    clock = Clock()
    account = build_account(clock)
    account.record_daily_pnl(daily_pnl=-600.0)
    before = account.get_state()
    clock.set("2026-09-09T21:00:00+00:00")
    with pytest.raises(ValueError, match="backwards"):
        account.ensure_trading_day()
    assert account.get_state() == before


def dated_store(clock):
    store = build_store()
    account, portfolio = build_portfolio(clock)
    lifecycle = store.trade_lifecycle_service
    lifecycle.portfolio_manager_v2 = portfolio
    lifecycle.broker_connector_v2._utc_now = lambda: clock().isoformat()
    account._durability = portfolio._durability = store._durability
    return store, account, portfolio


def open_recovery_trade(store):
    """Persist actual PAPER fills/terminal evidence for the dated recovery tests."""
    from backend.tests.test_durable_crash_recovery_v2 import signal
    lifecycle = store.trade_lifecycle_service
    order = signal()
    order.update(entry_price=1000., stop_loss=990., take_profit=1040.)
    result = lifecycle.submit_signal(signal=order, order_type="MARKET", risk_context={
        "account_balance": 17000., "risk_percent": .25, "point_value": 2.,
        "daily_pnl": 0., "total_drawdown": 0.})
    assert result["accepted"], result
    return result["position"]


def close_recovery_trade(store, pnl):
    position = open_recovery_trade(store)
    store.trade_lifecycle_service.update_position(
        position_id=position["position_id"], current_price=1000. + pnl / 4.)


@pytest.mark.parametrize("after_rollover", [False, True])
def test_h_disk_restart_same_day_keeps_daily_state_and_baseline(tmp_path, after_rollover):
    clock = Clock()
    source, account, portfolio = dated_store(clock)
    # A real partial loss leaves one managed position while the daily block is
    # active. No new position is fabricated after admission has been blocked.
    position = open_recovery_trade(source)
    position.update(quantity=1., current_price=700., partial_exit_price=700.,
                    partial_taken=True, partial_pnl_recorded=True,
                    partial_closed_quantity=1., realized_pnl=-600.)
    source.trade_lifecycle_service.replace_active_position(position=position)
    if after_rollover:
        advance(clock)
        account.ensure_trading_day()
        source.trade_lifecycle_service.update_position(
            position_id=position["position_id"], current_price=950.)
        populate_store(source)
    before = portfolio.capture_risk_state()
    path = tmp_path / "state.json"
    source.save_to_file(file_path=path)
    target, restored, restored_portfolio = dated_store(clock)
    startup = StartupCoordinatorV2(state_recovery_service=StateRecoveryServiceV2(execution_state_store=target))
    assert startup.startup_from(file_path=path)["success"] is True
    assert restored_portfolio.capture_risk_state() == before
    assert restored.ensure_trading_day()["reset"] is False
    restored.update_from_portfolio(portfolio_summary=restored_portfolio.get_summary())
    assert restored_portfolio.capture_risk_state() == before
    assert target.trade_lifecycle_service.get_active_positions() == source.trade_lifecycle_service.get_active_positions()
    restored_protection = target.capture_state()["protective_registry"]["protections"][0]
    original_protection = source.capture_state()["protective_registry"]["protections"][0]
    for key in original_protection.keys() - {"created_at", "updated_at"}:
        assert restored_protection[key] == original_protection[key]
    # A second restart after a reset must keep today's new loss.
    target.save_to_file(file_path=path)
    second, second_account, _ = dated_store(clock)
    second.restore_from_file(file_path=path)
    assert second_account.ensure_trading_day()["reset"] is False
    assert second_account.get_state() == restored.get_state()


def test_restart_from_previous_day_resets_once_on_first_use(tmp_path):
    clock = Clock()
    source, account, portfolio = dated_store(clock)
    close_recovery_trade(source, -600.0)
    path = tmp_path / "state.json"
    source.save_to_file(file_path=path)
    advance(clock)
    target, restored, restored_portfolio = dated_store(clock)
    target.restore_from_file(file_path=path)
    assert restored.get_state()["daily_pnl"] == -600.0
    assert restored.ensure_trading_day()["reset"] is True
    assert restored.ensure_trading_day()["reset"] is False
    restored.update_from_portfolio(portfolio_summary=restored_portfolio.get_summary())
    assert restored.get_state()["daily_pnl"] == 0.0
    assert restored.get_state()["realized_pnl"] == -600.0


@pytest.mark.parametrize("damage", ["missing_snapshot", "missing_day", "invalid_day", "inconsistent_loss", "missing_history", "missing_block"])
def test_incomplete_or_inconsistent_recovery_fails_before_mutation(damage):
    clock = Clock()
    source, _, portfolio = dated_store(clock)
    close_recovery_trade(source, -600.0)
    snapshot = source.capture_state()
    state = snapshot["account_portfolio"]["account"]["state"]
    if damage == "missing_snapshot":
        snapshot.pop("account_portfolio")
    elif damage == "missing_day":
        state.pop("trading_day")
    elif damage == "invalid_day":
        state["trading_day"] = "not-a-date"
    elif damage == "inconsistent_loss":
        state["daily_loss_used"] = 0.0
    elif damage == "missing_history":
        snapshot["account_portfolio"]["closed_positions"] = []
    else:
        state.update(trading_blocked=False, blocking_reasons=[])
    target, restored, target_portfolio = dated_store(clock)
    before = restored.get_state()
    with pytest.raises(ValueError):
        target.restore_state(state=snapshot)
    before.update(trading_blocked=True, blocking_reasons=["durability_consistency_unproven"])
    assert restored.get_state() == before
    assert target._durability.failed
    assert target_portfolio.get_open_positions() == []
    assert target_portfolio.get_closed_positions() == []
    assert target.trade_lifecycle_service.get_active_positions() == []


@pytest.mark.parametrize("structural,order_type", [(False, "MARKET"), (True, "MARKET"), (True, "LIMIT")])
def test_i_new_signal_resets_before_admission_and_preserves_structural_rejection(observed_service, structural, order_type):
    service, calls = observed_service
    clock = Clock()
    account = attach_clock(service, clock)
    if structural:
        account.maximum_total_drawdown = 500.0
    close_trade(service.portfolio_manager_v2, "yesterday", -600.0)
    before = execution_state(service)
    advance(clock)
    for spy in calls.values():
        spy.reset_mock()
    signal = build_valid_signal()
    signal["symbol"] = "MNQ"
    signal["timestamp"] = "1999-01-01T00:00:00Z"  # Signal timestamps never choose the risk day.
    risk = {"account_balance": 16400.0, "risk_percent": 0.5, "point_value": 2.0,
            "daily_pnl": -600.0, "total_drawdown": 600.0, "current_price": 100.0}
    original_risk = deepcopy(risk)
    evaluate = service.risk_manager_v2.evaluate
    def checked_evaluate(**kwargs):
        assert account.get_state()["daily_pnl"] == 0.0
        assert account.get_state()["trading_day"] == "2026-09-11"
        assert kwargs["daily_pnl"] == 0.0
        return evaluate(**kwargs)
    service.risk_manager_v2.evaluate = Mock(side_effect=checked_evaluate)
    result = service.submit_signal(signal=signal, order_type=order_type, risk_context=risk,
                                   order_context={"market_is_open": True})
    assert risk == original_risk
    assert account.get_state()["daily_pnl"] == 0.0
    assert account.ensure_trading_day()["reset"] is False
    assert result["accepted"] is (not structural)
    if structural:
        assert result["reason"] == "account_trading_blocked"
        assert all(spy.call_count == 0 for spy in calls.values())
        after = execution_state(service)
        for key in before.keys() - {"portfolio"}:
            assert after[key] == before[key]
        assert account.get_state()["blocking_reasons"] == ["maximum_total_drawdown_reached"]
    else:
        assert service.risk_manager_v2.evaluate.call_count == 1
        assert calls["ExecutionManagerV2.prepare_order"].call_count == 1
        assert calls["PaperBrokerConnectorV2.submit_order"].call_count == 1
    assert service.portfolio_manager_v2.get_closed_positions() == before["portfolio_closed_positions"]


def test_new_day_reset_keeps_active_execution_and_journal_history(observed_service):
    service, _ = observed_service
    clock = Clock()
    account = attach_clock(service, clock)
    signal = build_valid_signal()
    signal["symbol"] = "MNQ"
    result = service.submit_signal(signal=signal, order_type="MARKET", risk_context={
        "account_balance": 17000.0, "risk_percent": 0.5, "point_value": 2.0,
        "daily_pnl": 0.0, "total_drawdown": 0.0, "current_price": 100.0,
    }, order_context={"market_is_open": True})
    assert result["accepted"] is True
    before = execution_state(service)
    assert before["journal"]
    advance(clock)
    account.ensure_trading_day()
    after = execution_state(service)
    for key in before.keys() - {"portfolio"}:
        assert after[key] == before[key]
