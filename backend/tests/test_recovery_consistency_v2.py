"""Phase 0.9B: reject semantic contradictions, preserve evidence and continue safely."""
from copy import deepcopy
import json

import pytest

from backend.services.durable_execution_state_v2 import seal, evidence_path
from backend.services.live_position_monitor_v2 import LivePositionMonitorV2
from backend.execution.partial_take_profit_engine_v2 import PartialTakeProfitEngineV2
from backend.execution.realized_pnl_engine_v2 import RealizedPnLEngineV2
from backend.tests.test_durable_crash_recovery_v2 import (
    build_runtime, open_position, partial, comparable, run_crash,
)
from backend.tests.test_pending_operation_reconciliation_v2 import crash, rewrite_evidence


DAMAGES = ["broker_entry", "entry_quantity", "broker_quantity", "journal_entry",
           "broker_sl", "broker_tp", "closed_without_broker", "over_close",
           "economic_pnl", "daily_pnl", "missing_paper", "missing_oco"]


def damage_state(state, damage):
    paper = state["execution_records"]["paper"]
    if damage == "broker_entry":
        next(iter(paper["positions"].values()))["entry_price"] = 101.
    elif damage == "entry_quantity":
        paper["fills"][0]["quantity"] = 1.
    elif damage == "broker_quantity":
        next(iter(paper["positions"].values()))["quantity"] = 99.
    elif damage == "journal_entry":
        state["execution_records"]["journal"][0]["entry"] = 101.
    elif damage in {"broker_sl", "broker_tp"}:
        next(iter(paper["positions"].values()))[
            "stop_loss" if damage == "broker_sl" else "take_profit"] = 95.
    elif damage in {"missing_paper", "closed_without_broker"}:
        paper["positions"] = {}
    elif damage == "missing_oco":
        state["execution_records"]["oco_groups"] = []
        state["oco_manager"]["groups"] = []
    elif damage == "over_close":
        fill = deepcopy(paper["fills"][0])
        fill.update(fill_id="over-close", fill_type="PARTIAL_CLOSE", quantity=3,
                    side="SELL", position_id=next(iter(paper["positions"])))
        paper["fills"].append(fill)
    elif damage == "economic_pnl":
        state["account_portfolio"]["closed_positions"][0]["realized_pnl"] = 40.
        state["execution_records"]["journal"][0]["pnl"] = 40.
        state["execution_records"]["history"][0]["realized_pnl"] = 40.
        account = state["account_portfolio"]["account"]["state"]
        for key in ("daily_pnl", "realized_pnl", "total_pnl", "profit_achieved"):
            account[key] = 40.
        for key in ("balance", "equity", "peak_equity"):
            account[key] = 17040.
    elif damage == "daily_pnl":
        state["account_portfolio"]["account"]["state"]["daily_pnl"] = 10.


def snapshot(action="open"):
    lifecycle, _, store, _, _ = build_runtime()
    position = open_position(lifecycle)
    if action == "full":
        lifecycle.update_position(position_id=position["position_id"], current_price=120.)
    return store.capture_state()


def assert_fenced(lifecycle, account, store):
    assert store._durability.failed
    assert account.get_state()["trading_blocked"]
    before = deepcopy(store._capture_records())
    with pytest.raises(RuntimeError):
        open_position(lifecycle)
    assert store._capture_records() == before


@pytest.mark.parametrize("damage", DAMAGES)
def test_committed_contradiction_preserves_evidence_and_blocks(tmp_path, damage):
    state = snapshot("full" if damage in {"closed_without_broker", "over_close", "economic_pnl"} else "open")
    damage_state(state, damage)
    path = tmp_path / "state.json"
    path.write_text(json.dumps(seal(state, 1, "COMMITTED")))
    persisted = path.read_bytes()
    lifecycle, account, store, recovery, _ = build_runtime()
    before = store._capture_records()
    with pytest.raises(ValueError):
        recovery.recover_from(file_path=path)
    assert not recovery.get_last_recovery_report()["success"]
    assert store._capture_records() == before
    assert not lifecycle.get_active_positions()
    assert path.read_bytes() == persisted
    assert_fenced(lifecycle, account, store)


@pytest.mark.parametrize("damage", DAMAGES)
def test_pending_contradiction_preserves_evidence_and_blocks(tmp_path, damage):
    path = tmp_path / "state.json"
    action = "full" if damage in {"closed_without_broker", "over_close", "economic_pnl"} else "complete"
    crash(path, action)
    rewrite_evidence(path, lambda value: damage_state(value["state"], damage))
    persisted = (path.read_bytes(), evidence_path(path).read_bytes())
    lifecycle, account, store, recovery, _ = build_runtime()
    before = store._capture_records()
    try:
        result = recovery.reconcile_pending_from(file_path=path)
        assert result["status"] == "AMBIGUOUS", result
        assert not result["restored"] and not result["resolved"]
        assert store._capture_records() == before
        assert persisted == (path.read_bytes(), evidence_path(path).read_bytes())
        assert_fenced(lifecycle, account, store)
    finally:
        store._durability.release()


