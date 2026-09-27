"""Isolated authenticated replay only. Never accesses production DPAPI or spools."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from backend.services import sim_native_authority_v3 as auth
from backend.services.sim_native_commissioning_policy_v1 import load as load_policy
from backend.services.sim_native_runtime_v3 import build_native_sim_runtime
from backend.services.sim_native_financial_runtime_service_v3 import SimNativeFinancialRuntimeServiceV3, admission_not_composed
from backend.services.sim_native_financial_projection_v3 import SimNativeFinancialProjectionV3
from backend.services.sim_admission_envelope_v3 import utc_us
from backend.tests.test_sim_native_integration_v3 import bridge_binary, artifacts, run_bridge
from backend.tests.test_controlled_sim_operation_v3 import KEY, BINDING, fields, authority, CONTEXT


@pytest.fixture
def environment(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.setattr(auth, "load_authority", lambda root=None: KEY)
    root = auth.authority_root()
    root.mkdir(parents=True)
    paths = {field: root / "runtime" / name for field, name in zip(auth.PATH_FIELDS,
        ("commands", "activations", "state", "reconciliation"))}
    for path in paths.values():
        path.mkdir(parents=True)
    policy = load_policy()
    runtime = build_native_sim_runtime(binding=BINDING, namespace_root=root / "runtime/financial", authority_key=KEY,
        runtime_evidence=admission_not_composed, api_settings=policy.api_settings,
        protection_timeout_us=policy.protection_timeout_us, recovery_timeout_us=policy.recovery_timeout_us)
    now = datetime.now(timezone.utc)
    config = auth.publish_config(binding=BINDING, configuration_generation=1, paths=paths,
        risk_version=runtime.lifecycle.native_admission_producer_v3.risk_version(),
        issued_us=utc_us(now)-1_000_000, expires_us=utc_us(now)+3_600_000_000)
    monkeypatch.setattr(auth, "publish_config", Mock(side_effect=AssertionError("no implicit configuration publication")))
    monkeypatch.setattr(auth, "provision_authority", Mock(side_effect=AssertionError("no implicit provisioning")))
    yield root, paths, now, runtime, config


def service(environment):
    return SimNativeFinancialRuntimeServiceV3(clock=lambda: environment[2])


def seed(environment, native):
    root, paths, now, _, _ = environment
    policy = load_policy()
    runtime = build_native_sim_runtime(binding=BINDING, namespace_root=root / "runtime/financial", authority_key=KEY,
        runtime_evidence=admission_not_composed, api_settings=policy.api_settings,
        protection_timeout_us=policy.protection_timeout_us, recovery_timeout_us=policy.recovery_timeout_us,
        envelope=authority().issue(fields(), **CONTEXT))
    runtime.store.start()
    runtime.store._durability.release()
    for path in (native / "state").glob("*.state"):
        (paths["state_directory"] / path.name).write_bytes(path.read_bytes())


def test_no_operation_is_durable_and_get_has_no_side_effects(environment):
    root, paths, _, _, _ = environment
    svc = service(environment)
    svc.start()
    try:
        value = svc.get_snapshot()
        assert value["status"] == "NO_OPERATION", value
        assert value["open_position_count"] == value["journal_count"] == value["realized_pnl"] == 0
        assert value["processed_event_count"] == value["pending_dashboard_events"] == 0
        assert value["backend_account_id"] == BINDING.backend_account_id
        assert svc.cadence_seconds == 2.5
        assert all(not list(path.iterdir()) for path in paths.values())
        before = {str(p): p.read_bytes() for p in root.rglob("*") if p.is_file() and not p.name.endswith(".lock")}
        for _ in range(3):
            assert svc.get_snapshot() == value
        assert before == {str(p): p.read_bytes() for p in root.rglob("*") if p.is_file() and not p.name.endswith(".lock")}
        owner = svc._runtime
        svc.start()
        assert svc._runtime is owner
        with pytest.raises(RuntimeError, match="ADMISSION_NOT_COMPOSED"):
            owner.lifecycle.native_admission_producer_v3.runtime_evidence()
    finally:
        svc.stop(); svc.stop()


@pytest.mark.parametrize("damage", ["expired", "signature", "generation", "path", "risk", "authority"])
def test_bad_production_config_is_unavailable_without_financial_writes(environment, damage, monkeypatch):
    root, _, now, _, _ = environment
    if damage == "authority":
        monkeypatch.setattr(auth, "load_authority", Mock(side_effect=ValueError("unavailable")))
    elif damage == "signature":
        (root / "controlled-v3-config.sig").write_bytes(b"bad")
    elif damage != "expired":
        import hmac, hashlib
        document = json.loads((root / "controlled-v3-config.json").read_bytes())
        document[{"generation": "runtime_generation", "path": "state_directory", "risk": "risk_version"}[damage]] = "wrong"
        wire = auth.canonical(document)
        (root / "controlled-v3-config.json").write_bytes(wire)
        (root / "controlled-v3-config.sig").write_bytes(hmac.new(KEY, auth.DOMAIN+wire, hashlib.sha256).hexdigest().encode())
    svc = SimNativeFinancialRuntimeServiceV3(clock=lambda: now + timedelta(hours=2) if damage == "expired" else now)
    svc.start()
    try:
        assert svc.get_snapshot()["status"] == "UNAVAILABLE"
        assert not (root / "runtime/financial").exists()
    finally: svc.stop()


@pytest.mark.parametrize("mode,role,pnl,opened", [("valid", "ENTRY", 0, 1), ("target", "PROFIT_TARGET", 400, 0),
    ("stop", "PROTECTIVE_STOP", -200, 0), ("recovery_fill", "RECOVERY_CLOSE", -20, 0)])
def test_authenticated_bridge_replay_restart_and_projection_once(environment, bridge_binary, tmp_path, monkeypatch, mode, role, pnl, opened):
    from backend.services.sim_native_integration_v3 import NativeSimIntegrationV3
    import traceback
    failures = []
    reconcile = NativeSimIntegrationV3.reconcile
    def checked(flow):
        try:
            return reconcile(flow)
        except Exception:
            failures.append(traceback.format_exc())
            raise
    monkeypatch.setattr(NativeSimIntegrationV3, "reconcile", checked)
    native = artifacts(tmp_path / "bridge")
    result = run_bridge(bridge_binary, native, mode)
    assert not result["error"], result
    seed(environment, native)
    svc = service(environment)
    svc.start()
    try:
        value = svc.get_snapshot()
        assert value["status"] == ("OPEN" if opened else "CLOSED"), (value, svc._diagnostic.latest, failures)
        assert value["entry_price"] == 100
        assert value["stop_loss"] == 90 and value["take_profit"] == 120
        assert value["direction"] == "LONG" and value["quantity"] == 1
        assert value["order_role"] == role
        assert value["realized_pnl"] == pnl
        assert value["open_position_count"] == opened and value["closed_position_count"] == 1-opened
        assert value["journal_count"] == 1 and value["processed_event_count"] == 2-opened
        trade = svc._runtime.lifecycle.trade_journal_v2.trades[0]
        assert trade.status == ("OPEN" if opened else "CLOSED")
        assert trade.pnl == pnl
        assert value["pending_dashboard_events"] == 0
        state = svc._runtime.store.capture_state()
        assert state["execution_records"]["paper"] is None
        projection = svc._projection.path.read_bytes()
        svc.observe()
        assert svc.get_snapshot() == value
        assert svc._projection.path.read_bytes() == projection
    finally: svc.stop()
    restored = service(environment)
    restored.start()
    try:
        assert restored.get_snapshot() == value
        assert restored._projection.path.read_bytes() == projection
        assert restored._runtime.store.capture_state()["account_portfolio"] == state["account_portfolio"]
        assert len(restored._runtime.lifecycle.trade_journal_v2.trades) == 1
    finally: restored.stop()
    assert svc._runtime.store._durability._lease is None
    assert restored._runtime.store._durability._lease is None


@pytest.mark.parametrize("has_trade", [False, True])
def test_root_lifespan_shared_service_survives_real_paper_switch(environment, tmp_path, monkeypatch, bridge_binary, has_trade):
    from backend.api.asgi import create_asgi_app
    monkeypatch.setenv("ARMS_ADMIN_TOKEN", "isolated-admin")
    config = tmp_path / "paper.json"
    config.write_text('{"active_account":"TOPSTEP_150K"}')
    if has_trade:
        native = artifacts(tmp_path / "bridge")
        assert not run_bridge(bridge_binary, native, "target")["error"]
        seed(environment, native)
    svc = service(environment)
    svc.start = Mock(wraps=svc.start)
    svc.stop = Mock(wraps=svc.stop)
    factory = Mock(return_value=svc)
    app = create_asgi_app(account_config_path=config, state_path=tmp_path / "paper/state.json",
                          sim_native_service_factory=factory)
    factory.assert_not_called()
    url = "/api/v3/dashboard/sim-native-financial"
    with TestClient(app, headers={"X-ARMS-ADMIN-TOKEN": "isolated-admin"}) as client:
        before = client.get(url)
        assert before.json()["status"] == ("CLOSED" if has_trade else "NO_OPERATION")
        owner, journal = svc._runtime, svc._runtime.lifecycle.trade_journal_v2
        projection = svc._projection.path.read_bytes()
        checkpoint = svc._runtime.store.account_namespace.read_bytes()
        for _ in range(3):
            assert client.get(url).json() == before.json()
        assert svc._runtime.store.account_namespace.read_bytes() == checkpoint
        target = next((key, row) for key, row in app.coordinator._catalog["accounts"].items() if row["profile_name"] == "TOPSTEP_50K")
        switched = client.post("/api/v2/dashboard/account-manager/switch", json={"account_id": target[0], **target[1]})
        assert switched.status_code == 200 and switched.json()["changed"] is True, switched.text
        assert client.get(url).json() == before.json()
        assert svc._runtime is owner and svc._runtime.lifecycle.trade_journal_v2 is journal
        assert len(journal.trades) == int(has_trade)
        assert svc._projection.path.read_bytes() == projection
        assert app.coordinator.published.runtime.trade_lifecycle_service.trade_journal_v2.trades == []
        assert client.post(url, json={"command": "SUBMIT"}).status_code == 405
        svc.start.assert_called_once()
    factory.assert_called_once()
    svc.stop.assert_called_once()
    assert owner.store._durability._lease is None


def test_expiry_and_stalled_worker_never_report_ready_or_mutate_on_get(environment):
    svc = service(environment); svc.start()
    try:
        before = svc._runtime.store.account_namespace.read_bytes()
        svc.clock = lambda: environment[2] + timedelta(seconds=3)
        assert svc.get_snapshot()["status"] == "UNAVAILABLE"
        assert svc._runtime.store.account_namespace.read_bytes() == before
        svc.clock = lambda: environment[2] + timedelta(hours=2)
        svc.observe()
        assert svc.get_snapshot()["status"] == "UNAVAILABLE"
        assert svc._runtime.store._durability._lease is None
        assert svc._runtime.store.account_namespace.read_bytes() == before
    finally: svc.stop()


def test_paper_startup_failure_still_releases_native_owner(environment, tmp_path):
    from backend.api.asgi import create_asgi_app
    config = tmp_path / "invalid-paper.json"
    config.write_text("{}")
    svc = service(environment)
    svc.stop = Mock(wraps=svc.stop)
    app = create_asgi_app(account_config_path=config, state_path=tmp_path / "paper.json", sim_native_service_factory=lambda: svc)
    with pytest.raises(Exception):
        with TestClient(app):
            pass
    svc.stop.assert_called_once()
    assert svc._runtime.store._durability._lease is None


def test_invalid_native_configuration_does_not_block_paper(environment, tmp_path):
    from backend.api.asgi import create_asgi_app
    (environment[0] / "controlled-v3-config.sig").write_bytes(b"invalid")
    config = tmp_path / "paper.json"
    config.write_text('{"active_account":"TOPSTEP_150K"}')
    app = create_asgi_app(account_config_path=config, state_path=tmp_path / "paper/state.json",
                          sim_native_service_factory=lambda: service(environment))
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/api/v3/dashboard/sim-native-financial").json()["status"] == "UNAVAILABLE"


def test_second_financial_owner_cannot_replace_running_state(environment):
    first, second = service(environment), service(environment)
    first.start()
    try:
        state = first._runtime.store.account_namespace.read_bytes()
        second.start()
        assert second.get_snapshot()["status"] == "UNAVAILABLE"
        assert first.get_snapshot()["status"] == "NO_OPERATION"
        assert first._runtime.store.account_namespace.read_bytes() == state
        assert first._runtime.store._durability._lease is not None
    finally:
        second.stop(); first.stop()
