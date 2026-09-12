"""0.10B: real PAPER transitions, durable isolation, publication and failure boundaries."""
from copy import deepcopy
import json
from threading import Event, Thread
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.tests.test_account_switch_safety_containment_v2 import (
    runtime as legacy_runtime, signal, URLS,
)
from backend.api.account_runtime_application_v2 import AccountRuntimeApplicationV2
from backend.services.account_runtime_coordinator_v2 import AccountRuntimeCoordinatorV2
from backend.services.account_switch_safety_v2 import AccountSwitchRejected
from backend.services.durable_execution_state_v2 import AccountAdmissionRejected, seal


@pytest.fixture
def hosted(legacy_runtime, tmp_path):
    manager = legacy_runtime.safety._managers[0]
    def make():
        return AccountRuntimeCoordinatorV2(config_path=legacy_runtime.config,
            namespace_root=tmp_path / "accounts", registry=manager.registry)
    coordinator = make()
    app = AccountRuntimeApplicationV2(coordinator)
    with TestClient(app) as client:
        yield SimpleNamespace(c=coordinator, app=app, client=client, make=make,
                              config=legacy_runtime.config)


def target(h, name):
    matches = [key for key, row in h.c._catalog["accounts"].items()
               if row["profile_name"] == name]
    assert len(matches) == 1
    return {"account_id": matches[0], "profile_name": name}


def switch(h, name, url=URLS[0]):
    return h.client.post(url, json=target(h, name))


def snapshot(h):
    value = h.c.published.runtime.execution_state_store.capture_state()
    value.pop("captured_at")
    value.pop("account_identity")
    return value


def trade(h, close_price=None):
    r = h.c.published.runtime
    p = r.account_switch_safety_v2._managers[0].get_active_account()
    state = r.account_state_manager_v2.get_state()
    result = r.trade_lifecycle_service.submit_signal(signal=signal(), order_type="MARKET",
        risk_context={**target(h, h.c.identity.profile_name),
                      "account_balance": r.portfolio_manager_v2.get_available_balance(),
                      "risk_percent": p.risk_percent, "point_value": 2.,
                      "daily_pnl": state["daily_pnl"], "total_drawdown": state["drawdown"]})
    assert result["accepted"], result
    if close_price is not None:
        r.trade_lifecycle_service.update_position(position_id=result["position"]["position_id"],
                                                  current_price=close_price)
    return result


