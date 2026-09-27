"""Crash/replay of isolated durable projection and authenticated phase batches."""
from copy import deepcopy
import base64
import hashlib
import hmac
import json

import pytest

from backend.services import sim_native_financial_projection_v3 as projection_module
from backend.services.sim_native_integration_v3 import NativeSimIntegrationV3
from backend.services.sim_native_financial_checkpoint_v3 import native_phase
from backend.tests.test_sim_native_financial_runtime_service_v3 import environment, service, seed
from backend.tests.test_sim_native_integration_v3 import bridge_binary, artifacts, run_bridge
from backend.tests.test_controlled_sim_operation_v3 import KEY


def replay(environment, bridge_binary, tmp_path):
    native = artifacts(tmp_path / "bridge")
    assert not run_bridge(bridge_binary, native, "target")["error"]
    seed(environment, native)


@pytest.mark.parametrize("window", ["before_publish", "before_replace", "after_replace_before_ack"])
def test_crash_windows_restore_finances_and_exactly_once_projection(environment, bridge_binary, tmp_path, monkeypatch, window):
    replay(environment, bridge_binary, tmp_path)
    svc = service(environment)
    writer = projection_module.atomic_write
    publish = NativeSimIntegrationV3._publish_dashboard
    def failed_write(path, state):
        if state["events"]:
            if window == "after_replace_before_ack":
                writer(path, state)
            raise OSError("synthetic crash")
        return writer(path, state)
    with monkeypatch.context() as patch:
        if window == "before_publish":
            patch.setattr(NativeSimIntegrationV3, "_publish_dashboard", lambda *a, **k: (_ for _ in ()).throw(OSError("crash")))
        elif window == "before_replace":
            from backend.services import durable_execution_state_v2 as durable
            replace = durable.os.replace
            def fail_before_replace(source, destination):
                if destination.name == "dashboard-projection.json" and json.loads(source.read_bytes())["events"]:
                    raise OSError("synthetic crash after fsync before replace")
                return replace(source, destination)
            patch.setattr(durable.os, "replace", fail_before_replace)
        else:
            patch.setattr(projection_module, "atomic_write", failed_write)
        svc.start()
        assert svc.get_snapshot()["status"] == "UNAVAILABLE"
        state = json.loads(svc._runtime.store.account_namespace.read_bytes())
        assert state["native_financial"]["delivered"] == []
        committed = json.loads(svc._projection.path.read_bytes())
        assert committed["processed_event_count"] == (1 if window == "after_replace_before_ack" else 0)
    svc.stop()
    restored = service(environment)
    restored.start()
    try:
        value = restored.get_snapshot()
        assert value["status"] == "CLOSED", value
        assert value["realized_pnl"] == 400 and value["journal_count"] == 1
        assert value["processed_event_count"] == 2 and value["pending_dashboard_events"] == 0
        assert restored._runtime.store.capture_state()["account_portfolio"] == state["account_portfolio"]
        before = restored._projection.path.read_bytes()
        for event_id, event in restored._runtime.store._native["outbox"].items():
            publish(restored._integration, event_id=event_id, event=event)
        restored.observe()
        assert restored._projection.path.read_bytes() == before
        assert restored.get_snapshot() == value
        assert len(restored._runtime.store._native["delivered"]) == 2
    finally: restored.stop()


@pytest.mark.parametrize("field,value", [("event_id", "bad"), ("backend_account_id", "OTHER"),
    ("execution_domain", "PAPER"), ("order_role", "RECOVERY_CLOSE"), ("position_id", "other"),
    ("entry_price", 1), ("quantity", 2), ("stop_loss", 1)])
