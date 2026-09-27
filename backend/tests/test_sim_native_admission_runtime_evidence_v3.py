"""Synthetic local snapshots/config only; no production authority or native calls."""
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
import hashlib
import hmac
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from backend.services import sim_native_authority_v3 as auth
from backend.services.sim_native_admission_runtime_evidence_v3 import SimNativeAdmissionRuntimeEvidenceV3
from backend.services.sim_native_commissioning_policy_v1 import load as load_policy
from backend.services.sim_native_dashboard_reader_v3 import BOOLEAN_FIELDS, COMMISSIONING_FILE, RuntimeSchema
from backend.services.sim_admission_envelope_v3 import AuthenticatedAdmissionV3, utc_us
from backend.services.first_controlled_trade_preflight_v3 import FirstControlledTradePreflightV3
from backend.tests.test_sim_native_financial_runtime_service_v3 import environment
from backend.tests.test_controlled_sim_operation_v3 import BINDING, KEY


def disk(root):
    return {str(p): (p.read_bytes(), p.stat().st_mtime_ns) for p in root.rglob("*")
            if p.is_file() and not p.name.endswith(".lock")}


def assert_preflight_rejects(adapter):
    financial = {"execution_domain": "SIM_NATIVE", "backend_account_id": BINDING.backend_account_id,
        "native_account": "Sim101", "provider": "Simulator", "instrument": "NQ DEC26", "runtime_generation": 1,
        "status": "NO_OPERATION", "open_position_count": 0, "closed_position_count": 0,
        "journal_count": 0, "pending_dashboard_events": 0}
    original = deepcopy(financial)
    result = FirstControlledTradePreflightV3(evidence=adapter, read_financial=lambda: financial).get_snapshot()
    assert result["status"] == "NOT_READY" and result["authorization_state"] == "NOT_AUTHORIZED"
    assert financial == original


@pytest.fixture
def evidence_environment(environment):
    root, paths, now, runtime, config = environment
    snapshots = root / "runtime/snapshots"
    snapshots.mkdir()
    commissioning = {"schema": "ARMS_CONTROLLED_COMMISSIONING_V3", "observed_at": now.isoformat(),
        "restore_status": "NO_PERSISTED_OPERATION", "last_configuration_error": "", "reconciliation_fence": False,
        **{k: config[k] for k in ("configuration_generation", "runtime_generation", "authority_id",
                                  "backend_account_id", "native_account", "provider", "instrument")},
        **{k: True for k in BOOLEAN_FIELDS}}
    commissioning.update(native_submit_enabled=False, auto_retry_allowed=False)
    snapshot = {"schema": RuntimeSchema.SCHEMA, "observed_at": now.isoformat(), "account_name": "Sim101",
        "provider": "Simulator", "instrument": "NQ DEC26", "connection_status": "Connected",
        "physical_test_readiness": "PHYSICAL_TEST_READY", "position_state": "FLAT", "active_order_count": 0,
        "native_submit_enabled": False, "auto_retry_allowed": False}
    def write():
        for name, value in ((COMMISSIONING_FILE, commissioning), (RuntimeSchema.FILE_NAME, snapshot)):
            (snapshots / name).write_text(json.dumps(value), encoding="utf-8")
    write()
    adapter = SimNativeAdmissionRuntimeEvidenceV3(runtime=runtime, configuration=config,
        policy=load_policy(), clock=lambda: now)
    return SimpleNamespace(root=root, paths=paths, now=now, runtime=runtime, config=config,
        commissioning=commissioning, snapshot=snapshot, write=write, adapter=adapter)


def sign_config(env, **changes):
    config = {**env.config, **changes}
    wire = auth.canonical(config)
    (env.root / "controlled-v3-config.json").write_bytes(wire)
    (env.root / "controlled-v3-config.sig").write_bytes(hmac.new(KEY, auth.DOMAIN+wire, hashlib.sha256).hexdigest().encode())