@pytest.mark.parametrize("record", ["orders", "fills", "positions", "client_order_index"])
@pytest.mark.parametrize("mode", ["committed", "pending"])
def test_nonempty_broker_evidence_is_never_discarded(tmp_path, record, mode):
    path = tmp_path / "state.json"
    if mode == "pending":
        crash(path, "prepared")
    lifecycle, account, store, recovery, _ = build_runtime()
    if mode == "committed":
        path.write_text(json.dumps(seal(store.capture_state(), 1, "COMMITTED")))
    evidence = [{"fill_id": "isolated-fill"}] if record == "fills" else {"isolated": "evidence"}
    setattr(lifecycle.broker_connector_v2, "_" + record, deepcopy(evidence))
    before = store._capture_records()
    persisted = path.read_bytes()
    try:
        if mode == "committed":
            with pytest.raises(ValueError):
                recovery.recover_from(file_path=path)
        else:
            result = recovery.reconcile_pending_from(file_path=path)
            assert not result["resolved"] and not result["restored"]
        assert before == store._capture_records()
        assert path.read_bytes() == persisted
        assert_fenced(lifecycle, account, store)
    finally:
        store._durability.release()


def test_missing_authorities_cannot_restore_phantom_position(tmp_path):
    state = snapshot()
    state["account_portfolio"] = None
    state["execution_records"]["journal"] = None
    state["execution_records"]["paper"].update(orders={}, fills=[], positions={}, client_order_index={})
    lifecycle, _, store, recovery, _ = build_runtime()
    lifecycle.portfolio_manager_v2 = None
    lifecycle.trade_journal_v2 = None
    with pytest.raises(ValueError):
        recovery.recover(state=state)
    assert store._durability.failed
    assert not lifecycle.get_active_positions()
    assert not lifecycle.broker_connector_v2.get_fills()


@pytest.mark.parametrize("participant", ["broker", "journal", "account", "oco", "fill_identity"])
def test_post_restore_detects_incomplete_reconstruction(monkeypatch, participant):
    state = snapshot()
    lifecycle, account, store, recovery, _ = build_runtime()
    original = store._restore_records
    def incomplete(records):
        original(records)
        if participant == "broker":
            lifecycle.broker_connector_v2._positions = {}
        elif participant == "journal":
            lifecycle.trade_journal_v2.trades = []
        elif participant == "account":
            account._state["daily_pnl"] = 10.
        elif participant == "oco":
            store.oco_manager._groups = {}
        else:
            lifecycle.broker_connector_v2._fills[0]["fill_id"] = "different-valid-identity"
    monkeypatch.setattr(store, "_restore_records", incomplete)
    with pytest.raises(ValueError):
        recovery.recover(state=state)
    assert not recovery.get_last_recovery_report()["success"]
    assert store._restored_state is None
    assert_fenced(lifecycle, account, store)


@pytest.mark.parametrize("restart", [False, True])
def test_monitor_partial_then_full_close_has_one_economic_pnl(tmp_path, restart):
    path = tmp_path / "state.json"
    if restart:
        run_crash(path, "monitor_partial")
    lifecycle, account, store, recovery, startup = build_runtime()
    startup.startup_from(file_path=path)
    try:
        if not restart:
            open_position(lifecycle)
        monitor = LivePositionMonitorV2(trade_lifecycle_service=lifecycle,
            portfolio_manager_v2=lifecycle.portfolio_manager_v2,
            partial_take_profit_engine=PartialTakeProfitEngineV2(trigger_profit_points=10., close_fraction=.5),
            realized_pnl_engine=RealizedPnLEngineV2(point_value=2.))
        monitor.process_price(symbol="MNQ", current_price=110.)
        assert account.get_state()["daily_pnl"] == 20.
        assert len(lifecycle.broker_connector_v2.get_fills()) == 2
        monitor.process_price(symbol="MNQ", current_price=120.)
        assert account.get_state()["realized_pnl"] == account.get_state()["daily_pnl"] == 60.
        assert lifecycle.portfolio_manager_v2.get_total_realized_pnl() == 60.
        assert lifecycle.trade_journal_v2.trades[0].pnl == 60.
        assert lifecycle.trade_history_manager.get_history()[0]["realized_pnl"] == 60.
        assert not lifecycle.get_active_positions()
        assert not store.protective_order_registry.list_protections(status="ACTIVE")
        assert not store.oco_manager.list_groups(status="ACTIVE")
        before = comparable(store.capture_state())
        monitor.process_price(symbol="MNQ", current_price=120.)
        assert comparable(store.capture_state()) == before
        assert json.loads(path.read_text())["durability"]["phase"] == "COMMITTED"
    finally:
        store._durability.release()
    fresh, risk, target, restore, _ = build_runtime()
    restore.recover_from(file_path=path)
    assert comparable(target.capture_state()) == before
    assert restore.recover_from(file_path=path)["restore_result"]["idempotent"]
    assert not fresh.get_active_positions()
    assert risk.get_state()["daily_pnl"] == 60.


