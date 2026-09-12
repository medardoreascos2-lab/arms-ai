"""Real process exits: no graceful shutdown and no final/manual snapshot."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from backend.account.account_state_manager_v2 import AccountStateManagerV2
from backend.journal.trade_journal_v2 import TradeJournalV2
from backend.portfolio.portfolio_manager_v2 import PortfolioManagerV2
from backend.services.execution_state_store_v2 import ExecutionStateStoreV2
from backend.services.state_recovery_service_v2 import StateRecoveryServiceV2
from backend.services.startup_coordinator_v2 import StartupCoordinatorV2
from backend.tests.test_execution_state_store_v2 import build_lifecycle_service
from backend.tests.test_trade_lifecycle_close_sync_v2 import build_signal, build_risk_manager


def build_runtime():
    lifecycle = build_lifecycle_service()
    lifecycle.risk_manager_v2 = build_risk_manager()
    account = AccountStateManagerV2(starting_balance=17000.0,
        maximum_daily_loss=40.0, maximum_total_drawdown=1000.0)
    lifecycle.portfolio_manager_v2 = PortfolioManagerV2(
        starting_balance=17000.0, account_state_manager_v2=account)
    lifecycle.trade_journal_v2 = TradeJournalV2()
    store = ExecutionStateStoreV2(trade_lifecycle_service=lifecycle,
        protective_order_registry=lifecycle.protective_order_registry_v2,
        oco_manager=lifecycle.oco_manager_v2)
    recovery = StateRecoveryServiceV2(execution_state_store=store)
    startup = StartupCoordinatorV2(state_recovery_service=recovery)
    return lifecycle, account, store, recovery, startup


def signal():
    value = build_signal()
    value.update(symbol="MNQ", entry_price=100.0, stop_loss=90.0, take_profit=120.0)
    return value


def open_position(lifecycle):
    result = lifecycle.submit_signal(signal=signal(), order_type="MARKET",
        risk_context={"account_balance": 17000.0, "risk_percent": 0.25,
                      "point_value": 2.0, "daily_pnl": 0.0, "total_drawdown": 0.0})
    assert result["accepted"] is True, result
    return result["position"]


def partial(lifecycle):
    position = lifecycle.get_active_positions()[0]
    position.update(quantity=1.0, current_price=110.0, partial_exit_price=110.0,
                    partial_taken=True, partial_pnl_recorded=True,
                    partial_closed_quantity=1.0, realized_pnl=20.0)
    lifecycle.replace_active_position(position=position)


def crash_worker(path, action):
    lifecycle, account, store, _, startup = build_runtime()
    startup.startup_from(file_path=path)
    if action.startswith("window_"):
        from backend.services import durable_execution_state_v2 as durable
        original_write = durable.atomic_write
        def crash_at_write(path, state):
            phase = state["durability"]["phase"]
            if action == "window_before_pending" and phase == "PENDING":
                os._exit(23)
            if action == "window_before_committed" and phase == "COMMITTED":
                os._exit(23)
            original_write(path, state)
            if action == "window_after_pending" and phase == "PENDING":
                os._exit(23)
            if action == "window_after_committed" and phase == "COMMITTED":
                os._exit(23)
        durable.atomic_write = crash_at_write
    if action == "pending_open":
        lifecycle.trade_journal_v2.record_open_trade = lambda **kwargs: os._exit(23)
    position = open_position(lifecycle)
    if action == "pending_loss":
        lifecycle.trade_journal_v2.close_trade = lambda **kwargs: os._exit(23)
        lifecycle.update_position(position_id=position["position_id"], current_price=90.0)
    if action == "monitor_partial":
        from backend.services.live_position_monitor_v2 import LivePositionMonitorV2
        from backend.execution.partial_take_profit_engine_v2 import PartialTakeProfitEngineV2
        from backend.execution.realized_pnl_engine_v2 import RealizedPnLEngineV2
        monitor = LivePositionMonitorV2(trade_lifecycle_service=lifecycle,
            portfolio_manager_v2=lifecycle.portfolio_manager_v2,
            partial_take_profit_engine=PartialTakeProfitEngineV2(trigger_profit_points=10.0, close_fraction=0.5),
            realized_pnl_engine=RealizedPnLEngineV2(point_value=2.0))
        monitor.process_price(symbol="MNQ", current_price=110.0)
    if action.startswith("old_"):
        store.save_to_file(file_path=path)
    if action in {"partial", "partial_full", "partial_zero", "old_partial"}:
        partial(lifecycle)
    if action in {"full", "partial_full"}:
        lifecycle.update_position(position_id=position["position_id"], current_price=120.0)
    if action in {"loss", "old_loss", "partial_zero"}:
        lifecycle.update_position(position_id=position["position_id"], current_price=90.0)
    if action == "pending":
        with store._durability.mutation():
            partial(lifecycle)
            os._exit(23)
    os._exit(23)


def run_crash(path, action):
    result = subprocess.run([sys.executable, "-m", "backend.tests.test_durable_crash_recovery_v2", str(path), action],
        cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True, timeout=30)
    assert result.returncode == 23, result.stdout + result.stderr


def comparable(state):
    state = deepcopy(state)
    state.pop("captured_at", None)
    return state


@pytest.mark.parametrize("action,quantity,pnl,blocked", [
    ("open", 2.0, 0.0, False), ("partial", 1.0, 20.0, False),
    ("monitor_partial", 1.0, 20.0, False),
    ("full", 0.0, 80.0, False), ("loss", 0.0, -40.0, True),
    ("partial_full", 0.0, 60.0, False), ("partial_zero", 0.0, 0.0, False),
    ("old_partial", 1.0, 20.0, False), ("old_loss", 0.0, -40.0, True),
])
def test_abrupt_crash_preserves_complete_state(tmp_path, action, quantity, pnl, blocked):
    path = tmp_path / "state.json"
    run_crash(path, action)
    for _ in range(2):
        lifecycle, account, store, recovery, _ = build_runtime()
        expected = store.load_from_file(file_path=path)
        recovery.recover_from(file_path=path)
        baseline = comparable(store.capture_state())
        recovery.recover_from(file_path=path)
        assert comparable(store.capture_state()) == baseline == comparable(expected)
        state = account.get_state()
        assert state["realized_pnl"] == state["daily_pnl"] == pnl
        assert state["trading_blocked"] is blocked
        assert state["daily_loss_used"] == max(0, -pnl)
        portfolio = lifecycle.portfolio_manager_v2
        assert portfolio.get_total_realized_pnl() == pnl
        positions = lifecycle.get_active_positions()
        assert len(positions) == int(quantity > 0)
        assert len(portfolio.get_closed_positions()) == int(quantity == 0)
        assert len(lifecycle.trade_journal_v2.trades) == 1
        trade = lifecycle.trade_journal_v2.trades[0]
        assert trade.pnl == pnl
        assert trade.status == ("OPEN" if quantity else "CLOSED")
        assert len(lifecycle.trade_history_manager.get_history()) == int(quantity == 0)
        assert len(lifecycle.broker_connector_v2.get_fills()) == (2 if "partial" in action else 1)
        if quantity:
            assert positions[0]["quantity"] == quantity
            assert portfolio.get_open_positions()[0]["quantity"] == quantity
            protection = store.protective_order_registry.list_protections(status="ACTIVE")[0]
            assert protection["quantity"] == quantity
            assert protection["stop_price"] == positions[0]["stop_loss"]
            assert len(store.oco_manager.list_groups(status="ACTIVE")) == 1
        else:
            assert not store.protective_order_registry.list_protections(status="ACTIVE")
            assert not store.oco_manager.list_groups(status="ACTIVE")
            assert all(p["status"] == "CLOSED" for p in lifecycle.broker_connector_v2.get_positions())


@pytest.mark.parametrize("damage", ["empty", "truncated", "checksum", "pending", "temporary", "pending_open", "pending_loss"])
def test_corrupt_or_inflight_state_fails_closed(tmp_path, damage):
    path = tmp_path / "state.json"
    run_crash(path, damage if damage.startswith("pending") else "open")
    if damage == "empty":
        path.write_text("")
    elif damage == "truncated":
        path.write_text(path.read_text()[:100])
    elif damage == "checksum":
        data = json.loads(path.read_text())
        data["account_portfolio"]["account"]["state"]["daily_pnl"] = 999
        path.write_text(json.dumps(data))
    elif damage == "temporary":
        path.with_suffix(".json.tmp").write_text("{")
    lifecycle, account, store, _, startup = build_runtime()
    before = path.read_bytes()
    with pytest.raises((ValueError, FileNotFoundError)):
        startup.startup_from(file_path=path)
    assert startup.get_status() == "FAILED"
    assert account.get_state()["trading_blocked"] is True
    assert lifecycle.get_active_positions() == []
    assert lifecycle.trade_journal_v2.trades == []
    assert path.read_bytes() == before
    with pytest.raises(RuntimeError, match="failed closed"):
        open_position(lifecycle)
    assert lifecycle.broker_connector_v2.get_fills() == []
    with pytest.raises(RuntimeError):
        store.save_to_file(file_path=path)


def test_recovery_can_continue_partial_without_duplicate_pnl(tmp_path):
    path = tmp_path / "state.json"
    run_crash(path, "partial")
    lifecycle, account, store, _, startup = build_runtime()
    try:
        startup.startup_from(file_path=path)
        partial(lifecycle)  # Exact repeated state must not close another contract.
        position = lifecycle.get_active_positions()[0]
        lifecycle.update_position(position_id=position["position_id"], current_price=120.0)
        assert account.get_state()["realized_pnl"] == 60.0
        assert account.get_state()["daily_pnl"] == 60.0
        assert len(lifecycle.broker_connector_v2.get_fills()) == 2
        assert len(lifecycle.trade_journal_v2.get_closed_trades()) == 1
    finally:
        store._durability.release()


def test_write_failure_blocks_execution_and_preserves_pending_fence(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    lifecycle, account, store, _, startup = build_runtime()
    startup.startup_from(file_path=path)
    from backend.services import durable_execution_state_v2 as durable
    real_write = durable.atomic_write
    def fail_commit(path, state):
        if state["durability"]["phase"] == "COMMITTED":
            raise OSError("injected disk failure")
        real_write(path, state)
    monkeypatch.setattr(durable, "atomic_write", fail_commit)
    try:
        with pytest.raises(OSError):
            open_position(lifecycle)
        assert account.get_state()["trading_blocked"] is True
        assert json.loads(path.read_text())["durability"]["phase"] == "PENDING"
        with pytest.raises(RuntimeError):
            lifecycle.update_position(position_id=lifecycle.get_active_positions()[0]["position_id"], current_price=90.0)
    finally:
        store._durability.release()


def test_second_runtime_writer_is_denied(tmp_path):
    path = tmp_path / "state.json"
    _, _, first, _, startup = build_runtime()
    startup.startup_from(file_path=path)
    try:
        lifecycle, account, second, _, other = build_runtime()
        with pytest.raises(RuntimeError, match="runtime writer"):
            other.startup_from(file_path=path)
        assert account.get_state()["trading_blocked"] is True
        assert lifecycle.broker_connector_v2.get_fills() == []
        assert second._durability.failed is True
    finally:
        first._durability.release()


def test_concurrent_submissions_are_ordered_and_only_fill_once(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    path = tmp_path / "state.json"
    lifecycle, _, store, _, startup = build_runtime()
    startup.startup_from(file_path=path)
    try:
        def submit(_):
            return lifecycle.submit_signal(signal=signal(), order_type="MARKET",
                risk_context={"account_balance": 17000.0, "risk_percent": 0.25,
                    "point_value": 2.0, "daily_pnl": 0.0, "total_drawdown": 0.0})
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(submit, range(4)))
        assert sum(result["accepted"] for result in results) == 1
        assert len(lifecycle.broker_connector_v2.get_fills()) == 1
        assert len(lifecycle.trade_journal_v2.trades) == 1
        assert comparable(store.load_from_file(file_path=path)) == comparable(store.capture_state())
        assert json.loads(path.read_text())["durability"]["generation"] == 5
    finally:
        store._durability.release()


def test_pending_write_failure_has_zero_execution_side_effects(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    lifecycle, _, store, _, startup = build_runtime()
    startup.startup_from(file_path=path)
    before = path.read_bytes()
    def fail_fsync(_):
        raise OSError("injected fsync failure")
    monkeypatch.setattr(os, "fsync", fail_fsync)
    try:
        with pytest.raises(OSError):
            open_position(lifecycle)
        assert lifecycle.broker_connector_v2.get_fills() == []
        assert lifecycle.get_active_positions() == []
        assert lifecycle.trade_journal_v2.trades == []
        assert path.read_bytes() == before
        assert path.with_suffix(".json.tmp").exists()
    finally:
        store._durability.release()


def test_legacy_snapshot_with_missing_journal_is_not_invented(tmp_path):
    path = tmp_path / "state.json"
    run_crash(path, "open")
    legacy = json.loads(path.read_text())
    for key in ("execution_records", "durability", "checksum"):
        legacy.pop(key)
    path.write_text(json.dumps(legacy))
    lifecycle, account, _, _, startup = build_runtime()
    with pytest.raises(ValueError, match="Legacy snapshot lacks"):
        startup.startup_from(file_path=path)
    assert account.get_state()["trading_blocked"] is True
    assert lifecycle.trade_journal_v2.trades == []
    assert lifecycle.get_active_positions() == []


def test_daily_block_and_protection_changes_checkpoint_immediately(tmp_path):
    path = tmp_path / "state.json"
    lifecycle, account, store, _, startup = build_runtime()
    startup.startup_from(file_path=path)
    try:
        position = open_position(lifecycle)
        position.update(stop_loss=95.0, take_profit=125.0)
        lifecycle.replace_active_position(position=position)
        account.record_daily_pnl(daily_pnl=-40.0)
        saved = store.load_from_file(file_path=path)
        assert saved["account_portfolio"]["account"]["state"]["trading_blocked"] is True
        assert saved["protective_registry"]["protections"][0]["stop_price"] == 95.0
        assert saved["active_positions"][0]["take_profit"] == 125.0
        fresh, risk, target, recovery, _ = build_runtime()
        recovery.recover_from(file_path=path)
        assert risk.get_state()["daily_pnl"] == -40.0
        assert risk.get_state()["trading_blocked"] is True
        assert fresh.broker_connector_v2.get_orders()[0]["stop_loss"] == 95.0
        assert comparable(target.capture_state()) == comparable(saved)
    finally:
        store._durability.release()


@pytest.mark.parametrize("damage", ["missing_fill", "duplicate_fill", "journal_field", "protection_quantity", "risk_block", "live_position"])
def test_internally_inconsistent_checkpoint_is_rejected_before_restore(tmp_path, damage):
    from backend.services.durable_execution_state_v2 import seal
    path = tmp_path / "state.json"
    run_crash(path, "loss" if damage == "risk_block" else "open")
    state = json.loads(path.read_text())
    state.pop("checksum")
    if damage == "missing_fill":
        state["execution_records"]["paper"]["fills"] = []
    elif damage == "duplicate_fill":
        fills = state["execution_records"]["paper"]["fills"]
        fills.append(deepcopy(fills[0]))
    elif damage == "journal_field":
        state["execution_records"]["journal"][0].pop("created_at")
    elif damage == "protection_quantity":
        state["protective_registry"]["protections"][0]["quantity"] = 9.0
    elif damage == "live_position":
        state["active_positions"][0]["execution_mode"] = "LIVE"
    else:
        state["account_portfolio"]["account"]["state"]["trading_blocked"] = False
    path.write_text(json.dumps(seal(state, 100, "COMMITTED")))
    lifecycle, account, _, _, startup = build_runtime()
    with pytest.raises(ValueError):
        startup.startup_from(file_path=path)
    assert account.get_state()["trading_blocked"] is True
    assert lifecycle.get_active_positions() == []
    assert lifecycle.trade_journal_v2.trades == []
    assert lifecycle.broker_connector_v2.get_fills() == []


def test_recovery_cannot_erase_a_current_risk_block(tmp_path):
    path = tmp_path / "state.json"
    run_crash(path, "open")
    lifecycle, account, _, recovery, _ = build_runtime()
    account.record_daily_pnl(daily_pnl=-40.0)
    with pytest.raises(ValueError, match="existing risk block"):
        recovery.recover_from(file_path=path)
    assert account.get_state()["trading_blocked"] is True
    assert account.get_state()["daily_pnl"] == -40.0
    assert lifecycle.get_active_positions() == []


def test_empty_legacy_snapshot_migrates_without_inventing_activity(tmp_path):
    path = tmp_path / "state.json"
    _, _, source, _, _ = build_runtime()
    legacy = source.capture_state()
    legacy.pop("execution_records")
    path.write_text(json.dumps(legacy))
    lifecycle, _, store, recovery, startup = build_runtime()
    try:
        startup.startup_from(file_path=path)
        assert json.loads(path.read_text())["durability"]["phase"] == "COMMITTED"
        assert lifecycle.get_active_positions() == []
        assert lifecycle.trade_journal_v2.trades == []
        recovery.recover_from(file_path=path)
        with pytest.raises(RuntimeError, match="Cannot clear active"):
            recovery.clear_saved_state(file_path=path)
    finally:
        store._durability.release()


@pytest.mark.parametrize("phase", ["PENDING", "INVALID_CHECKSUM"])
def test_memory_recovery_verifies_persisted_envelope(phase):
    from backend.services.durable_execution_state_v2 import seal
    lifecycle, account, store, recovery, _ = build_runtime()
    state = seal(store.capture_state(), 1, "PENDING" if phase == "PENDING" else "COMMITTED")
    if phase == "INVALID_CHECKSUM":
        state["checksum"] = "invalid"
    with pytest.raises(ValueError):
        recovery.recover(state=state)
    assert recovery.get_last_recovery_report()["success"] is False
    assert account.get_state()["trading_blocked"] is True
    with pytest.raises(RuntimeError, match="failed closed"):
        open_position(lifecycle)


def test_read_only_load_cannot_authorize_overwriting_operational_state(tmp_path):
    path = tmp_path / "state.json"
    run_crash(path, "open")
    before = path.read_bytes()
    _, _, reader, _, _ = build_runtime()
    reader.load_from_file(file_path=path)
    with pytest.raises(ValueError, match="without recovery"):
        reader.save_to_file(file_path=path)
    assert path.read_bytes() == before


@pytest.mark.parametrize("action,phase,recoverable,count", [
    ("window_before_pending", "COMMITTED", True, 0),
    ("window_after_pending", "PENDING", False, 0),
    ("pending_open", "PENDING", False, 0),
    ("window_before_committed", "PENDING", False, 0),
    ("window_after_committed", "COMMITTED", True, 1),
])
def test_exact_crash_window_matrix(tmp_path, action, phase, recoverable, count):
    path = tmp_path / "state.json"
    run_crash(path, action)
    before = path.read_bytes()
    envelope = json.loads(before)
    assert envelope["durability"]["phase"] == phase
    assert envelope["durability"]["generation"] == (1 if action == "window_before_pending" else 2)
    lifecycle, account, store, recovery, startup = build_runtime()
    if recoverable:
        try:
            startup.startup_from(file_path=path)
            recovery.recover_from(file_path=path)
            assert len(lifecycle.get_active_positions()) == count
            assert len(lifecycle.broker_connector_v2.get_fills()) == count
            assert len(lifecycle.trade_journal_v2.trades) == count
            assert account.get_state()["realized_pnl"] == 0.0
            assert account.get_state()["daily_pnl"] == 0.0
        finally:
            store._durability.release()
    else:
        with pytest.raises(ValueError, match="Incomplete"):
            startup.startup_from(file_path=path)
        assert path.read_bytes() == before
        assert account.get_state()["trading_blocked"] is True
        assert lifecycle.get_active_positions() == []
        with pytest.raises(RuntimeError, match="failed closed"):
            open_position(lifecycle)


def test_restored_file_can_checkpoint_but_cannot_overwrite_another_file(tmp_path):
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    run_crash(first, "open")
    run_crash(second, "loss")
    _, _, store, recovery, _ = build_runtime()
    recovery.recover_from(file_path=first)
    generation = json.loads(first.read_text())["durability"]["generation"]
    store.save_to_file(file_path=first)
    assert json.loads(first.read_text())["durability"]["generation"] == generation + 1
    before = second.read_bytes()
    store.load_from_file(file_path=second)
    with pytest.raises(ValueError, match="without recovery"):
        store.save_to_file(file_path=second)
    assert second.read_bytes() == before


def test_same_generation_changed_file_is_not_overwritten(tmp_path):
    from backend.services.durable_execution_state_v2 import seal
    path = tmp_path / "state.json"
    run_crash(path, "open")
    _, _, store, recovery, _ = build_runtime()
    recovery.recover_from(file_path=path)
    raw = json.loads(path.read_text())
    raw.pop("checksum")
    raw["captured_at"] = "2026-09-11T01:00:00+00:00"
    path.write_text(json.dumps(seal(raw, raw["durability"]["generation"], "COMMITTED")))
    before = path.read_bytes()
    with pytest.raises(ValueError, match="without recovery"):
        store.save_to_file(file_path=path)
    assert path.read_bytes() == before


def test_manual_snapshot_does_not_reenable_stopped_runtime(tmp_path):
    path = tmp_path / "state.json"
    lifecycle, _, store, _, startup = build_runtime()
    startup.startup_from(file_path=path)
    store._durability.release()
    store.save_to_file(file_path=path)
    with pytest.raises(RuntimeError, match="failed closed"):
        open_position(lifecycle)
    assert lifecycle.broker_connector_v2.get_fills() == []


if __name__ == "__main__":
    crash_worker(Path(sys.argv[1]), sys.argv[2])
