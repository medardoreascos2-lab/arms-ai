"""PAPER reconciliation with actual abrupt process exits and persisted evidence."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from backend.services.durable_execution_state_v2 import canonical, evidence_path
from backend.tests.test_durable_crash_recovery_v2 import (
    build_runtime, comparable, open_position, partial,
)
from backend.tests.test_paper_execution_engine_v2 import build_valid_order


def worker(path, action):
    lifecycle, account, store, recovery, startup = build_runtime()
    if action.startswith("reconcile_"):
        from backend.services import pending_operation_reconciliation_v2 as reconcile
        if action == "reconcile_before_restore":
            store.restore_state = lambda **kw: os._exit(23)
        if action == "reconcile_restore":
            original = store._restore_records
            def interrupt(records):
                original(records)
                os._exit(23)
            store._restore_records = interrupt
        else:
            original = reconcile.atomic_write
            def interrupt(target, value):
                if action == "reconcile_before_commit":
                    os._exit(23)
                if action == "reconcile_tmp":
                    with target.with_suffix(target.suffix + ".tmp").open("wb") as stream:
                        stream.write(canonical(value) + b"\n")
                        stream.flush()
                        os.fsync(stream.fileno())
                    os._exit(23)
                original(target, value)
                os._exit(23)
            reconcile.atomic_write = interrupt
        recovery.reconcile_pending_from(file_path=path)
        raise AssertionError("Fault injection did not fire")
    startup.startup_from(file_path=path)
    if action in {"partial", "partial_complete", "full", "loss", "partial_then_broker_close", "partial_during_close"}:
        position = open_position(lifecycle)
    if action in {"prepared", "started"}:
        original = store._durability.record_evidence
        def interrupt(stage, state):
            if stage == "STARTED" and action == "prepared":
                os._exit(23)
            original(stage, state)
            if stage == "STARTED":
                os._exit(23)
        store._durability.record_evidence = interrupt
    if action == "broker_without_journal":
        lifecycle.trade_journal_v2.record_open_trade = lambda **kw: os._exit(23)
    if action in {"complete", "partial_complete", "full", "loss"}:
        store._durability.checkpoint = lambda: os._exit(23)
    if action in {"partial", "partial_then_broker_close", "partial_during_close"}:
        with store._durability.mutation():
            partial(lifecycle)
            if action == "partial_during_close":
                original = store._durability.record_evidence
                def interrupt(stage, state):
                    if stage == "OBSERVED":
                        os._exit(23)  # PAPER close occurred, but no observation was persisted.
                    original(stage, state)
                store._durability.record_evidence = interrupt
            if action in {"partial_then_broker_close", "partial_during_close"}:
                lifecycle.broker_connector_v2.close_position(
                    position_id=position["broker_position_id"], current_price=120.0, reason="TAKE_PROFIT")
            os._exit(23)
    elif action == "partial_complete":
        partial(lifecycle)
    elif action in {"full", "loss"}:
        lifecycle.update_position(position_id=position["position_id"],
                                  current_price=90.0 if action == "loss" else 120.0)
    elif action == "submitted":
        order = build_valid_order()
        order.update(order_type="LIMIT", limit_price=99.0)
        with store._durability.mutation():
            lifecycle.broker_connector_v2.submit_order(prepared_order=order)
            os._exit(23)
    else:
        open_position(lifecycle)
    raise AssertionError("Fault injection did not fire")


def crash(path, action):
    result = subprocess.run([sys.executable, "-m",
                            "backend.tests.test_pending_operation_reconciliation_v2", str(path), action],
                            cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True, timeout=30)
    assert result.returncode == 23, result.stdout + result.stderr


def rewrite_evidence(path, change):
    value = json.loads(evidence_path(path).read_text(encoding="utf-8"))
    change(value)
    value.pop("checksum")
    value["checksum"] = hashlib.sha256(canonical(value)).hexdigest()
    evidence_path(path).write_bytes(canonical(value) + b"\n")


@pytest.mark.parametrize("action,status,quantity,pnl,fills,resolved", [
    ("prepared", "CONFIRMED_NOT_EXECUTED", 0, 0, 0, True),  # A
    ("submitted", "PARTIALLY_EXECUTED", 0, 0, 0, False),  # B
    ("complete", "CONFIRMED_EXECUTED", 2, 0, 1, True),  # C
    ("partial", "PARTIALLY_EXECUTED", 1, 20, 2, False),  # D
    ("partial_complete", "CONFIRMED_EXECUTED", 1, 20, 2, True),
    ("full", "CONFIRMED_EXECUTED", 0, 80, 1, True),
    ("loss", "CONFIRMED_EXECUTED", 0, -40, 1, True),
])
def test_reconcile_exact_state_and_repeat(tmp_path, action, status, quantity, pnl, fills, resolved):
    path = tmp_path / "state.json"
    crash(path, action)
    persisted = path.read_bytes()
    expected = json.loads(evidence_path(path).read_text(encoding="utf-8"))["state"]
    for attempt in range(2):
        lifecycle, account, store, recovery, _ = build_runtime()
        try:
            # Reconstruction must never execute an order or accounting callback.
            def forbidden(**kw):
                raise AssertionError("Reconciliation replayed an execution/accounting side effect")
            lifecycle.broker_connector_v2.submit_order = forbidden
            lifecycle.broker_connector_v2.close_partial = forbidden
            lifecycle.broker_connector_v2.close_position = forbidden
            lifecycle.trade_journal_v2.record_open_trade = forbidden
            lifecycle.trade_journal_v2.close_trade = forbidden
            account.update_from_portfolio = forbidden
            result = recovery.reconcile_pending_from(file_path=path)
            assert result["status"] == status, result
            assert result["resolved"] is resolved
            assert result["restored"] is True
            current = comparable(store.capture_state())
            expected_state = comparable(expected)
            if not resolved:
                expected_state["account_portfolio"]["account"]["state"]["trading_blocked"] = True
                expected_state["account_portfolio"]["account"]["state"]["blocking_reasons"].append("durability_consistency_unproven")
            assert current == expected_state
            assert recovery.reconcile_pending_from(file_path=path)["idempotent"] is True  # I
            assert comparable(store.capture_state()) == current
            assert sum(p["quantity"] for p in lifecycle.get_active_positions()) == quantity
            assert account.get_state()["realized_pnl"] == account.get_state()["daily_pnl"] == pnl
            assert len(lifecycle.broker_connector_v2.get_fills()) == fills
            if not resolved:
                assert path.read_bytes() == persisted
                with pytest.raises(RuntimeError):
                    lifecycle.update_position(position_id="anything", current_price=100)
            if action == "submitted":
                assert len(lifecycle.broker_connector_v2.get_orders()) == 1
                assert not lifecycle.trade_journal_v2.trades
            if action in {"full", "loss"}:
                assert len(lifecycle.portfolio_manager_v2.get_closed_positions()) == 1
                assert not store.protective_order_registry.list_protections(status="ACTIVE")
                assert not store.oco_manager.list_groups(status="ACTIVE")
        finally:
            store._durability.release()


@pytest.mark.parametrize("action,damage,status", [
    ("started", None, "AMBIGUOUS"),
    ("broker_without_journal", None, "AMBIGUOUS"),  # F
    ("partial_then_broker_close", None, "AMBIGUOUS"),
    ("partial_during_close", None, "AMBIGUOUS"),
    ("complete", "missing_fill", "AMBIGUOUS"),  # E
    ("complete", "fill_price", "AMBIGUOUS"),  # G
    ("complete", "identity", "AMBIGUOUS"),
    ("complete", "generation", "AMBIGUOUS"),
    ("complete", "journal", "AMBIGUOUS"),
    ("complete", "duplicate_fill", "AMBIGUOUS"),
    ("complete", "checksum", "CORRUPT"),  # H
    ("complete", "pending_json", "CORRUPT"),
    ("complete", "pending_scalar", "CORRUPT"),
    ("complete", "pending_checksum", "CORRUPT"),
    ("complete", "tmp", "AMBIGUOUS"),
    ("complete", "evidence_tmp", "AMBIGUOUS"),
    ("complete", "missing_evidence", "AMBIGUOUS"),
])
def test_insufficient_contradictory_or_corrupt_never_guessed(tmp_path, action, damage, status):
    path = tmp_path / "state.json"
    crash(path, action)
    def change(value):
        paper = value["state"]["execution_records"]["paper"]
        if damage == "missing_fill":
            paper["fills"] = []
        elif damage == "fill_price":
            paper["fills"][0]["filled_price"] += 1
        elif damage == "identity":
            value["operation_id"] = "unrelated-operation"
        elif damage == "generation":
            value["generation"] += 1
        elif damage == "journal":
            value["state"]["execution_records"]["journal"] = []
        elif damage == "duplicate_fill":
            paper["fills"].append(deepcopy(paper["fills"][0]))
    if damage in {"missing_fill", "fill_price", "identity", "generation", "journal", "duplicate_fill"}:
        rewrite_evidence(path, change)
    elif damage == "checksum":
        evidence_path(path).write_text('{}')
    elif damage == "pending_json":
        path.write_text('{')
    elif damage == "pending_scalar":
        path.write_text('[]')
    elif damage == "pending_checksum":
        value = json.loads(path.read_text())
        value["checksum"] = "wrong"
        path.write_text(json.dumps(value))
    elif damage == "tmp":
        path.with_suffix(".json.tmp").write_text('{')
    elif damage == "evidence_tmp":
        evidence_path(path).with_suffix(".json.tmp").write_text('{')
    elif damage == "missing_evidence":
        evidence_path(path).unlink()
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir() if p.suffix != ".lock"}
    lifecycle, account, store, recovery, _ = build_runtime()
    try:
        result = recovery.reconcile_pending_from(file_path=path)
        assert result["status"] == status, result
        assert not result["resolved"] and not result["restored"]
        assert recovery.reconcile_pending_from(file_path=path)["idempotent"]
        assert not lifecycle.get_active_positions()
        assert not lifecycle.trade_journal_v2.trades
        assert not lifecycle.broker_connector_v2.get_fills()
        assert account.get_state()["realized_pnl"] == account.get_state()["daily_pnl"] == 0
        assert account.get_state()["trading_blocked"]
        with pytest.raises(RuntimeError):
            open_position(lifecycle)
        after = {p.name: p.read_bytes() for p in tmp_path.iterdir() if p.suffix != ".lock"}
        assert before == after
    finally:
        store._durability.release()


@pytest.mark.parametrize("action,window", [
    (action, window) for action in ("complete", "full")
    for window in ("restore", "before_commit", "tmp", "after_commit")
] + [("partial", "restore")])
def test_crash_during_reconciliation(tmp_path, window, action):  # J
    path = tmp_path / "state.json"
    crash(path, action)
    expected = json.loads(evidence_path(path).read_text(encoding="utf-8"))["state"]
    if window == "restore":
        # Reconciliation retains the original PENDING; it does not write a new
        # PENDING. A crash before reconstruction must leave both sources intact.
        before = (path.read_bytes(), evidence_path(path).read_bytes())
        crash(path, "reconcile_before_restore")
        assert before == (path.read_bytes(), evidence_path(path).read_bytes())
    crash(path, "reconcile_" + window)
    _, account, store, recovery, _ = build_runtime()
    try:
        result = recovery.reconcile_pending_from(file_path=path)
        assert result["restored"], result
        assert result["resolved"] is (action != "partial")
        assert account.get_state()["realized_pnl"] == expected["account_portfolio"]["account"]["state"]["realized_pnl"]
        assert store._capture_records() == expected["execution_records"]
        assert recovery.reconcile_pending_from(file_path=path)["idempotent"]
    finally:
        store._durability.release()


@pytest.mark.parametrize("action", ["prepared", "complete", "full"])
def test_reconciliation_then_new_valid_operation(tmp_path, action):  # K
    path = tmp_path / "state.json"
    crash(path, action)
    lifecycle, account, store, recovery, startup = build_runtime()
    try:
        assert recovery.reconcile_pending_from(file_path=path)["resolved"]
        startup.startup_from(file_path=path)
        if action == "complete":
            position = lifecycle.get_active_positions()[0]
            lifecycle.update_position(position_id=position["position_id"], current_price=120)
        before = account.get_state()["realized_pnl"]
        fills_before = len(lifecycle.broker_connector_v2.get_fills())
        open_position(lifecycle)
        assert len(lifecycle.broker_connector_v2.get_fills()) == fills_before + 1
        assert account.get_state()["realized_pnl"] == before
        assert account.get_state()["daily_pnl"] == before
        assert comparable(store.load_from_file(file_path=path)) == comparable(store.capture_state())
        with pytest.raises(RuntimeError, match="changed"):
            recovery.reconcile_pending_from(file_path=path)
    finally:
        store._durability.release()


def test_structural_block_is_never_removed(tmp_path):
    path = tmp_path / "state.json"
    crash(path, "complete")
    lifecycle, account, store, recovery, _ = build_runtime()
    account._state.update(trading_blocked=True, blocking_reasons=["structural_account_block"])
    try:
        result = recovery.reconcile_pending_from(file_path=path)
        assert not result["resolved"]
        assert "structural_account_block" in account.get_state()["blocking_reasons"]
        assert not lifecycle.broker_connector_v2.get_fills()
        assert not lifecycle.get_active_positions()
    finally:
        store._durability.release()


@pytest.mark.parametrize("temporary", [False, True])
def test_orphaned_evidence_denies_clean_start_and_manual_overwrite(tmp_path, temporary):
    path = tmp_path / "state.json"
    artifact = evidence_path(path)
    if temporary:
        artifact = artifact.with_suffix(artifact.suffix + ".tmp")
    artifact.write_text('{}')
    _, account, store, _, startup = build_runtime()
    with pytest.raises(FileNotFoundError):
        startup.startup_from(file_path=path)
    assert account.get_state()["trading_blocked"]
    _, _, manual, _, _ = build_runtime()
    with pytest.raises(ValueError, match="orphaned"):
        manual.save_to_file(file_path=path)
    assert artifact.read_text() == '{}'
    assert not path.exists()


def test_competing_writer_cannot_reconcile(tmp_path):
    path = tmp_path / "state.json"
    crash(path, "complete")
    _, _, first, _, _ = build_runtime()
    first._durability.acquire(path)
    _, account, second, recovery, _ = build_runtime()
    try:
        before = path.read_bytes()
        with pytest.raises(RuntimeError, match="runtime writer"):
            recovery.reconcile_pending_from(file_path=path)
        assert account.get_state()["trading_blocked"]
        assert path.read_bytes() == before
    finally:
        first._durability.release()
        second._durability.release()


def test_live_connector_is_not_called(tmp_path):
    from unittest.mock import Mock
    path = tmp_path / "state.json"
    crash(path, "complete")
    lifecycle, account, store, recovery, _ = build_runtime()
    broker = Mock(execution_mode="LIVE")
    lifecycle.broker_connector_v2 = broker
    before = path.read_bytes()
    with pytest.raises(ValueError, match="only for PAPER"):
        recovery.reconcile_pending_from(file_path=path)
    assert not broker.mock_calls
    assert account.get_state()["trading_blocked"]
    assert path.read_bytes() == before


def test_legacy_pending_remains_ambiguous(tmp_path):
    from backend.services.durable_execution_state_v2 import seal
    lifecycle, account, store, recovery, _ = build_runtime()
    path = tmp_path / "state.json"
    path.write_bytes(canonical(seal(store.capture_state(), 2, "PENDING")))
    try:
        assert recovery.reconcile_pending_from(file_path=path)["status"] == "AMBIGUOUS"
        assert not lifecycle.broker_connector_v2.get_fills()
        assert account.get_state()["trading_blocked"]
    finally:
        store._durability.release()


def test_persisted_partial_entry_restores_only_filled_contract(tmp_path):
    """Explicit persisted fixture: PAPER's normal engine only emits full entries.

    All participants describe one filled contract out of a two-contract order.
    The reconciler must not create the unfilled contract or claim completion.
    """
    path = tmp_path / "state.json"
    crash(path, "complete")
    def partial_entry(value):
        state = value["state"]
        paper = state["execution_records"]["paper"]
        order = next(iter(paper["orders"].values()))
        order["status"] = "PARTIALLY_FILLED"
        paper["fills"][0]["quantity"] = 1
        next(iter(paper["positions"].values()))["quantity"] = 1
        state["active_positions"][0]["quantity"] = 1
        state["account_portfolio"]["open_positions"][0]["quantity"] = 1
        state["execution_records"]["journal"][0]["contracts"] = 1
        state["execution_records"]["protections"][0]["quantity"] = 1
        state["protective_registry"]["protections"][0]["quantity"] = 1
    rewrite_evidence(path, partial_entry)
    expected = json.loads(evidence_path(path).read_text(encoding="utf-8"))["state"]
    lifecycle, account, store, recovery, _ = build_runtime()
    try:
        result = recovery.reconcile_pending_from(file_path=path)
        assert result["status"] == "PARTIALLY_EXECUTED", result
        assert result["restored"] and not result["resolved"]
        assert store._capture_records() == expected["execution_records"]
        assert lifecycle.get_active_positions()[0]["quantity"] == 1
        assert account.get_state()["realized_pnl"] == account.get_state()["daily_pnl"] == 0
        assert account.get_state()["trading_blocked"]
        assert recovery.reconcile_pending_from(file_path=path)["idempotent"]
    finally:
        store._durability.release()

    # Quantity conservation must also hold after full closure. A terminal
    # status cannot make contradictory partial fills safe to promote.
    for action in ("partial_complete", "full"):
        conflict_path = tmp_path / (action + "-conflict.json")
        crash(conflict_path, action)
        def inconsistent_quantity(value):
            paper = value["state"]["execution_records"]["paper"]
            if action == "partial_complete":
                paper["fills"][-1]["quantity"] = 3
            else:
                fill = deepcopy(paper["fills"][0])
                fill.update(fill_id="contradictory-partial", fill_type="PARTIAL_CLOSE",
                            quantity=3, side="SELL", position_id=next(iter(paper["positions"])))
                paper["fills"].append(fill)
        rewrite_evidence(conflict_path, inconsistent_quantity)
        before = (conflict_path.read_bytes(), evidence_path(conflict_path).read_bytes())
        lifecycle, account, store, recovery, _ = build_runtime()
        try:
            result = recovery.reconcile_pending_from(file_path=conflict_path)
            assert result["status"] == "AMBIGUOUS", result
            assert not result["restored"] and not result["resolved"]
            assert not lifecycle.broker_connector_v2.get_fills()
            assert not lifecycle.get_active_positions()
            assert not lifecycle.trade_journal_v2.trades
            assert account.get_state()["realized_pnl"] == account.get_state()["daily_pnl"] == 0
            assert account.get_state()["trading_blocked"]
            assert recovery.reconcile_pending_from(file_path=conflict_path)["idempotent"]
            with pytest.raises(RuntimeError):
                open_position(lifecycle)
            assert before == (conflict_path.read_bytes(), evidence_path(conflict_path).read_bytes())
        finally:
            store._durability.release()


def test_evidence_write_failure_cannot_enter_operation(tmp_path, monkeypatch):
    lifecycle, account, store, _, startup = build_runtime()
    path = tmp_path / "state.json"
    startup.startup_from(file_path=path)
    before = path.read_bytes()
    def fail(_):
        raise OSError("injected evidence fsync failure")
    monkeypatch.setattr(os, "fsync", fail)
    try:
        with pytest.raises(OSError):
            open_position(lifecycle)
        assert path.read_bytes() == before
        assert not lifecycle.broker_connector_v2.get_orders()
        assert not lifecycle.broker_connector_v2.get_fills()
        assert not lifecycle.trade_journal_v2.trades
        assert account.get_state()["trading_blocked"]
    finally:
        store._durability.release()


if __name__ == "__main__":
    worker(Path(sys.argv[1]), sys.argv[2])
