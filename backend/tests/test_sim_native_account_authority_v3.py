"""Explicit synthetic fixtures; no NinjaTrader runtime or native transport."""
from copy import deepcopy
from dataclasses import asdict
from datetime import timedelta
import base64
import hashlib
import hmac
import json
from unittest.mock import Mock

import pytest

from backend.accounts.sim_native_account_v3 import SimNativeAccountV3, DEFAULT_BINDING
from backend.services.sim_native_runtime_v3 import build_native_sim_runtime, DisabledNativeSimConnectorV3
from backend.services.sim_admission_envelope_v3 import AuthenticatedAdmissionV3, NativeAdmissionAuthorityV3
from backend.tests.test_controlled_sim_operation_v3 import BINDING, KEY, CONTEXT, authority, fields, binary, run
from backend.tests.runtime_market_fixture_v81 import NOW, publish_test_market


def resolve(**changes):
    document = json.loads(DEFAULT_BINDING.read_text())
    document["accounts"][0].update(changes)
    return SimNativeAccountV3.resolve(document=document, execution_domain="SIM_NATIVE", provider="Simulator", native_account_name="Sim101")


def native_snapshot():
    return {**BINDING.claims(), "account": "Sim101", "provider": "Simulator", "instrument": "NQ DEC26",
            "runtime_generation": "1", "connected": True, "position_quantity": 0, "active_orders": [],
            "sim_runtime_revalidation": "PASS", "sim_execution_authority": "DISABLED",
            "observed_at": NOW.isoformat(), "runtime_ref": "synthetic-runtime-1"}


@pytest.fixture
def runtime(tmp_path):
    snapshot = native_snapshot()
    runtime = build_native_sim_runtime(binding=BINDING, namespace_root=tmp_path, authority_key=KEY,
        runtime_evidence=lambda: deepcopy(snapshot), protection_timeout_us=1_000_000, recovery_timeout_us=20_000_000)
    publish_test_market(runtime.lifecycle, directory=tmp_path/"market", symbol="NQ", price=10000)
    runtime.store.start()
    yield runtime, snapshot
    runtime.store._durability.release()


def request(runtime):
    identity = {"account_id": BINDING.backend_account_id, "profile_name": BINDING.risk_profile_id,
                "runtime_generation": 1, "execution_domain": "SIM_NATIVE"}
    return {"signal": {**identity, "approved": True, "status": "READY", "decision": "SEND_SIGNAL", "grade": "A+",
        "symbol": "NQ", "timeframe": "1m", "direction": "LONG", "contracts": 1, "entry_price": 10000.,
        "stop_loss": 9990., "take_profit": 10020., "probability": .92, "confluence_score": .90,
        "blocking_reasons": [], "generated_at": NOW.isoformat(), "submission_id": "synthetic-signal-1",
        "native_command_id": "synthetic-command-1", "native_activation_id": "synthetic-activation-1"},
        "order_type": "MARKET", "risk_context": {**identity, "account_balance": 150000., "risk_percent": .5,
            "point_value": 20., "daily_pnl": 0., "total_drawdown": 0.}}


def test_unique_explicit_binding_uses_canonical_profile_without_rewriting_it():
    from backend.accounts.account_registry_v1 import AccountRegistryV1
    registry = AccountRegistryV1()
    before = deepcopy(asdict(registry.get_account("TOPSTEP_150K")))
    assert resolve() == BINDING
    assert BINDING.execution_domain == "SIM_NATIVE"
    assert BINDING.backend_account_id.startswith("SIM_NATIVE-")
    assert BINDING.ledger_id == BINDING.journal_account_id == BINDING.backend_account_id
    assert asdict(BINDING.manager().get_active_account()) == before
    assert asdict(registry.get_account("TOPSTEP_150K")) == before
    document = json.loads(DEFAULT_BINDING.read_text())
    document["accounts"].append(deepcopy(document["accounts"][0]))
    with pytest.raises(ValueError):
        SimNativeAccountV3.resolve(document=document, execution_domain="SIM_NATIVE", provider="Simulator", native_account_name="Sim101")