@pytest.mark.parametrize("url", URLS)
@pytest.mark.parametrize("scenario", list("ABCDEFGHIJKLMN"))
def test_scenarios_a_to_n(hosted, scenario, url):
    h = hosted
    a = h.c.published.runtime
    if scenario in "BFGMN":
        trade(h, 10010.)
    a_events = a.trade_lifecycle_service.execution_risk_gate_v1.logger.get_events()
    if scenario in {"C", "G"}:
        a.account_state_manager_v2.record_daily_pnl(daily_pnl=-3000.)
    if scenario == "D":
        trade(h, 7500.)
        a.account_state_manager_v2.record_daily_pnl(daily_pnl=0.)
    if scenario == "E":
        trade(h)
    before = snapshot(h)
    config_before = h.config.read_bytes()
    generation = h.c.published.generation
    if scenario == "H":
        disk = a.execution_state_store._durability.path.read_bytes()
        for _ in range(3):
            result = switch(h, "A", url)
            assert result.status_code == 200, result.text
            assert result.json()["status"] == "ACCOUNT_UNCHANGED"
            assert result.json()["changed"] is False
        assert h.config.read_bytes() == config_before
        assert a.execution_state_store._durability.path.read_bytes() == disk
        assert h.c.published.generation == generation
        assert h.c.published.runtime is a
        assert h.c.phase == "READY"
        assert h.app.state.dashboard_event_bus_v2.get_event_history() == []
        return
    response = switch(h, "B", url)
    if scenario == "E":
        assert response.status_code == 409
        assert snapshot(h) == before
        assert h.config.read_bytes() == config_before
        return
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "ACCOUNT_CHANGED"
    assert h.c.published.generation == generation + 1
    b = h.c.published.runtime
    assert b is not a
    assert b.settings.account_balance == b.portfolio_manager_v2.get_available_balance() == 50000
    assert b.settings.risk_percent == .25
    assert b.risk_manager_v2.maximum_daily_loss == 1000
    assert b.risk_manager_v2.maximum_total_drawdown == 2000
    assert b.execution_manager.get_contract_limit("MNQ") == 50
    assert b.execution_manager.get_contract_limit("NQ") == 5
    assert b.account_state_manager_v2.get_state()["trading_blocked"] is False
    assert b.trade_lifecycle_service.trade_journal_v2.get_trades() == []
    assert b.trade_history_manager.get_history() == []
    assert b.trade_lifecycle_service.broker_connector_v2.get_fills() == []
    assert b.execution_state_store._durability.path.parent.name == target(h, "B")["account_id"]
    assert h.client.get("/api/v2/dashboard/account-manager").json()["active_account"] == "B"
    assert h.app.state.trade_lifecycle_service_v2 is b.trade_lifecycle_service
    assert a.execution_state_store._durability.retired
    with pytest.raises(AccountAdmissionRejected):
        a.execution_manager.prepare_order(signal=signal(), order_type="MARKET")
    if scenario == "A":
        saved = a.execution_state_store.account_namespace.read_bytes()
        denied = a.trade_lifecycle_service.submit_signal(signal=signal(), order_type="MARKET")
        assert denied["accepted"] is False and denied["prepared_order"] is None
        with pytest.raises(AccountAdmissionRejected):
            a.paper_execution_engine.execute(prepared_order={})
        with pytest.raises(AccountAdmissionRejected):
            a.trade_lifecycle_service.broker_connector_v2.submit_order(prepared_order={})
        with pytest.raises(AccountAdmissionRejected):
            a.execution_state_store.save_to_file(file_path=a.execution_state_store.account_namespace)
        assert a.execution_state_store.account_namespace.read_bytes() == saved
    events = h.app.state.dashboard_event_bus_v2.get_event_history()
    assert [e["event_type"] for e in events] == ["ACCOUNT_CHANGED"]
    if scenario == "L":
        result = trade(h)
        assert result["execution_risk_gate"]["account"] == "B"
        assert b.trade_lifecycle_service.broker_connector_v2.account_id == target(h, "B")["account_id"]
    if scenario == "G":
        assert b.trade_lifecycle_service.execution_risk_gate_v1.logger.get_events() == []
        trade(h, 10020.)
        b.account_state_manager_v2.record_daily_pnl(daily_pnl=-123.)
        b_events = b.trade_lifecycle_service.execution_risk_gate_v1.logger.get_events()
        b_before = snapshot(h)
        assert switch(h, "A", url).status_code == 200
        assert snapshot(h) == before
        assert h.c.published.runtime.trade_lifecycle_service.execution_risk_gate_v1.logger.get_events() == a_events
        assert switch(h, "B", url).status_code == 200
        assert snapshot(h) == b_before
        assert h.c.published.runtime.trade_lifecycle_service.execution_risk_gate_v1.logger.get_events() == b_events
    if scenario in "MN":
        b_before = snapshot(h)
        h.c.close()
        restarted = h.make()
        try:
            restarted.start()
            assert restarted.identity.account_id == target(h, "B")["account_id"]
            current = restarted.published.runtime.execution_state_store.capture_state()
            current.pop("captured_at"); current.pop("account_identity")
            assert current == b_before
            assert restarted.switch(**target(h, "A"))["changed"]
            current = restarted.published.runtime.execution_state_store.capture_state()
            current.pop("captured_at"); current.pop("account_identity")
            assert current == before
            restarted.close()
            restarted = h.make()
            restarted.start()
            assert restarted.identity.profile_name == "A"
            current = restarted.published.runtime.execution_state_store.capture_state()
            current.pop("captured_at"); current.pop("account_identity")
            assert current == before
        finally:
            restarted.close()


