"""0.10A: containment through both URLs; real PAPER and durable side effects."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
from threading import Event, Thread
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.accounts.account_config_manager_v2 import AccountConfigManagerV2
from backend.accounts.account_registry_v1 import AccountRegistryV1
from backend.accounts.funding_firm_profile_v1 import FundingFirmProfile
from backend.api.routers.account_manager_api_v2 import router as manager_router
from backend.api.routers.account_switch_api_v2 import router as legacy_router
from backend.services.account_switch_safety_v2 import AccountSwitchRejected
from backend.services.durable_execution_state_v2 import AccountAdmissionRejected, seal, evidence_path
from backend.services.runtime_context_v2 import build_runtime_context


URLS = ["/api/v2/dashboard/account-manager/switch", "/api/v2/dashboard/account/switch"]
POLICY = {
    "ARMS_MAXIMUM_QUOTE_AGE_SECONDS": "30", "ARMS_MINIMUM_REWARD_RISK_RATIO": "2",
    "ARMS_MINIMUM_STOP_POINTS": "1", "ARMS_MAXIMUM_STOP_POINTS": "100",
    "ARMS_MAXIMUM_SPREAD_POINTS": "5", "ARMS_MINIMUM_ATR_POINTS": "1",
    "ARMS_MINIMUM_A_PLUS_PROBABILITY": ".8", "ARMS_MINIMUM_A_PLUS_CONFLUENCE_SCORE": ".8",
    "ARMS_MAXIMUM_SIGNAL_AGE_SECONDS": "300", "ARMS_MAXIMUM_OPEN_POSITIONS": "1",
}


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    for key, value in POLICY.items():
        monkeypatch.setenv(key, value)
    a = FundingFirmProfile("AUDIT-A", 150000, 9000., 3000., 4500., 15, .5,
                           "PAPER", "TRAILING", True, "TRADING_COMBINE", 15, 150, 4500.)
    profiles = {
        "A": a, "B": replace(a, firm_name="AUDIT-B", account_size=50000,
                             daily_loss_limit=1000., max_drawdown=2000., profit_target=3000.,
                             risk_percent=.25, max_contracts=5, max_mini_contracts=5,
                             max_micro_contracts=50, maximum_loss_limit=2000.),
    }
    config = tmp_path / "accounts.json"
    config.write_text('{"active_account":"A"}\n', encoding="utf-8")
    monkeypatch.setattr(AccountConfigManagerV2, "DEFAULT_CONFIG_PATH", config)
    def registry_init(self):
        self.accounts = deepcopy(profiles)
    monkeypatch.setattr(AccountRegistryV1, "__init__", registry_init)
    context = build_runtime_context()
    safety = context.account_switch_safety_v2
    app = FastAPI()
    app.include_router(manager_router)
    app.include_router(legacy_router)
    app.state.account_config_manager_v2 = safety._managers[0]
    app.state.account_switch_safety_v2 = safety
    app.state.trade_lifecycle_service_v2 = context.trade_lifecycle_service
    result = SimpleNamespace(context=context, safety=safety, config=config,
                             app=app, client=TestClient(app), path=tmp_path / "state.json")
    yield result
    context.execution_state_store._durability.release()


def payload(runtime, profile="B", account_id=None):
    return {"account_id": account_id or runtime.safety.identity.account_id, "profile_name": profile}


def signal():
    return {"approved": True, "status": "READY", "decision": "SEND_SIGNAL",
            "symbol": "MNQ", "timeframe": "5M", "direction": "LONG",
            "entry_price": 10000., "stop_loss": 9995., "take_profit": 10010.,
            "contracts": 1, "probability": .95, "confluence_score": .95,
            "grade": "A+", "blocking_reasons": [], "warnings": [], "summary": "audit PAPER"}


def submit(runtime, profile="A"):
    c = runtime.context
    state = c.account_state_manager_v2.get_state()
    return c.trade_lifecycle_service.submit_signal(
        signal=signal(), order_type="MARKET",
        risk_context={"account_id": runtime.safety.identity.account_id, "profile_name": profile,
                      "account_balance": c.portfolio_manager_v2.get_available_balance(),
                      "risk_percent": .5, "point_value": 2., "daily_pnl": state["daily_pnl"],
                      "total_drawdown": state["drawdown"]})


def close(runtime, price=10010.):
    opened = submit(runtime)
    assert opened["accepted"], opened
    runtime.context.trade_lifecycle_service.update_position(
        position_id=opened["position"]["position_id"], current_price=price)


def state(runtime):
    result = runtime.context.execution_state_store.capture_state()
    result.pop("captured_at")
    return result


@pytest.mark.parametrize("url", URLS)
@pytest.mark.parametrize("scenario", list("ABCDEFGHIJKLM"))
def test_a_to_m_preserve_account_and_zero_switch_side_effects(runtime, monkeypatch, url, scenario):
    c = runtime.context
    if scenario in "BFGM":
        close(runtime)
    if scenario == "C":
        c.account_state_manager_v2.record_daily_pnl(daily_pnl=-3000.)
    if scenario == "D":
        close(runtime, price=7500.)
        c.account_state_manager_v2.record_daily_pnl(daily_pnl=0.)
        assert c.account_state_manager_v2.get_state()["blocking_reasons"] == ["maximum_total_drawdown_reached"]
    if scenario == "E":
        assert submit(runtime)["accepted"]
    if scenario == "M":
        c.startup_coordinator.startup_from(file_path=runtime.path)
    before, config_before = state(runtime), runtime.config.read_bytes()
    disk_before = runtime.path.read_bytes() if runtime.path.exists() else None
    generation = c.execution_state_store._durability.generation
    broker_call = Mock(wraps=c.trade_lifecycle_service.broker_connector_v2.submit_order)
    prepare = Mock(wraps=c.execution_manager.prepare_order)
    monkeypatch.setattr(c.trade_lifecycle_service.broker_connector_v2, "submit_order", broker_call)
    monkeypatch.setattr(c.execution_manager, "prepare_order", prepare)
    writer = Mock(side_effect=AssertionError("Switch must not persist the selector"))
    monkeypatch.setattr(AccountConfigManagerV2, "_save_active_account", writer)
    target = "A" if scenario == "H" else "B"
    for _ in range(3 if scenario == "H" else 1):
        response = runtime.client.post(url, json=payload(runtime, target))
        assert response.status_code == (200 if scenario == "H" else 409), response.text
        assert response.json()["status"] == ("ACCOUNT_UNCHANGED" if scenario == "H" else "ACCOUNT_SWITCH_REJECTED")
        assert response.json()["changed"] is False
    if scenario == "G":
        assert runtime.client.post(url, json=payload(runtime, "A")).json()["status"] == "ACCOUNT_UNCHANGED"
    if scenario == "L":
        rejected = submit(runtime, "B")
        assert rejected["accepted"] is False
        assert rejected["reason"] == "signal_account_mismatch"
    assert state(runtime) == before
    assert runtime.config.read_bytes() == config_before
    assert c.execution_state_store._durability.generation == generation
    assert runtime.app.state.account_config_manager_v2.active_account == "A"
    assert runtime.client.get("/api/v2/dashboard/account-manager").json()["active_account"] == "A"
    assert c.execution_manager.get_contract_limit("MNQ") == 150
    assert c.risk_manager_v2.maximum_daily_loss == 3000
    assert c.risk_manager_v2.maximum_total_drawdown == 4500
    broker_call.assert_not_called()
    prepare.assert_not_called()
    writer.assert_not_called()
    if scenario == "M":
        assert runtime.path.read_bytes() == disk_before
        c.execution_state_store._durability.release()
        restarted = build_runtime_context()
        try:
            report = restarted.startup_coordinator.startup_from(file_path=runtime.path)
            assert report["status"] == "RECOVERED"
            recovered = restarted.execution_state_store.capture_state()
            recovered.pop("captured_at")
            assert recovered == before
            assert restarted.account_switch_safety_v2.identity.profile_name == "A"
        finally:
            restarted.execution_state_store._durability.release()


@pytest.mark.parametrize("source,reason", [
    ("lifecycle", "lifecycle_position_active"), ("portfolio", "portfolio_position_active"),
    ("paper", "paper_position_active"), ("order", "order_pending"),
    ("protection", "protection_active"), ("oco", "oco_active"),
    ("exposure", "exposure_active"), ("pending", "durable_operation_pending"),
    ("depth", "durable_operation_pending"), ("failed", "reconciliation_or_restart_required"),
    ("disk_pending", "reconciliation_pending"), ("evidence_tmp", "reconciliation_pending"),
    ("unknown", "activity_state_unproven"),
])
@pytest.mark.parametrize("url", URLS)
def test_each_activity_source_independently_blocks_even_noop(runtime, monkeypatch, source, reason, url):
    c, safety = runtime.context, runtime.safety
    broker = c.trade_lifecycle_service.broker_connector_v2
    if source == "lifecycle":
        monkeypatch.setattr(c.trade_lifecycle_service, "get_active_positions", lambda: [{"position_id": "A"}])
    elif source == "portfolio":
        monkeypatch.setattr(c.portfolio_manager_v2, "get_open_positions", lambda: [{"position_id": "A"}])
    elif source == "paper":
        monkeypatch.setattr(broker, "get_positions", lambda: [{"status": "OPEN"}])
    elif source == "order":
        monkeypatch.setattr(broker, "get_orders", lambda: [{"status": "PENDING"}])
    elif source == "protection":
        monkeypatch.setattr(c.protective_order_registry, "list_protections", lambda **kw: [{"status": "ACTIVE"}])
    elif source == "oco":
        monkeypatch.setattr(c.oco_manager, "list_groups", lambda **kw: [{"status": "ACTIVE"}])
    elif source == "exposure":
        c.account_state_manager_v2.update_open_risk(open_risk=1.)
    elif source == "pending":
        safety.durability.operation = {"operation_id": "pending"}
    elif source == "depth":
        safety.durability.depth = 1
    elif source == "failed":
        safety.durability.failed = True
    elif source in ("disk_pending", "evidence_tmp"):
        c.startup_coordinator.startup_from(file_path=runtime.path)
        if source == "disk_pending":
            runtime.path.write_text(json.dumps(seal(c.execution_state_store.capture_state(), 2, "PENDING")))
        else:
            evidence_path(runtime.path).with_suffix(".json.tmp").write_text("{")
    elif source == "unknown":
        monkeypatch.setattr(c.trade_lifecycle_service, "get_active_positions", lambda: None)
    original = runtime.config.read_bytes()
    response = runtime.client.post(url, json=payload(runtime, "A"))
    assert response.status_code == 409
    assert response.json()["reason"] == reason
    assert runtime.config.read_bytes() == original
    assert broker._fills == []


@pytest.mark.parametrize("url", URLS)
def test_json_contract_and_operational_identity(runtime, url):
    assert runtime.client.post(url, params={"account_name": "B"}).status_code == 422
    assert runtime.client.post(url, json={"account_name": "B"}).status_code == 422
    assert runtime.client.post(url, json={"profile_name": "A"}).status_code == 422
    assert runtime.client.post(url, json={**payload(runtime), "extra": True}).status_code == 422
    assert runtime.client.post(url, json=payload(runtime, "a")).status_code == 422
    assert runtime.client.post(url, json=payload(runtime, "A", account_id="OTHER-PAPER")).status_code == 409
    context = runtime.client.get("/api/v2/dashboard/account-manager/switch-context")
    assert context.status_code == 200
    assert context.json() == {**payload(runtime, "A"), "cross_account_switch_enabled": False}
    assert runtime.client.post(url, json=payload(runtime, "A")).json()["status"] == "ACCOUNT_UNCHANGED"


def test_missing_coordinator_is_not_legacy_bypass(runtime):
    runtime.app.state.account_switch_safety_v2 = None
    for url in URLS:
        assert runtime.client.post(url, json=payload(runtime)).status_code == 503
    assert json.loads(runtime.config.read_text())["active_account"] == "A"


@pytest.mark.parametrize("drift", ["selector", "disk", "profile", "rules", "broker"])
def test_same_account_requires_proven_identity(runtime, drift):
    c, safety = runtime.context, runtime.safety
    if drift == "selector":
        safety._managers[-1].active_account = "B"
    elif drift == "disk":
        runtime.config.write_text('{"active_account":"B"}')
    elif drift == "profile":
        safety._managers[0].get_active_account().risk_percent = .25
    elif drift == "rules":
        c.risk_manager_v2.maximum_total_drawdown = 9999
    else:
        c.trade_lifecycle_service.broker_connector_v2.account_id = "OTHER-PAPER"
    before = state(runtime)
    original = runtime.config.read_bytes()
    assert runtime.client.post(URLS[0], json=payload(runtime, "A")).status_code == 409
    assert submit(runtime)["accepted"] is False
    assert state(runtime) == before
    assert runtime.config.read_bytes() == original


def test_bound_manager_cannot_bypass_coordinator(runtime):
    before = runtime.config.read_bytes()
    for manager in runtime.safety._managers:
        with pytest.raises(AccountSwitchRejected):
            manager.set_active_account("B")
        assert manager.set_active_account("A").account_size == 150000
    assert runtime.config.read_bytes() == before


@pytest.mark.parametrize("stale", [
    {"profile_name": "B"}, {"account_id": "OTHER-PAPER"},
    {"risk_percent": .25}, {"account_balance": 50000.},
])
def test_stale_b_signal_has_no_fill_after_rejected_switch(runtime, stale):
    assert runtime.client.post(URLS[0], json=payload(runtime)).status_code == 409
    before = state(runtime)
    risk = {"account_balance": 150000., "risk_percent": .5, "point_value": 2.,
            "daily_pnl": 0., "total_drawdown": 0., **stale}
    result = runtime.context.trade_lifecycle_service.submit_signal(
        signal=signal(), order_type="MARKET", risk_context=risk)
    assert result["accepted"] is False
    assert result["prepared_order"] is result["execution"] is None
    assert state(runtime) == before


def test_rejected_switch_does_not_disable_valid_a_trading(runtime):
    assert runtime.client.post(URLS[0], json=payload(runtime)).status_code == 409
    result = submit(runtime)
    assert result["accepted"]
    assert result["execution_risk_gate"]["account"] == "A"


def test_switch_vs_signal_execution_and_other_switch(runtime, monkeypatch):
    entered, release = Event(), Event()
    errors = []
    original = runtime.safety._assert_quiescent
    def paused_check():
        entered.set()
        assert release.wait(5)
        original()
    monkeypatch.setattr(runtime.safety, "_assert_quiescent", paused_check)
    def switch():
        try:
            runtime.safety.switch(**payload(runtime))
        except AccountSwitchRejected as exc:
            errors.append(str(exc))
    worker = Thread(target=switch)
    before = state(runtime)
    worker.start()
    try:
        assert entered.wait(5)
        rejected = submit(runtime)
        assert rejected["reason"] == "account_switch_in_progress"
        with pytest.raises(AccountAdmissionRejected):
            runtime.context.execution_manager.prepare_order(signal=signal(), order_type="MARKET")
        with pytest.raises(AccountAdmissionRejected):
            runtime.context.paper_execution_engine.execute(prepared_order={})
        with pytest.raises(AccountAdmissionRejected):
            runtime.context.trade_lifecycle_service.broker_connector_v2.submit_order(prepared_order={})
        for url in URLS:
            result = runtime.client.post(url, json=payload(runtime))
            assert result.status_code == 409
            assert result.json()["reason"] == "account_switch_in_progress"
    finally:
        release.set()
        worker.join(5)
    assert not worker.is_alive()
    assert errors == ["account_switch_requires_coordinated_transition"]
    assert state(runtime) == before
    assert runtime.safety.durability.account_switch_in_progress is False


def test_switch_vs_durable_persistence_both_directions(runtime, monkeypatch):
    from backend.services import durable_execution_state_v2 as durable_module
    entered, release = Event(), Event()
    original_write = durable_module.atomic_write
    errors = []
    def paused_write(path, value):
        entered.set()
        assert release.wait(5)
        return original_write(path, value)
    monkeypatch.setattr(durable_module, "atomic_write", paused_write)
    def save():
        try:
            runtime.context.execution_state_store.save_to_file(file_path=runtime.path)
        except Exception as exc:
            errors.append(exc)
    worker = Thread(target=save)
    worker.start()
    try:
        assert entered.wait(5)
        result = runtime.client.post(URLS[0], json=payload(runtime))
        assert result.status_code == 409
        assert result.json()["reason"] == "runtime_operation_in_progress"
    finally:
        release.set()
        worker.join(5)
    assert not worker.is_alive()
    assert errors == []
    assert json.loads(runtime.config.read_text())["active_account"] == "A"
    # While switch owns the barrier, a checkpoint cannot enter atomic_write.
    entered.clear()
    checking, finish = Event(), Event()
    original_check = runtime.safety._assert_quiescent
    def paused_check():
        checking.set()
        assert finish.wait(5)
        original_check()
    monkeypatch.setattr(runtime.safety, "_assert_quiescent", paused_check)
    def switch():
        with pytest.raises(AccountSwitchRejected):
            runtime.safety.switch(**payload(runtime))
    switch_worker = Thread(target=switch)
    save_worker = Thread(target=save)
    switch_worker.start()
    try:
        assert checking.wait(5)
        save_worker.start()
        assert not entered.wait(.1)
    finally:
        finish.set()
        switch_worker.join(5)
        save_worker.join(5)
    assert not switch_worker.is_alive() and not save_worker.is_alive()
    assert errors == []
    assert entered.is_set()


@pytest.mark.parametrize("with_context", [False, True])
def test_real_application_wiring_uses_same_coordinator(runtime, with_context, tmp_path):
    from backend.api.app import create_app
    app = create_app(
        runtime_context=runtime.context if with_context else None,
        account_config_manager_v2=AccountConfigManagerV2(),
        risk_event_store_path_v2=tmp_path / "risk.json",
        start_backtesting_background_worker=False,
    )
    client = TestClient(app)
    safety = app.state.account_switch_safety_v2
    assert safety.durability is app.state.trade_lifecycle_service_v2._durability
    assert app.state.execution_manager_v2._durability is safety.durability
    events_before = app.state.dashboard_event_bus_v2.get_event_history()
    for url in URLS:
        assert client.post(url, json=payload(runtime)).status_code == 409
        assert client.post(url, json=payload(runtime, "A")).json()["status"] == "ACCOUNT_UNCHANGED"

    assert app.state.dashboard_event_bus_v2.get_event_history() == events_before


def test_different_profile_identity_is_rejected_even_with_identical_parameters(runtime):
    for manager in runtime.safety._managers:
        manager.registry.accounts["B"] = deepcopy(manager.registry.accounts["A"])
    before = state(runtime)
    for url in URLS:
        result = runtime.client.post(url, json=payload(runtime))
        assert result.status_code == 409
        assert result.json()["reason"] == "account_switch_requires_coordinated_transition"
    assert state(runtime) == before


def test_initial_split_capital_cannot_be_blessed_as_same_account(runtime):
    from backend.config_settings import ArmsSettings
    split = build_runtime_context(settings=ArmsSettings(account_balance=17000.))
    with pytest.raises(AccountSwitchRejected, match="runtime_profile_mismatch"):
        split.account_switch_safety_v2.switch(
            account_id=split.account_switch_safety_v2.identity.account_id, profile_name="A")
    assert split.trade_lifecycle_service.broker_connector_v2.get_fills() == []


def test_switch_is_rejected_while_preexisting_a_signal_executes(runtime, monkeypatch):
    entered, release = Event(), Event()
    results, errors = [], []
    broker = runtime.context.trade_lifecycle_service.broker_connector_v2
    original = broker.submit_order
    def paused_submit(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        return original(*args, **kwargs)
    monkeypatch.setattr(broker, "submit_order", paused_submit)
    def execute():
        try:
            results.append(submit(runtime))
        except Exception as exc:
            errors.append(exc)
    worker = Thread(target=execute)
    worker.start()
    try:
        assert entered.wait(5)
        for url in URLS:
            response = runtime.client.post(url, json=payload(runtime))
            assert response.status_code == 409
            assert response.json()["reason"] == "runtime_operation_in_progress"
        assert broker.get_fills() == []
    finally:
        release.set()
        worker.join(5)
    assert not worker.is_alive() and errors == []
    assert results[0]["accepted"] is True
    assert results[0]["execution_risk_gate"]["account"] == "A"
    assert len(broker.get_fills()) == 1
    assert json.loads(runtime.config.read_text())["active_account"] == "A"


def test_reentrant_switch_cannot_pass_an_inflight_operation_without_disk_durability(runtime):
    before = state(runtime)
    with runtime.safety.durability.mutation():
        with pytest.raises(AccountSwitchRejected, match="durable_operation_pending"):
            runtime.safety.switch(**payload(runtime, "A"))
    assert runtime.safety.durability.active_operations == 0
    assert state(runtime) == before