@pytest.mark.parametrize("component", ["journal", "portfolio", "account", "registry", "oco"])
def test_missing_or_unshared_authority_blocks_even_empty_recovery(component):
    lifecycle, account, store, recovery, _ = build_runtime()
    state = store.capture_state()
    if component == "journal":
        lifecycle.trade_journal_v2 = None
    elif component == "portfolio":
        lifecycle.portfolio_manager_v2 = None
    elif component == "account":
        lifecycle.portfolio_manager_v2.account_state_manager_v2 = None
    elif component == "registry":
        lifecycle.protective_order_registry_v2 = type(store.protective_order_registry)()
    else:
        lifecycle.oco_manager_v2 = type(store.oco_manager)()
    with pytest.raises(ValueError):
        recovery.recover(state=state)
    assert store._durability.failed
    assert not lifecycle.get_active_positions()
    assert not lifecycle.broker_connector_v2.get_fills()


@pytest.mark.parametrize("record", ["journal", "history", "portfolio_open", "portfolio_closed", "protection", "oco", "account"])
def test_other_destination_evidence_is_preserved(record):
    lifecycle, account, store, recovery, _ = build_runtime()
    state = store.capture_state()
    source = snapshot("full" if record == "portfolio_closed" else "open")
    if record == "journal":
        lifecycle.trade_journal_v2.trades = [store._journal_entry(source["execution_records"]["journal"][0])]
    elif record == "history":
        lifecycle.trade_history_manager._history = [{"position_id": "existing-history"}]
    elif record == "portfolio_open":
        lifecycle.portfolio_manager_v2._open_positions = {"existing": source["account_portfolio"]["open_positions"][0]}
    elif record == "portfolio_closed":
        lifecycle.portfolio_manager_v2._closed_positions = source["account_portfolio"]["closed_positions"]
    elif record == "protection":
        store.protective_order_registry._protections = {"existing": source["execution_records"]["protections"][0]}
    elif record == "oco":
        store.oco_manager._groups = {"existing": source["execution_records"]["oco_groups"][0]}
    else:
        account._state["realized_pnl"] = 20.
    before = store.capture_state()
    with pytest.raises(ValueError):
        recovery.recover(state=state)
    after = store.capture_state()
    before["captured_at"] = after["captured_at"]
    before["account_portfolio"]["account"]["state"]["trading_blocked"] = True
    before["account_portfolio"]["account"]["state"]["blocking_reasons"].append("durability_consistency_unproven")
    assert before == after
    assert_fenced(lifecycle, account, store)


@pytest.mark.parametrize("result", [None, {}, {"restored": False}, {"restored": True}])
def test_recovery_cannot_trust_a_report_without_operational_restoration(monkeypatch, result):
    lifecycle, account, store, recovery, _ = build_runtime()
    monkeypatch.setattr(store, "restore_state", lambda **kwargs: result)
    with pytest.raises(ValueError):
        recovery.recover(state=snapshot())
    assert_fenced(lifecycle, account, store)


def test_short_partial_economics_and_daily_adjustment_survive_recovery(tmp_path):
    from backend.tests.test_durable_crash_recovery_v2 import signal
    lifecycle, account, store, _, startup = build_runtime()
    path = tmp_path / "short.json"
    startup.startup_from(file_path=path)
    try:
        order = signal()
        order.update(direction="SHORT", stop_loss=110., take_profit=80.)
        result = lifecycle.submit_signal(signal=order, order_type="MARKET", risk_context={
            "account_balance": 17000., "risk_percent": .25, "point_value": 2., "daily_pnl": 0., "total_drawdown": 0.})
        assert result["accepted"]
        position = result["position"]
        position.update(quantity=1., current_price=90., partial_exit_price=90., partial_taken=True,
                        partial_pnl_recorded=True, partial_closed_quantity=1., realized_pnl=20.)
        lifecycle.replace_active_position(position=position)
        account.record_daily_pnl(daily_pnl=10.)  # Explicit risk input: a -10 adjustment, not a trade.
        lifecycle.update_position(position_id=position["position_id"], current_price=80.)
        assert account.get_state()["realized_pnl"] == 60.
        assert account.get_state()["daily_pnl"] == 50.
        expected = comparable(store.capture_state())
    finally:
        store._durability.release()
    fresh, risk, target, recovery, _ = build_runtime()
    recovery.recover_from(file_path=path)
    assert comparable(target.capture_state()) == expected
    assert risk.get_state()["daily_pnl"] == 50.
    assert len(fresh.broker_connector_v2.get_fills()) == 2
    assert recovery.recover_from(file_path=path)["restore_result"]["idempotent"]