@pytest.mark.parametrize("corruption", ["other_account", "missing", "profile", "generation"])
def test_o_recovery_rejects_wrong_or_missing_identity(hosted, corruption):
    h = hosted
    foreign = h.c.published.runtime.execution_state_store.capture_state()
    assert switch(h, "B").status_code == 200
    store = h.c.published.runtime.execution_state_store
    if corruption != "other_account":
        foreign = store.capture_state()
        if corruption == "missing":
            foreign.pop("account_identity")
        elif corruption == "profile":
            foreign["account_identity"]["profile_name"] = "A"
        else:
            foreign["account_identity"]["runtime_generation"] = 0
    before = store.capture_state()
    with pytest.raises(ValueError):
        store.validate_state(state=foreign)
    after = store.capture_state()
    after["captured_at"] = before["captured_at"]
    assert after == before
    with pytest.raises(ValueError, match="namespace"):
        store.load_from_file(file_path=h.c.snapshot_path(target(h, "A")["account_id"]))


def test_p_identical_profiles_with_distinct_ids_are_isolated(legacy_runtime, tmp_path):
    registry = legacy_runtime.safety._managers[0].registry
    root = (tmp_path / "isolated").resolve()
    config = legacy_runtime.config
    config.write_text(json.dumps({"version": 2, "active_account": "A",
        "active_account_id": "PAPER-ONE", "runtime_generation": 1, "namespace_root": str(root),
        "accounts": {"PAPER-ONE": {"profile_name": "A"}, "PAPER-TWO": {"profile_name": "A"}}}))
    c = AccountRuntimeCoordinatorV2(config_path=config, namespace_root=root, registry=registry)
    try:
        c.start()
        c.published.runtime.account_state_manager_v2.record_daily_pnl(daily_pnl=-3000.)
        foreign = c.published.runtime.execution_state_store.capture_state()
        assert c.switch(account_id="PAPER-TWO", profile_name="A")["changed"]
        with pytest.raises(ValueError, match="Cross-account"):
            c.published.runtime.execution_state_store.validate_state(state=foreign)
        assert not c.published.runtime.account_state_manager_v2.get_state()["trading_blocked"]
        assert c.switch(account_id="PAPER-ONE", profile_name="A")["changed"]
        assert c.published.runtime.account_state_manager_v2.get_state()["trading_blocked"]
    finally:
        c.close()


@pytest.mark.parametrize("phase", ["BUILD_TARGET", "RECOVER_TARGET", "VALIDATE_TARGET", "BEFORE_PUBLISH", "AFTER_PUBLISH"])
def test_q_r_crash_boundary_recovers_only_committed_account(hosted, monkeypatch, phase):
    h = hosted
    trade(h, 10010.)
    before = snapshot(h)
    def crash(step):
        if step == phase:
            raise SystemExit("simulated process termination")
    monkeypatch.setattr(h.c, "_step", crash)
    with pytest.raises(SystemExit):
        h.c.switch(**target(h, "B"))
    assert not [e for e in h.app.state.dashboard_event_bus_v2.get_event_history()
                if e["event_type"] == "ACCOUNT_CHANGED"]
    h.c.close(checkpoint=False)
    c = h.make()
    try:
        c.start()
        assert c.identity.profile_name == ("B" if phase == "AFTER_PUBLISH" else "A")
        if phase != "AFTER_PUBLISH":
            value = c.published.runtime.execution_state_store.capture_state()
            value.pop("captured_at"); value.pop("account_identity")
            assert value == before
    finally:
        c.close()