def test_poisoned_projection_event_has_no_effect(environment, bridge_binary, tmp_path, monkeypatch, field, value):
    replay(environment, bridge_binary, tmp_path)
    svc = service(environment); svc.start()
    try:
        before = svc._projection.path.read_bytes()
        money = svc._runtime.store.capture_state()["account_portfolio"]
        events = []
        with monkeypatch.context() as patch:
            patch.setattr(svc._projection, "publish", lambda **event: events.append(deepcopy(event)) or {"published": True})
            for event_id, event in svc._runtime.store._native["outbox"].items():
                svc._integration._publish_dashboard(event_id=event_id, event=event)
        entry = next(event for event in events if event["event_type"] == "trade_opened")
        entry["payload"][field] = value
        with pytest.raises(ValueError):
            svc._projection.publish(**entry)
        assert svc._projection.path.read_bytes() == before
        assert svc._runtime.store.capture_state()["account_portfolio"] == money
    finally: svc.stop()


def signed(phase):
    payload = b"".join(k.encode()+b"\t"+base64.b64encode(v.encode())+b"\n" for k,v in sorted(phase.items()))
    return hmac.new(KEY, b"arms.native.phase.v3\0"+payload, hashlib.sha256).hexdigest().encode()+b"\n"+payload


@pytest.mark.parametrize("damage", ["hmac", "admission_digest", "backend_account_id", "provider", "instrument",
    "runtime_generation", "execution_domain", "gap", "price", "exit_without_entry", "second_entry"])
def test_adversarial_batch_has_zero_financial_or_projection_effect(environment, bridge_binary, tmp_path, damage):
    replay(environment, bridge_binary, tmp_path)
    root, paths, _, _, _ = environment
    phases = sorted(paths["state_directory"].glob("*.state"))
    checkpoint = next((root / "runtime/financial").rglob("runtime-state.json"))
    before = json.loads(checkpoint.read_bytes())["account_portfolio"]
    if damage == "gap":
        phases[0].unlink()
    else:
        path = phases[-1]
        wire = path.read_bytes()
        if damage == "hmac":
            path.write_bytes(b"0"*64+wire[64:])
        else:
            state = json.loads(checkpoint.read_bytes())
            phase = native_phase(wire, KEY, state["native_financial"]["admission_digest"])
            if damage in {"price", "exit_without_entry", "second_entry"}:
                entry = next(k for k,v in phase.items() if k.startswith("execution.") and v.startswith("ENTRY|"))
                if damage == "price": phase[entry] = phase[entry].replace("|100|", "|101|")
                elif damage == "exit_without_entry": del phase[entry]
                else: phase["execution.second-entry"] = phase[entry]
            else:
                phase[damage] = "PAPER" if damage == "execution_domain" else "wrong"
            path.write_bytes(signed(phase))
    svc = service(environment); svc.start()
    try:
        assert svc.get_snapshot()["status"] == "UNAVAILABLE"
        after = json.loads(checkpoint.read_bytes())
        assert after["account_portfolio"] == before
        assert after["native_financial"]["executions"] == {}
        assert svc._projection.read()["processed_event_count"] == 0
        assert list(paths["reconciliation_directory"].iterdir()) == []
    finally: svc.stop()


def test_corrupt_projection_fails_closed_and_missing_projection_rebuilds(environment, bridge_binary, tmp_path):
    replay(environment, bridge_binary, tmp_path)
    svc = service(environment); svc.start()
    value = svc.get_snapshot()
    path = svc._projection.path
    original = path.read_bytes()
    svc.stop()
    path.write_bytes(b'{"schema":"wrong"}')
    broken = service(environment); broken.start()
    assert broken.get_snapshot()["status"] == "UNAVAILABLE"
    assert path.read_bytes() == b'{"schema":"wrong"}'
    broken.stop()
    path.unlink()  # Isolated test-only loss simulation, never production repair.
    restored = service(environment); restored.start()
    try:
        assert restored.get_snapshot() == value
        assert path.read_bytes() == original
    finally: restored.stop()


def test_redirected_projection_temporary_file_is_rejected(environment, monkeypatch):
    svc = service(environment)
    original = projection_module.safe_path
    def redirected(path, **options):
        if path.name == "dashboard-projection.json.tmp":
            raise ValueError("synthetic redirected temporary path")
        return original(path, **options)
    monkeypatch.setattr(projection_module, "safe_path", redirected)
    svc.start()
    try:
        assert svc.get_snapshot()["status"] == "UNAVAILABLE"
        assert not svc._projection.path.exists()
    finally: svc.stop()