def test_exact_evidence_is_deterministic_read_only_and_not_authentication(evidence_environment):
    env = evidence_environment
    before = disk(env.root)
    value = env.adapter()
    BINDING.assert_claims(value)
    assert set(value) == set(BINDING.claims()) | {"account", "provider", "instrument", "runtime_generation",
        "connected", "position_quantity", "active_orders", "sim_runtime_revalidation", "sim_execution_authority",
        "observed_at", "runtime_ref"}
    assert value["observed_at"] == env.snapshot["observed_at"]
    assert value["sim_execution_authority"] == "DISABLED"
    assert len(value["runtime_ref"]) == 64
    assert env.adapter() == value
    value["active_orders"].append("cannot poison next read")
    assert env.adapter()["active_orders"] == []
    assert disk(env.root) == before
    assert all(not list(p.iterdir()) for p in env.paths.values())


@pytest.mark.parametrize("source,field,value", [
    ("snapshot", "account_name", "Sim102"), ("snapshot", "provider", "Live"),
    ("snapshot", "instrument", "MNQ DEC26"), ("snapshot", "connection_status", "Disconnected"),
    ("snapshot", "position_state", "LONG"), ("snapshot", "position_state", "SHORT"),
    ("snapshot", "position_state", "UNKNOWN"), ("snapshot", "active_order_count", 1),
    ("snapshot", "active_order_count", False), ("snapshot", "native_submit_enabled", True),
    ("snapshot", "auto_retry_allowed", True), ("snapshot", "physical_test_readiness", "MARKET_SESSION_CLOSED"),
    ("commissioning", "config_signature_valid", False), ("commissioning", "reconciliation_fence", True),
    ("commissioning", "runtime_generation", "2"), ("commissioning", "configuration_generation", "2"),
    ("commissioning", "authority_id", "b"*64), ("commissioning", "authority_loaded", False),
    ("commissioning", "controlled_v3_configured", False), ("commissioning", "command_path_ready", False),
    ("commissioning", "activation_path_ready", False), ("commissioning", "state_path_ready", False),
    ("commissioning", "reconciliation_path_ready", False), ("commissioning", "auto_retry_allowed", True),
    ("commissioning", "native_submit_enabled", True),
])
def test_negative_runtime_has_no_evidence_or_side_effects(evidence_environment, source, field, value):
    env = evidence_environment
    getattr(env, source)[field] = value; env.write()
    before = disk(env.root)
    view, evidence = env.adapter.inspect()
    assert view["status"] == "NOT_READY" and evidence is None
    if value == "MARKET_SESSION_CLOSED":
        assert view["reason"] == "NOT_READY_SESSION_CLOSED"
    with pytest.raises(RuntimeError, match="ADMISSION_EVIDENCE_UNAVAILABLE"):
        env.adapter()
    assert_preflight_rejects(env.adapter)
    assert disk(env.root) == before


@pytest.mark.parametrize("source", ["snapshot", "commissioning"])
@pytest.mark.parametrize("age,ready", [(15, True), (15.001, False), (-.001, False)])
def test_live_freshness_boundary(evidence_environment, source, age, ready):
    env = evidence_environment
    getattr(env, source)["observed_at"] = (env.now-timedelta(seconds=age)).isoformat(); env.write()
    assert (env.adapter.inspect()[1] is not None) is ready
    if not ready:
        assert_preflight_rejects(env.adapter)


@pytest.mark.parametrize("damage", ["expired", "signature", "risk", "runtime_generation", "configuration_generation", "policy"])
def test_authenticated_configuration_and_policy_fail_closed(evidence_environment, damage, monkeypatch):
    env = evidence_environment
    if damage == "expired": sign_config(env, expires_us=str(int(env.config["issued_us"])+1))
    elif damage == "signature": (env.root / "controlled-v3-config.sig").write_bytes(b"invalid-secret-must-not-leak")
    elif damage == "risk": sign_config(env, risk_version="wrong")
    elif damage == "policy":
        owner = env.runtime.lifecycle.runtime_admission_v2
        monkeypatch.setattr(owner, "settings", replace(owner.settings, maximum_signal_age_seconds=300))
    else: sign_config(env, **{damage: "2"})
    before = disk(env.root)
    view, evidence = env.adapter.inspect()
    assert evidence is None and view["status"] == "NOT_READY"
    assert "invalid-secret" not in json.dumps(view)
    assert_preflight_rejects(env.adapter)
    assert disk(env.root) == before