def test_s_t_switch_excludes_signals_execution_persistence_and_other_switch(hosted, monkeypatch):
    h = hosted
    source = h.c.published.runtime
    entered, release = Event(), Event()
    result, errors = [], []
    def pause(phase):
        if phase == "BEFORE_PUBLISH":
            entered.set()
            assert release.wait(10)
    monkeypatch.setattr(h.c, "_step", pause)
    def change():
        try:
            result.append(h.c.switch(**target(h, "B")))
        except BaseException as exc:
            errors.append(exc)
    thread = Thread(target=change)
    thread.start()
    try:
        assert entered.wait(10)
        blocked = source.trade_lifecycle_service.submit_signal(signal=signal(), order_type="MARKET")
        assert blocked["accepted"] is False
        assert blocked["prepared_order"] is None
        with pytest.raises(AccountAdmissionRejected):
            source.paper_execution_engine.execute(prepared_order={})
        with pytest.raises(AccountAdmissionRejected):
            source.execution_state_store._durability.checkpoint()
        with pytest.raises(AccountSwitchRejected):
            h.c.switch(**target(h, "B"))
        assert h.client.get("/api/v2/dashboard/account-manager").status_code == 409
    finally:
        release.set(); thread.join(10)
    assert not thread.is_alive() and not errors
    assert result[0]["changed"] and h.c.identity.profile_name == "B"


def test_preexisting_operation_blocks_switch(hosted):
    h = hosted
    before = h.config.read_bytes()
    with h.c.published.runtime.execution_state_store._durability.mutation():
        with pytest.raises(AccountSwitchRejected, match="durable_operation_pending"):
            h.c.switch(**target(h, "B"))
    assert h.config.read_bytes() == before


def test_new_b_rejects_stale_a_signal_before_prepare(hosted, monkeypatch):
    h = hosted
    stale = target(h, "A")
    assert switch(h, "B").status_code == 200
    r = h.c.published.runtime
    def forbidden(**kwargs):
        pytest.fail("A stale signal prepared an order")
    monkeypatch.setattr(r.execution_manager, "prepare_order", forbidden)
    for changes in (stale, {"account_balance": 150000.}, {"risk_percent": .5}):
        risk = {**target(h, "B"), "account_balance": 50000., "risk_percent": .25, **changes}
        value = r.trade_lifecycle_service.submit_signal(signal=signal(), order_type="MARKET",
                                                       risk_context=risk)
        assert value["accepted"] is False and value["prepared_order"] is None
    assert r.trade_lifecycle_service.broker_connector_v2.get_fills() == []


def test_legacy_global_snapshot_is_never_silently_adopted(legacy_runtime, tmp_path):
    path = tmp_path / "global.json"
    path.write_text("{}")
    c = AccountRuntimeCoordinatorV2(config_path=legacy_runtime.config,
        namespace_root=tmp_path / "accounts", registry=legacy_runtime.safety._managers[0].registry,
        legacy_state_path=path)
    original = legacy_runtime.config.read_bytes()
    with pytest.raises(AccountSwitchRejected, match="legacy_snapshot"):
        c.start()
    assert legacy_runtime.config.read_bytes() == original