@pytest.mark.parametrize("domain,provider,account", [("PAPER", "Simulator", "Sim101"),
    ("LIVE", "Simulator", "Sim101"), ("SIM_NATIVE", "Other", "Sim101"), ("SIM_NATIVE", "Simulator", "Sim102")])
def test_selection_has_no_fallback(domain, provider, account):
    with pytest.raises(ValueError):
        SimNativeAccountV3.load(execution_domain=domain, provider=provider, native_account_name=account)


@pytest.mark.parametrize("field,value", [("backend_account_id", "PAPER-WRONG"), ("execution_domain", "PAPER"),
    ("execution_domain", "LIVE"), ("account", "Sim102"), ("provider", "Live"), ("risk_profile_id", "TOPSTEP_50K"),
    ("risk_profile_digest", "0"*64), ("instrument_authority_id", "0"*64), ("instrument", "MNQ DEC26"),
    ("runtime_generation", "2"), ("ledger_id", "OTHER"), ("journal_account_id", "OTHER"), ("binding_digest", "0"*64)])
def test_signed_mismatched_envelope_rejects_before_native_calls(binary, tmp_path, field, value):
    values = fields(); values[field] = value
    with pytest.raises(ValueError):
        authority().issue(values, **CONTEXT)
    result = run(binary, tmp_path, "entry_only", values)
    assert result["error"]
    assert result["create"] == result["submit"] == result["cancel"] == result["flatten"] == 0
    assert not (tmp_path/"consumed").exists()


def test_canonical_lifecycle_produces_account_bound_admission_after_gates(runtime, monkeypatch):
    runtime, snapshot = runtime
    denied = Mock(side_effect=AssertionError("admission must not execute or prepare"))
    monkeypatch.setattr(runtime.lifecycle.execution_manager, "prepare_order", denied)
    monkeypatch.setattr(runtime.lifecycle.paper_execution_engine, "execute", denied)
    monkeypatch.setattr(runtime.lifecycle.broker_connector_v2, "submit_order", denied)
    result = runtime.lifecycle.submit_signal(**request(runtime))
    assert result["accepted"] is True, result
    assert result["status"] == "ADMITTED_NATIVE_SUBMIT_DISABLED"
    disk = json.loads(runtime.store.account_namespace.read_text())
    record = AuthenticatedAdmissionV3.read(disk["native_financial"]["admission_wire"].encode())
    values = record.fields()
    BINDING.assert_claims(values)
    assert values["operation_id"] == values["client_order_id"]
    assert values["signal_id"] == "synthetic-signal-1"
    assert values["risk_ceiling"] == "200.0"
    assert disk["durability"]["phase"] == "COMMITTED"
    assert disk["sim_native_account"] == BINDING.claims()
    assert runtime.lifecycle.get_active_positions() == []
    assert runtime.lifecycle.trade_journal_v2.trades == []
    denied.assert_not_called()


@pytest.mark.parametrize("condition", ["probability", "confluence", "news", "market", "rr", "stop", "risk",
    "account", "domain", "generation", "native_provider", "native_account", "native_risk", "native_generation", "native_stale",
    "native_instrument", "nonflat", "active_order", "outside_scope"])
def test_rejections_cannot_issue_admission_or_mutate_financial_state(runtime, tmp_path, condition):
    runtime, snapshot = runtime
    body = request(runtime)
    if condition in {"probability", "confluence"}:
        body["signal"]["probability" if condition == "probability" else "confluence_score"] = .1
    elif condition in {"news", "market"}:
        publish_test_market(runtime.lifecycle, directory=tmp_path/"market", symbol="NQ", price=10000,
                            news_blocked=condition == "news", closed=condition == "market")
    elif condition == "rr": body["signal"]["take_profit"] = 10001.
    elif condition == "stop": body["signal"]["stop_loss"] = 10001.
    elif condition == "risk": body["risk_context"]["risk_percent"] = 1.
    elif condition == "account": body["signal"]["account_id"] = "PAPER-WRONG"
    elif condition == "domain": body["signal"]["execution_domain"] = "LIVE"
    elif condition == "generation": body["signal"]["runtime_generation"] = 2
    elif condition == "native_provider": snapshot["provider"] = "Live"
    elif condition == "native_account": snapshot["account"] = "Sim102"
    elif condition == "native_risk": snapshot["risk_profile_id"] = "TOPSTEP_50K"
    elif condition == "native_generation": snapshot["runtime_generation"] = "2"
    elif condition == "native_instrument": snapshot["instrument"] = "MNQ DEC26"
    elif condition == "native_stale": snapshot["observed_at"] = (NOW-timedelta(seconds=16)).isoformat()
    elif condition == "nonflat": snapshot["position_quantity"] = 1
    elif condition == "active_order": snapshot["active_orders"] = ["foreign"]
    before = runtime.lifecycle.portfolio_manager_v2.capture_risk_state()
    try:
        if condition == "outside_scope":
            runtime.lifecycle.native_admission_producer_v3.produce(signal={}, risk_evaluation={}, execution_risk_gate={}, quote={})
            pytest.fail("outside scope issued admission")
        result = runtime.lifecycle.submit_signal(**body)
        assert result.get("accepted") is not True, result
    except (ValueError, RuntimeError):
        pass
    assert runtime.store.admission_digest == ""
    assert runtime.lifecycle.trade_journal_v2.trades == []
    assert runtime.lifecycle.portfolio_manager_v2.capture_risk_state() == before