def test_runtime_reference_changes_with_valid_observation(evidence_environment):
    env = evidence_environment
    initial = env.adapter()["runtime_ref"]
    env.snapshot["observed_at"] = (env.now-timedelta(seconds=1)).isoformat(); env.write()
    assert env.adapter()["runtime_ref"] != initial


def test_slow_authentication_cannot_return_stale_evidence(evidence_environment, monkeypatch):
    env = evidence_environment
    clock = [env.now]
    env.adapter.clock = lambda: clock[0]
    original = auth.verify_config
    def delayed(**kwargs):
        value = original(**kwargs)
        clock[0] += timedelta(seconds=16)
        return value
    monkeypatch.setattr(auth, "verify_config", delayed)
    view, evidence = env.adapter.inspect()
    assert evidence is None and view["reason"] == "HEARTBEAT_STALE"
    assert view["heartbeat_fresh"] is False


def test_isolated_admission_dry_run_preserves_all_execution_blocks(evidence_environment, tmp_path, monkeypatch):
    from backend.tests import runtime_market_fixture_v81 as market
    from backend.tests.test_sim_native_account_authority_v3 import request
    env = evidence_environment
    runtime = env.runtime
    # Fixed weekday fixture, independent of the real machine's closed Sunday session.
    env.now = market.NOW
    issued = env.now-timedelta(seconds=1)
    sign_config(env, issued_us=str(utc_us(issued)), issued_at=issued.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                expires_us=str(utc_us(env.now+timedelta(hours=1))))
    env.config = auth.read_authenticated_config()
    env.snapshot["observed_at"] = env.commissioning["observed_at"] = env.now.isoformat()
    env.write()
    env.adapter = SimNativeAdmissionRuntimeEvidenceV3(runtime=runtime, configuration=env.config,
        policy=load_policy(), clock=lambda: env.now)
    market.publish_test_market(runtime.lifecycle, directory=tmp_path / "market", symbol="NQ", price=10000)
    runtime.lifecycle.native_admission_producer_v3.runtime_evidence = env.adapter
    denied = Mock(side_effect=AssertionError("no execution in admission dry run"))
    for owner, name in ((runtime.lifecycle.execution_manager, "prepare_order"),
                        (runtime.lifecycle.paper_execution_engine, "execute"),
                        (runtime.lifecycle.broker_connector_v2, "submit_order"),
                        (runtime.lifecycle.broker_connector_v2, "cancel_order"),
                        (runtime.lifecycle.broker_connector_v2, "close_position")):
        monkeypatch.setattr(owner, name, denied)
    runtime.store.start()
    try:
        body = request(runtime); body["signal"]["generated_at"] = env.now.isoformat()
        result = runtime.lifecycle.submit_signal(**body)
        assert result["accepted"] is True, result
        assert result["prepared_order"] is result["execution"] is result["position"] is None
        record = json.loads(runtime.store.account_namespace.read_bytes())
        envelope = AuthenticatedAdmissionV3.read(record["native_financial"]["admission_wire"].encode())
        values = envelope.fields()
        producer = runtime.lifecycle.native_admission_producer_v3
        assert producer.authority.verify(envelope, now_us=utc_us(env.now), instrument=BINDING.instrument,
            runtime_generation=1, risk_version=producer.risk_version()) == values
        BINDING.assert_claims(values)
        assert values["quantity"] == "1" and values["runtime_generation"] == "1"
        assert all(values[k+"_approval"] == "APPROVED" for k in ("risk", "probability", "confluence", "news", "market", "rr", "stop"))
        assert runtime.lifecycle.get_active_positions() == [] and runtime.lifecycle.trade_journal_v2.trades == []
        assert all(not list(path.iterdir()) for path in env.paths.values())
        denied.assert_not_called()
    finally:
        runtime.store._durability.release()