@pytest.mark.parametrize("phase", [
    "BEFORE_FREEZE", "FREEZE", "AFTER_CHECKPOINT", "BUILD_DURING", "RECOVER_DURING",
    "BEFORE_PUBLISH", "SELECTOR_TEMP", "SELECTOR_TEMP_PARTIAL",
    "SELECTOR_REPLACED", "AFTER_PUBLISH", "READY",
])
def test_real_process_exit_during_publication(hosted, phase):
    import os
    from dataclasses import asdict
    import subprocess
    import sys
    h = hosted
    trade(h, 10010.)
    assert switch(h, "B").status_code == 200
    trade(h, 10030.)
    b_before = snapshot(h)
    assert switch(h, "A").status_code == 200
    before = snapshot(h)
    config, root = str(h.config), str(h.c.root)
    profiles = {key: asdict(row) for key, row in h.c.registry.accounts.items()}
    destination = target(h, "B")
    h.c.close()
    program = """
import json, os, sys
from pathlib import Path
from backend.accounts.account_registry_v1 import AccountRegistryV1
from backend.accounts.funding_firm_profile_v1 import FundingFirmProfile
from backend.services import account_runtime_coordinator_v2 as module
from backend.services.execution_state_store_v2 import ExecutionStateStoreV2
from backend.services.durable_execution_state_v2 import canonical
config, root, profiles, destination, phase = json.loads(sys.argv[1])
registry = AccountRegistryV1()
registry.accounts = {name: FundingFirmProfile(**row) for name, row in profiles.items()}
c = module.AccountRuntimeCoordinatorV2(config_path=config, namespace_root=root, registry=registry)
c.start()
original = module.atomic_write
def write(path, value):
    if Path(path) == Path(config) and phase.startswith("SELECTOR_TEMP"):
        temporary = Path(path).with_suffix(Path(path).suffix + ".tmp")
        with temporary.open("wb") as stream:
            stream.write(b"{" if phase.endswith("PARTIAL") else canonical(value) + b"\\n")
            stream.flush()
            os.fsync(stream.fileno())
        os._exit(73)
    original(path, value)
    if phase == "SELECTOR_REPLACED" and Path(path) == Path(config):
        os._exit(73)
module.atomic_write = write
build = module.build_runtime_context
def build_target(**kwargs):
    runtime = build(**kwargs)
    if phase == "BUILD_DURING":
        os._exit(73)
    return runtime
module.build_runtime_context = build_target
restore = ExecutionStateStoreV2.restore_state
def restore_target(self, **kwargs):
    result = restore(self, **kwargs)
    if phase == "RECOVER_DURING":
        os._exit(73)
    return result
ExecutionStateStoreV2.restore_state = restore_target
def step(name):
    if name == phase or phase == "AFTER_CHECKPOINT" and name == "BUILD_TARGET":
        os._exit(73)
c._step = step
if phase == "BEFORE_FREEZE":
    os._exit(73)
c.switch(**destination)
raise RuntimeError("Crash hook did not execute")
"""
    result = subprocess.run([sys.executable, "-B", "-c", program,
        json.dumps([config, root, profiles, destination, phase])],
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}, capture_output=True, text=True, timeout=30)
    assert result.returncode == 73, result.stderr
    restarted = h.make()
    if phase.startswith("SELECTOR_TEMP"):
        assert json.loads(h.config.read_text())["active_account"] == "A"
        with pytest.raises(AccountSwitchRejected, match="commit_ambiguous"):
            restarted.start()
        assert restarted._published is None
        return
    committed_b = phase in {"SELECTOR_REPLACED", "AFTER_PUBLISH", "READY"}
    try:
        restarted.start()
        assert restarted.identity.profile_name == ("B" if committed_b else "A")
        state = restarted.published.runtime.execution_state_store.capture_state()
        state.pop("captured_at"); state.pop("account_identity")
        assert state == (b_before if committed_b else before)
    finally:
        restarted.close()


@pytest.mark.parametrize("phase", ["BUILD_TARGET", "RECOVER_TARGET", "VALIDATE_TARGET", "BEFORE_PUBLISH"])
def test_failure_before_commit_preserves_a_and_allows_valid_a_signal(hosted, monkeypatch, phase):
    h = hosted
    before, config = snapshot(h), h.config.read_bytes()
    def fail(step):
        if step == phase:
            raise ValueError("injected transition failure")
    monkeypatch.setattr(h.c, "_step", fail)
    result = switch(h, "B")
    assert result.status_code == 409, result.text
    assert h.config.read_bytes() == config
    assert snapshot(h) == before
    assert not h.c.failed and not h.c.switching
    assert h.c.phase == "READY"
    assert trade(h, 10010.)["execution_risk_gate"]["account"] == "A"


