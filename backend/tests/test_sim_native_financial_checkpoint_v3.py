"""Offline Account-core -> existing financial owners -> durable checkpoint."""
from copy import deepcopy
import json

import pytest

from backend.tests.test_controlled_sim_operation_v3 import binary, run, KEY, fields, authority, CONTEXT, BINDING
from backend.services.sim_native_runtime_v3 import build_native_sim_runtime


def financial(namespace_root):
    runtime = build_native_sim_runtime(binding=BINDING, namespace_root=namespace_root, authority_key=KEY,
        runtime_evidence=lambda: {}, protection_timeout_us=1_000_000, recovery_timeout_us=20_000_000,
        envelope=authority().issue(fields(), **CONTEXT))
    return runtime.store, runtime.lifecycle, runtime.lifecycle.portfolio_manager_v2.account_state_manager_v2


def phases(root):
    return [p.read_bytes() for p in sorted((root/"state").glob("*.state"))]


@pytest.mark.parametrize("mode,pnl", [("protected", 0), ("target_fill", 400), ("stop_fill", -200), ("invalid_stop", 0)])
def test_native_facts_checkpoint_real_owners_once(binary, tmp_path, mode, pnl):
    native = tmp_path/"native"
    result = run(binary, native, mode)
    assert not result["error"]
    store, lifecycle, account = financial(tmp_path)
    path = BINDING.checkpoint_path(tmp_path)
    store.start(path)
    try:
        wire = phases(native)[-1]
        receipt = store.apply_phase(wire)
        assert store.apply_phase(wire) == receipt
        assert len(lifecycle.trade_journal_v2.trades) == 1
        assert account.get_state()["realized_pnl"] == pnl
        assert len(lifecycle.portfolio_manager_v2.get_closed_positions()) == int(mode.endswith("fill"))
        assert len(lifecycle.get_active_positions()) == int(not mode.endswith("fill"))
        persisted = json.loads(path.read_text())
        assert len(persisted["native_financial"]["executions"]) == (2 if mode.endswith("fill") else 1)
        assert persisted["execution_records"]["paper"] is None
        assert persisted["execution_records"]["protections"] == []
        before = deepcopy(persisted["account_portfolio"])
        events = []
        store.publish_pending(lambda **kw: events.append(kw))
        store.publish_pending(lambda **kw: events.append(kw))
        assert len(events) == len(persisted["native_financial"]["executions"])
        assert json.loads(path.read_text())["account_portfolio"] == before
    finally:
        store._durability.release()
    restored, lifecycle2, account2 = financial(tmp_path)
    restored.start(path)
    try:
        restored.apply_phase(wire)
        assert account2.get_state()["realized_pnl"] == pnl
        assert len(lifecycle2.trade_journal_v2.trades) == 1
        assert lifecycle2.portfolio_manager_v2.capture_risk_state() == before
        replay = []
        restored.publish_pending(lambda **kw: replay.append(kw))
        assert replay == []
    finally:
        restored._durability.release()


def test_dashboard_crash_replays_identity_without_reapplying_money(binary, tmp_path):
    native = tmp_path/"native"
    run(binary, native, "target_fill")
    store, lifecycle, account = financial(tmp_path)
    path = BINDING.checkpoint_path(tmp_path)
    store.start(path)
    events = []
    try:
        store.apply_phase(phases(native)[-1])
        before = lifecycle.portfolio_manager_v2.capture_risk_state()
        def crashed(**kw):
            events.append(kw)
            raise RuntimeError("connection lost after delivery")
        with pytest.raises(RuntimeError):
            store.publish_pending(crashed)
    finally:
        store._durability.release()
    restored, lifecycle, account = financial(tmp_path)
    restored.start(path)
    try:
        restored.publish_pending(lambda **kw: events.append(kw))
        assert events[0]["event_id"] == events[1]["event_id"]
        assert lifecycle.portfolio_manager_v2.capture_risk_state() == before
        assert account.get_state()["realized_pnl"] == 400
    finally:
        restored._durability.release()


def test_tampered_native_phase_has_zero_financial_effects(binary, tmp_path):
    native = tmp_path/"native"
    run(binary, native, "protected")
    store, lifecycle, _ = financial(tmp_path)
    store.start()
    try:
        before = store.capture_state()
        wire = phases(native)[-1]
        with pytest.raises(ValueError):
            store.apply_phase(b"0"*64 + wire[64:])
        after = store.capture_state()
        before.pop("captured_at"); after.pop("captured_at")
        assert before == after
    finally:
        store._durability.release()