def test_native_composition_does_not_change_paper_or_grant_mutation(runtime):
    from backend.tests.test_durable_crash_recovery_v2 import build_runtime
    runtime, _ = runtime
    paper, _, paper_store, _, _ = build_runtime()
    before = paper_store.capture_state()
    assert type(runtime.lifecycle.broker_connector_v2) is DisabledNativeSimConnectorV3
    assert paper.portfolio_manager_v2 is not runtime.lifecycle.portfolio_manager_v2
    assert paper.trade_journal_v2 is not runtime.lifecycle.trade_journal_v2
    for method in (runtime.lifecycle.broker_connector_v2.submit_order, runtime.lifecycle.broker_connector_v2.cancel_order,
                   runtime.lifecycle.broker_connector_v2.close_position, runtime.lifecycle.paper_execution_engine.execute,
                   runtime.lifecycle.execution_manager.prepare_order):
        with pytest.raises(RuntimeError): method()
    after = paper_store.capture_state()
    before.pop("captured_at"); after.pop("captured_at")
    assert before == after


def signed_phase_edit(wire, **changes):
    payload = wire.split(b"\n", 1)[1]
    values = {k.decode(): base64.b64decode(v).decode() for k,v in (line.split(b"\t") for line in payload.splitlines())}
    values.update(changes)
    data = b"".join(k.encode()+b"\t"+base64.b64encode(v.encode())+b"\n" for k,v in sorted(values.items()))
    return hmac.new(KEY, b"arms.native.phase.v3\0"+data, hashlib.sha256).hexdigest().encode()+b"\n"+data


def financial_runtime(root, binding=BINDING):
    values = fields(); values.update(binding.claims(), runtime_generation=str(binding.runtime_generation))
    issuer = NativeAdmissionAuthorityV3(key=KEY, account_binding=binding, execution_scope_guard=lambda: None)
    record = issuer.issue(values, **{**CONTEXT, "runtime_generation": binding.runtime_generation})
    return build_native_sim_runtime(binding=binding, namespace_root=root, authority_key=KEY,
        runtime_evidence=lambda: {}, protection_timeout_us=1_000_000, recovery_timeout_us=20_000_000, envelope=record)


@pytest.mark.parametrize("field,value", [("backend_account_id", "PAPER-WRONG"), ("execution_domain", "PAPER"),
    ("execution_domain", "LIVE"), ("account", "Sim102"), ("provider", "Other"), ("instrument", "MNQ DEC26"),
    ("risk_profile_id", "TOPSTEP_50K"), ("runtime_generation", "2"), ("operation_id", "different-operation"),
    ("order_id.ENTRY", "different-native-order")])
def test_even_authenticated_wrong_account_facts_never_apply(binary, tmp_path, field, value):
    run(binary, tmp_path/"native", "protected")
    wire = sorted((tmp_path/"native/state").glob("*.state"))[-1].read_bytes()
    runtime = financial_runtime(tmp_path)
    runtime.store.start()
    try:
        before = runtime.lifecycle.portfolio_manager_v2.capture_risk_state()
        with pytest.raises(ValueError):
            runtime.store.apply_phase(signed_phase_edit(wire, **{field:value}))
        assert runtime.lifecycle.portfolio_manager_v2.capture_risk_state() == before
        assert runtime.lifecycle.trade_journal_v2.trades == []
        assert runtime.store._native["executions"] == {}
    finally:
        runtime.store._durability.release()