def test_error_after_commit_is_uncertain_and_never_reports_unchanged(hosted, monkeypatch):
    h = hosted
    def fail(phase):
        if phase == "AFTER_PUBLISH":
            raise ValueError("HTTP response lost")
    monkeypatch.setattr(h.c, "_step", fail)
    result = switch(h, "B")
    assert result.status_code == 503
    assert result.json()["status"] == "ACCOUNT_TRANSITION_UNCERTAIN"
    assert result.json()["changed"] is None
    assert h.c.failed
    assert h.c.phase == "FAILED"
    assert h.client.get("/v2/positions").status_code == 409
    h.c.close(checkpoint=False)
    restarted = h.make()
    try:
        restarted.start()
        assert restarted.identity.profile_name == "B"
    finally:
        restarted.close()


def test_second_process_catalog_writer_is_rejected(hosted):
    other = hosted.make()
    with pytest.raises(AccountSwitchRejected, match="writer_active"):
        other.start()
    assert hosted.c.identity.profile_name == "A"


def test_signal_via_http_uses_b_risk_sizing_and_paper_identity(hosted):
    h = hosted
    assert switch(h, "B").status_code == 200
    result = h.client.post("/v2/trades/submit", json={"signal": signal(), "order_type": "MARKET",
        "risk_context": {**target(h, "B"), "account_balance": 50000., "risk_percent": .25,
                         "point_value": 2., "daily_pnl": 0., "total_drawdown": 0.}})
    assert result.status_code == 200, result.text
    value = result.json()
    assert value["accepted"], value
    assert value["execution_risk_gate"]["account"] == "B"
    assert value["risk_evaluation"]["risk_amount"] == 125.
    assert value["risk_evaluation"]["maximum_daily_loss"] == 1000.
    assert value["risk_evaluation"]["maximum_total_drawdown"] == 2000.
    assert h.c.published.runtime.trade_lifecycle_service.broker_connector_v2.account_id == target(h, "B")["account_id"]
    assert len(h.client.get("/v2/positions").json()["positions"]) == 1


def test_identity_omission_is_ambiguous_in_coordinated_runtime(hosted):
    h = hosted
    result = h.client.post("/v2/trades/submit", json={"signal": signal(), "order_type": "MARKET"})
    assert result.status_code == 200
    assert result.json()["accepted"] is False
    assert result.json()["reason"] == "signal_account_context_required"
    assert not h.c.published.runtime.trade_lifecycle_service.broker_connector_v2.get_fills()


def test_old_websocket_is_closed_on_new_publication(hosted):
    from starlette.websockets import WebSocketDisconnect
    h = hosted
    with h.client.websocket_connect("/api/v2/dashboard/ws") as socket:
        socket.receive_json()
        assert switch(h, "B").status_code == 200
        with pytest.raises(WebSocketDisconnect) as error:
            # A socket tied to A must reconnect instead of publishing stale A.
            socket.receive_json()
        assert error.value.code == 1012


def test_asgi_default_builds_coordinated_accounts(legacy_runtime, tmp_path):
    from backend.api.asgi import create_asgi_app
    app = create_asgi_app(state_path=tmp_path / "legacy.json",
        account_config_path=legacy_runtime.config,
        account_registry=legacy_runtime.safety._managers[0].registry)
    assert app.coordinator._published is None
    with TestClient(app) as client:
        context = client.get("/api/v2/dashboard/account-manager/switch-context").json()
        destination = next(row for row in context["accounts"] if row["profile_name"] == "B")
        assert client.post(URLS[1], json=destination).json()["changed"] is True
        assert app.state.runtime_context_v2.account_switch_safety_v2.identity.profile_name == "B"
        assert app.state.runtime_state_path_v2.parent.name == destination["account_id"]