@pytest.mark.parametrize("change", ["account", "profile", "generation"])
def test_checkpoint_and_native_execution_replay_are_account_scoped(binary, tmp_path, change):
    run(binary, tmp_path/"native", "target_fill")
    wire = sorted((tmp_path/"native/state").glob("*.state"))[-1].read_bytes()
    source = financial_runtime(tmp_path/"source")
    source.store.start()
    try:
        source.store.apply_phase(wire)
        snapshot = source.store.capture_state()
        scope = BINDING.claims()
        assert all(p["backend_account_id"] == BINDING.backend_account_id
                   for p in source.lifecycle.portfolio_manager_v2.get_closed_positions())
        assert source.lifecycle.trade_journal_v2.sim_native_account_binding is BINDING
        assert snapshot["sim_native_account"] == scope
        assert source.lifecycle.trade_journal_v2.trades[0].trade_id == "journal-native-" + source.store.admission_digest
    finally:
        source.store._durability.release()
    if change == "account":
        other = "SIM_NATIVE-" + "A"*32
        binding = resolve(backend_account_id=other, ledger_id=other, journal_account_id=other)
    elif change == "profile": binding = resolve(risk_profile_id="TOPSTEP_50K")
    else: binding = resolve(runtime_generation=2)
    target = financial_runtime(tmp_path/"target", binding)
    target.store.start()
    try:
        before = target.lifecycle.portfolio_manager_v2.capture_risk_state()
        with pytest.raises(ValueError): target.store.restore_state(state=snapshot)
        with pytest.raises(ValueError): target.store.apply_phase(wire)
        assert target.lifecycle.portfolio_manager_v2.capture_risk_state() == before
        assert target.lifecycle.trade_journal_v2.trades == []
    finally:
        target.store._durability.release()
    from backend.tests.test_durable_crash_recovery_v2 import build_runtime
    paper, _, paper_store, _, _ = build_runtime()
    with pytest.raises(ValueError): paper_store.validate_state(state=snapshot)
    assert paper.portfolio_manager_v2.get_open_positions() == []
    assert paper.trade_journal_v2.trades == []


@pytest.mark.parametrize("owner", ["journal", "portfolio", "connector"])
def test_replaced_paper_participant_is_rejected_before_writes(binary, tmp_path, owner):
    from backend.tests.test_durable_crash_recovery_v2 import build_runtime
    run(binary, tmp_path/"native", "protected")
    wire = sorted((tmp_path/"native/state").glob("*.state"))[-1].read_bytes()
    runtime = financial_runtime(tmp_path)
    runtime.store.start()
    paper, _, paper_store, _, _ = build_runtime()
    attribute = {"journal":"trade_journal_v2", "portfolio":"portfolio_manager_v2", "connector":"broker_connector_v2"}[owner]
    setattr(runtime.lifecycle, attribute, getattr(paper, attribute))
    before = paper_store.capture_state()
    try:
        with pytest.raises(ValueError): runtime.store.apply_phase(wire)
        after = paper_store.capture_state()
        before.pop("captured_at"); after.pop("captured_at")
        assert after == before
    finally:
        runtime.store._durability.release()


@pytest.mark.parametrize("owner,field", [("risk_manager_v2", "maximum_total_drawdown"),
    ("exposure_manager_v2", "maximum_symbol_open_risk"), ("portfolio_risk_engine_v2", "maximum_total_open_risk"),
    ("order_validation_engine_v2", "minimum_reward_risk_ratio")])
def test_changed_risk_rules_cannot_reuse_bound_profile(runtime, owner, field):
    runtime, _ = runtime
    setattr(getattr(runtime.lifecycle, owner), field, 999999.)
    result = runtime.lifecycle.submit_signal(**request(runtime))
    assert result["accepted"] is False
    assert runtime.store.admission_digest == ""
    assert runtime.lifecycle.trade_journal_v2.trades == []