@pytest.mark.parametrize("source", ["pending", "protection", "oco", "order", "portfolio", "unknown"])
def test_coordinated_switch_retains_010a_activity_blockers(hosted, monkeypatch, source):
    h = hosted
    r = h.c.published.runtime
    if source == "pending":
        r.execution_state_store._durability.operation = {"operation_id": "pending"}
    elif source == "protection":
        monkeypatch.setattr(r.protective_order_registry, "list_protections", lambda **kw: [{}])
    elif source == "oco":
        monkeypatch.setattr(r.oco_manager, "list_groups", lambda **kw: [{}])
    elif source == "order":
        monkeypatch.setattr(r.trade_lifecycle_service.broker_connector_v2, "get_orders",
                            lambda: [{"status": "PENDING"}])
    elif source == "portfolio":
        monkeypatch.setattr(r.portfolio_manager_v2, "get_open_positions", lambda: [{}])
    else:
        monkeypatch.setattr(r.trade_lifecycle_service, "get_active_positions", lambda: None)
    original = h.config.read_bytes()
    disk = r.execution_state_store._durability.path.read_bytes()
    assert switch(h, "B").status_code == 409
    assert h.config.read_bytes() == original
    assert r.execution_state_store._durability.path.read_bytes() == disk
    # Deliberately corrupted fixtures must not be checkpointed on shutdown.
    h.c.close(checkpoint=False)


@pytest.mark.parametrize("damage", ["corrupt", "pending", "missing_identity", "wrong_profile", "wrong_account"])
def test_target_snapshot_failure_never_publishes_or_inherits_source(hosted, damage):
    h = hosted
    assert switch(h, "B").status_code == 200
    trade(h, 10010.)
    path = h.c.published.runtime.execution_state_store._durability.path
    assert switch(h, "A").status_code == 200
    source, selector = snapshot(h), h.config.read_bytes()
    saved = json.loads(path.read_text())
    if damage == "corrupt":
        path.write_text("{")
    else:
        saved.pop("checksum")
        metadata = saved.pop("durability")
        if damage == "missing_identity":
            saved.pop("account_identity")
        elif damage == "wrong_profile":
            saved["account_identity"]["profile_name"] = "A"
        elif damage == "wrong_account":
            saved["account_identity"]["account_id"] = target(h, "A")["account_id"]
        path.write_text(json.dumps(seal(saved, metadata["generation"],
                                       "PENDING" if damage == "pending" else "COMMITTED")))
    assert switch(h, "B").status_code == 409
    assert snapshot(h) == source
    assert h.config.read_bytes() == selector
    assert h.c.identity.profile_name == "A"


@pytest.mark.parametrize("when", ["before_replace", "after_replace"])
def test_selector_io_failure_is_safe(hosted, monkeypatch, when):
    from backend.services import account_runtime_coordinator_v2 as module
    h = hosted
    before = snapshot(h)
    original = module.atomic_write
    def fail(path, value):
        if path == h.config.resolve():
            if when == "after_replace":
                original(path, value)
            raise OSError("selector write failed")
        return original(path, value)
    monkeypatch.setattr(module, "atomic_write", fail)
    response = switch(h, "B")
    assert response.status_code == (503 if when == "after_replace" else 409)
    if when == "before_replace":
        assert snapshot(h) == before
        assert not h.c.failed
        assert h.c.identity.profile_name == "A"
    else:
        assert h.c.failed
        assert json.loads(h.config.read_text())["active_account"] == "B"
        assert h.client.post("/v2/trades/submit", json={"signal": signal(), "order_type": "MARKET"}).status_code == 409


def test_switch_rejects_while_http_consumer_uses_source(hosted):
    h = hosted
    entered, release = Event(), Event()
    @h.c.published.application.get("/test-account-read")
    def paused_read():
        entered.set()
        assert release.wait(10)
        return {"account": "A"}
    results = []
    thread = Thread(target=lambda: results.append(h.client.get("/test-account-read")))
    thread.start()
    try:
        assert entered.wait(10)
        assert switch(h, "B").status_code == 409
        assert h.c.identity.profile_name == "A"
    finally:
        release.set(); thread.join(10)
    assert not thread.is_alive() and results[0].status_code == 200
    assert switch(h, "B").status_code == 200


def test_restored_b_pnl_is_used_for_new_sizing(hosted):
    h = hosted
    assert switch(h, "B").status_code == 200
    trade(h, 10010.)
    capital = h.c.published.runtime.portfolio_manager_v2.get_available_balance()
    assert capital == 50020.
    assert switch(h, "A").status_code == 200
    assert switch(h, "B").status_code == 200
    result = trade(h)
    assert result["risk_evaluation"]["risk_amount"] == capital * .25 / 100


def test_journal_dashboard_and_pipeline_are_account_scoped(hosted):
    h = hosted
    trade(h, 10010.)
    route = "/api/v3/dashboard/journal-debug"
    before = h.client.get(route).json()
    assert before["total"] == 1
    assert switch(h, "B").status_code == 200
    assert h.client.get(route).json()["total"] == 0
    assert switch(h, "A").status_code == 200
    assert h.client.get(route).json() == before


def test_final_review_published_target_remains_frozen_until_ready(hosted, monkeypatch):
    h = hosted
    observations = []
    original = h.c._step
    def probe(phase):
        original(phase)
        if phase == "AFTER_PUBLISH":
            r = h.c.published.runtime
            result = r.trade_lifecycle_service.submit_signal(
                signal=signal(), order_type="MARKET",
                risk_context={**target(h, "B"), "account_balance": 50000.,
                              "risk_percent": .25, "point_value": 2.,
                              "daily_pnl": 0., "total_drawdown": 0.})
            observations.append(result)
            with pytest.raises(AccountAdmissionRejected):
                r.execution_manager.prepare_order(signal=signal(), order_type="MARKET")
            with pytest.raises(AccountAdmissionRejected):
                r.paper_execution_engine.execute(prepared_order={})
            with pytest.raises(AccountAdmissionRejected):
                r.trade_lifecycle_service.broker_connector_v2.submit_order(prepared_order={})
            with pytest.raises(AccountAdmissionRejected):
                r.execution_state_store._durability.checkpoint()
    monkeypatch.setattr(h.c, "_step", probe)
    assert switch(h, "B").status_code == 200
    assert observations and observations[0]["accepted"] is False
    assert observations[0]["prepared_order"] is None
    assert not h.c.published.runtime.trade_lifecycle_service.broker_connector_v2.get_fills()


def test_final_review_coordinated_recovery_never_synthesizes_legacy_records(hosted):
    h = hosted
    store = h.c.published.runtime.execution_state_store
    value = store.capture_state()
    value.pop("execution_records")
    with pytest.raises(ValueError):
        store.validate_state(state=value)
    path = store.account_namespace
    original = path.read_bytes()
    try:
        path.write_text(json.dumps(value))
        with pytest.raises(ValueError):
            store.load_from_file(file_path=path)
    finally:
        path.write_bytes(original)


def test_final_review_source_checkpoint_failure_keeps_all_admission_closed(hosted, monkeypatch):
    from backend.services import durable_execution_state_v2 as durable
    h = hosted
    r = h.c.published.runtime
    original = durable.atomic_write
    def fail(path, value):
        if path == r.execution_state_store.account_namespace:
            raise OSError("source checkpoint failed")
        return original(path, value)
    monkeypatch.setattr(durable, "atomic_write", fail)
    assert switch(h, "B").status_code == 409
    assert h.c.phase == "FAILED"
    assert h.c.failed
    assert h.client.get("/v2/positions").status_code == 409
    with pytest.raises(AccountAdmissionRejected):
        r.execution_manager.prepare_order(signal=signal(), order_type="MARKET")
    with pytest.raises(AccountAdmissionRejected):
        r.paper_execution_engine.execute(prepared_order={})
    assert not r.trade_lifecycle_service.broker_connector_v2.get_fills()
