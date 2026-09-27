"""Offline tests of production Account-bridge binding with a synthetic SDK."""
from copy import deepcopy
from datetime import datetime, timezone
import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import subprocess

import pytest

from backend.services.sim_native_command_spool_v2 import SimNativeCommandSpoolV2
from backend.services.sim_native_integration_v3 import NativeSimIntegrationV3
from backend.services.sim_native_runtime_v3 import build_native_sim_runtime
from backend.services.sim_admission_envelope_v3 import DOMAIN, canonical
from backend.tests.test_controlled_sim_operation_v3 import ROOT, KEY, BINDING, NOW, CONTEXT, fields, authority
from backend.tests.test_sim_native_account_authority_v3 import runtime, request


@pytest.fixture(scope="module")
def bridge_binary(tmp_path_factory):
    directory = tmp_path_factory.mktemp("native-sdk-recording")
    main = (ROOT / "integrations/ninjatrader/ArmsSimNativeSubmitBridgeV2.cs").read_text()
    # Compile the actual manual recovery methods too, without loading a platform.
    manual = main[main.index("        private void AttemptEmergencyFlatten()"):main.index("        private void ValidateFlatPreflight(")]
    manual += main[main.index("        private void OnNativePositionUpdate("):main.index("        private void OnNativeOrderUpdate(")]
    manual_path = directory / "manual.cs"
    manual_path.write_text("using System; using System.Collections.Generic; using NinjaTrader.Cbi;\n"
        "namespace NinjaTrader.NinjaScript.Indicators { public partial class ArmsSimNativeSubmitBridgeV2 {\n" + manual + "\n}}")
    compiler = Path(os.environ.get("WINDIR", "C:/Windows")) / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"
    binary = directory / "bridge.exe"
    result = subprocess.run([str(compiler), "/nologo", "/langversion:5", "/target:exe", "/out:" + str(binary),
        "/r:System.Core.dll", "/r:System.Web.Extensions.dll", str(manual_path),
        str(ROOT / "integrations/ninjatrader/ControlledSimOperationV3.cs"),
        str(ROOT / "integrations/ninjatrader/ArmsSimNativeSubmitBridgeV2.ControlledV3.cs"),
        str(ROOT / "integrations/ninjatrader/ArmsSimNativeSubmitBridgeV2.ReconciliationV3.cs"),
        str(ROOT / "backend/tests/fixtures/native_bridge_v3_harness.cs")], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    return binary


def artifacts(root, values=None):
    root.mkdir(exist_ok=True)
    for name in ("activation", "state", "receipts"):
        (root / name).mkdir(exist_ok=True)
    (root / "key.bin").write_bytes(KEY)
    (root / "claims.json").write_text(json.dumps(BINDING.claims()))
    values = fields() if values is None else values
    payload = canonical(values)
    digest = hashlib.sha256(payload).hexdigest()
    # Deliberately signed invalid semantics in adversarial consumer cases.
    wire = b"ARMS_SIM_ADMISSION_V3\n" + digest.encode() + b"\n" + hmac.new(KEY, DOMAIN + payload, hashlib.sha256).hexdigest().encode() + b"\n" + payload
    encoded = base64.b64encode(wire).decode()
    command = dict(command="SUBMIT_ORDER", command_id=values["command_id"], operation_id=values["operation_id"],
        client_order_id=values["client_order_id"], payload=dict(schema="ARMS_SIM_COMMAND_V3", admission_wire=encoded))
    SimNativeCommandSpoolV2(root=root / "spool").write_command(command=command)
    activation = dict(schema="ARMS_SIM_ACTIVATION_V3", command_id=values["command_id"], activation_id=values["activation_id"],
        admission_digest=digest, admission_wire=encoded)
    (root / "activation" / (values["command_id"] + ".arm.json")).write_text(json.dumps(activation))
    return root


def run_bridge(binary, root, mode):
    result = subprocess.run([str(binary), str(root), mode], capture_output=True, text=True, timeout=30)
    if mode.startswith(("crash_", "restore_crash_")):
        assert result.returncode == 86, result.stdout + result.stderr
        return
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize("mode", ["disabled", "wrong_account", "wrong_provider", "wrong_instrument", "wrong_backend", "wrong_risk", "expired", "nonflat", "active"])
def test_native_boundary_rejections_have_zero_sdk_calls(bridge_binary, tmp_path, mode):
    result = run_bridge(bridge_binary, artifacts(tmp_path), mode)
    assert result["error"]
    assert result["create"] == result["submit"] == result["cancel"] == result["flatten"] == 0


@pytest.mark.parametrize("field,value", [(g + "_approval", "REJECTED") for g in ("risk", "probability", "confluence", "news", "market", "rr", "stop")] + [
    ("signal_us", "1"), ("quote_us", "1"), ("runtime_us", "1"), ("risk_expires_us", str(NOW)),
    ("stop_price", "101"), ("quantity", "2"), ("runtime_generation", "2")])
def test_signed_invalid_semantics_cannot_create_orders(bridge_binary, tmp_path, field, value):
    values = fields(); values[field] = value
    result = run_bridge(bridge_binary, artifacts(tmp_path, values), "entry")
    assert result["error"] and result["create"] == result["submit"] == 0


@pytest.mark.parametrize("damage", ["missing", "malformed", "consumed", "digest", "command", "signature"])
def test_invalid_activation_or_writer_never_reaches_sdk(bridge_binary, tmp_path, damage):
    artifacts(tmp_path)
    path = tmp_path / "activation/command-id.arm.json"
    if damage == "missing": path.unlink()
    elif damage == "malformed": path.write_text("{")
    elif damage == "consumed": Path(str(path) + ".consumed").write_text("consumed")
    elif damage == "digest":
        value = json.loads(path.read_text()); value["admission_digest"] = "0" * 64; path.write_text(json.dumps(value))
    else:
        path = tmp_path / "spool/commands/command-id.json"; value = json.loads(path.read_text())
        if damage == "command": value["operation_id"] = "wrong"
        else:
            wire = base64.b64decode(value["payload"]["admission_wire"]).replace(b"Sim101", b"Sim102")
            value["payload"]["admission_wire"] = base64.b64encode(wire).decode()
        path.write_text(json.dumps(value))
    result = run_bridge(bridge_binary, tmp_path, "entry")
    assert result["error"] and result["create"] == result["submit"] == 0


@pytest.mark.parametrize("mode", ["protected", "duplicate", "async_callbacks"])
def test_real_bridge_mapping_creates_exact_protection_once(bridge_binary, tmp_path, mode):
    result = run_bridge(bridge_binary, artifacts(tmp_path), mode)
    assert not result["error"], result
    assert result["create"] == 3 and result["submit"] == 2 and result["flatten"] == 0
    entry, stop, target = result["orders"]
    assert (entry["type"], stop["type"], target["type"]) == ("Market", "StopMarket", "Limit")
    assert stop["stop"] == 90 and target["limit"] == 120
    assert stop["oco"] == target["oco"] != "" and stop["action"] == target["action"] == "Sell"
    assert all(o["quantity"] == 1 and len(o["name"]) <= 50 for o in result["orders"])
    calls = (tmp_path / "sdk.calls").read_text().splitlines()
    assert [c.split()[0] for c in calls] == ["CREATE", "SUBMIT", "CREATE", "CREATE", "SUBMIT"]
    assert calls[-1] == "SUBMIT " + stop["name"] + "|" + target["name"]


@pytest.mark.parametrize("mode,recovery", [("recovery", 1), ("recovery_fill", 1), ("adverse", 1), ("cancel_fill", 0),
    ("unresolved", 0), ("stale_flat", 0), ("wrong_recovery_side", 0), ("wrong_recovery_qty", 0), ("unknown", 0), ("spoof_order", 0), ("overfill", 0)])
def test_recovery_never_guesses_exposure_or_calls_flatten(bridge_binary, tmp_path, mode, recovery):
    result = run_bridge(bridge_binary, artifacts(tmp_path), mode)
    assert not result["error"], result
    rows = [o for o in result["orders"] if o["name"].endswith(".R")]
    assert len(rows) == recovery and result["flatten"] == 0
    if rows:
        assert rows[0]["action"] == "Sell" and rows[0]["quantity"] == 1 and rows[0]["type"] == "Market"
    if mode in {"unknown", "spoof_order", "unresolved"}: assert result["status"] == "RECONCILIATION_REQUIRED"


@pytest.mark.parametrize("phase", ["PROTECTION_RECOVERY_REQUIRED", "CANCEL_REQUESTED", "CANCEL_RECONCILING", "POSITION_RECHECKED", "RECOVERY_CREATE_INTENT", "RECOVERY_CREATED", "RECOVERY_SUBMIT_INTENT", "RECOVERY_SUBMIT_RETURNED", "RECOVERY_NATIVE_EVIDENCE"])
def test_recovery_process_crash_never_reuses_consumed_identity(bridge_binary, tmp_path, phase):
    artifacts(tmp_path)
    run_bridge(bridge_binary, tmp_path, "crash_" + phase)
    before = (tmp_path / "sdk.calls").read_bytes()
    result = run_bridge(bridge_binary, tmp_path, "entry")
    assert result["error"] and result["create"] == result["submit"] == 0
    assert (tmp_path / "sdk.calls").read_bytes() == before


@pytest.mark.parametrize("mode,creates,submits", [("recovery_create_failure", 4, 2), ("recovery_submit_failure", 4, 3),
    ("close_during_create", 4, 2), ("exit_during_recovery_create", 4, 2), ("expiry_during_create", 4, 2), ("disabled_recovery", 3, 2), ("duplicate_entry", 4, 3)])
def test_uncertain_or_changed_recovery_never_retries(bridge_binary, tmp_path, mode, creates, submits):
    result = run_bridge(bridge_binary, artifacts(tmp_path), mode)
    assert result["error"] and result["create"] == creates and result["submit"] == submits
    before = (tmp_path / "sdk.calls").read_bytes()
    resumed = run_bridge(bridge_binary, tmp_path, "restore")
    assert resumed["create"] == resumed["submit"] == resumed["cancel"] == resumed["flatten"] == 0
    assert (tmp_path / "sdk.calls").read_bytes() == before


def test_short_recovery_uses_fresh_exposure_opposite_side(bridge_binary, tmp_path):
    values = fields(); values.update(side="SELL", stop_price="110", target_price="80")
    result = run_bridge(bridge_binary, artifacts(tmp_path, values), "short_recovery")
    assert not result["error"], result
    close = [o for o in result["orders"] if o["name"].endswith(".R")]
    assert len(close) == 1 and close[0]["action"] == "BuyToCover"


@pytest.mark.parametrize("mode,expected", [("manual_cancel_fill", 1), ("manual_already_flat", 0), ("manual_lagging_position", 1), ("manual_unsettled_baseline", 0)])
def test_actual_manual_recovery_ignores_precancel_flat_snapshot(bridge_binary, tmp_path, mode, expected):
    result = run_bridge(bridge_binary, artifacts(tmp_path), mode)
    assert result["flatten"] == expected and result["cancel"] == 1


class RecordingBus:
    def __init__(self, store): self.store, self.events = store, []
    def publish(self, **event):
        self.store.receipt()  # No dashboard event before committed finances.
        self.events.append(deepcopy(event))
        return {"published": True}


def integration(runtime, root, native):
    bus = RecordingBus(runtime.store)
    flow = runtime.integration(spool=SimNativeCommandSpoolV2(root=root / "spool"),
        activation_directory=root / "activation", phase_directory=native / "state", receipt_directory=native / "receipts", event_bus=bus)
    return flow, bus


def test_lifecycle_admission_publishes_existing_spool_after_commit(runtime, tmp_path):
    actual, _ = runtime
    flow, _ = integration(actual, tmp_path, tmp_path)
    result = flow.submit_signal(**request(actual))
    assert result["accepted"] is True
    command = flow.spool.read_command(command_id="synthetic-command-1")
    assert command["payload"]["schema"] == "ARMS_SIM_COMMAND_V3"
    assert (tmp_path / "activation/synthetic-command-1.arm.json").exists()
    assert actual.lifecycle.portfolio_manager_v2.get_open_positions() == []


@pytest.mark.parametrize("field,value", [("probability", .1), ("confluence_score", .1), ("blocking_reasons", ["NEWS_BLOCKED"]), ("stop_loss", 10001.)])
def test_rejected_lifecycle_cannot_publish_command_or_activation(runtime, tmp_path, field, value):
    actual, _ = runtime
    flow, _ = integration(actual, tmp_path, tmp_path)
    values = request(actual); values["signal"][field] = value
    result = flow.submit_signal(**values)
    assert result["accepted"] is False
    assert list(flow.spool.commands_dir.iterdir()) == []
    assert list(flow.activation_directory.iterdir()) == []
    assert actual.lifecycle.portfolio_manager_v2.get_open_positions() == []


@pytest.mark.parametrize("mode,pnl", [("recovery_fill", -20), ("target", 400), ("stop", -200), ("cancel_fill", 400)])
def test_actual_bridge_evidence_to_real_financial_owners_once(bridge_binary, tmp_path, mode, pnl):
    native = artifacts(tmp_path / "native")
    result = run_bridge(bridge_binary, native, mode)
    assert not result["error"], result
    actual = build_native_sim_runtime(binding=BINDING, namespace_root=tmp_path / "backend", authority_key=KEY,
        runtime_evidence=lambda: {}, protection_timeout_us=1_000_000, recovery_timeout_us=20_000_000,
        envelope=authority().issue(fields(), **CONTEXT))
    actual.store.start()
    try:
        flow, bus = integration(actual, tmp_path / "backend", native)
        flow.reconcile(); before = actual.lifecycle.portfolio_manager_v2.capture_risk_state()
        flow.reconcile()
        assert actual.lifecycle.portfolio_manager_v2.capture_risk_state() == before
        assert actual.lifecycle.portfolio_manager_v2.account_state_manager_v2.get_state()["realized_pnl"] == pnl
        assert len(actual.lifecycle.trade_journal_v2.trades) == 1
        assert len(actual.lifecycle.portfolio_manager_v2.get_closed_positions()) == 1
        assert len(bus.events) == 2
        assert len({e["payload"]["event_id"] for e in bus.events}) == 2
        restored = run_bridge(bridge_binary, native, "restore_reconciled")
        assert not restored["error"], restored
        assert restored["status"] == "RECOVERY_COMPLETE"
        assert restored["create"] == restored["submit"] == restored["cancel"] == restored["flatten"] == 0
        flow.reconcile()
        assert actual.lifecycle.portfolio_manager_v2.capture_risk_state() == before
    finally: actual.store._durability.release()
    restored_backend = build_native_sim_runtime(binding=BINDING, namespace_root=tmp_path / "backend", authority_key=KEY,
        runtime_evidence=lambda: {}, protection_timeout_us=1_000_000, recovery_timeout_us=20_000_000,
        envelope=authority().issue(fields(), **CONTEXT))
    restored_backend.store.start()
    try:
        flow, bus = integration(restored_backend, tmp_path / "backend", native)
        flow.reconcile()
        assert restored_backend.lifecycle.portfolio_manager_v2.capture_risk_state() == before
        assert len(restored_backend.lifecycle.trade_journal_v2.trades) == 1 and bus.events == []
    finally: restored_backend.store._durability.release()


@pytest.mark.parametrize("phase", ["RECOVERY_FINANCIAL_APPLIED", "RECOVERY_COMPLETE"])
def test_recovery_financial_receipt_and_completion_crash_windows(bridge_binary, tmp_path, phase):
    native = artifacts(tmp_path / "native")
    run_bridge(bridge_binary, native, "recovery_fill")
    actual = build_native_sim_runtime(binding=BINDING, namespace_root=tmp_path / "backend", authority_key=KEY,
        runtime_evidence=lambda: {}, protection_timeout_us=1_000_000, recovery_timeout_us=20_000_000,
        envelope=authority().issue(fields(), **CONTEXT))
    actual.store.start()
    try:
        flow, _ = integration(actual, tmp_path / "backend", native)
        flow.reconcile(); before = actual.lifecycle.portfolio_manager_v2.capture_risk_state()
        calls = (native / "sdk.calls").read_bytes()
        run_bridge(bridge_binary, native, "restore_crash_" + phase)
        result = run_bridge(bridge_binary, native, "restore_reconciled")
        assert not result["error"] and result["status"] == "RECOVERY_COMPLETE"
        assert (native / "sdk.calls").read_bytes() == calls
        flow.reconcile()
        assert actual.lifecycle.portfolio_manager_v2.capture_risk_state() == before
    finally: actual.store._durability.release()


def test_only_existing_bridge_owns_sdk_and_manual_flatten_is_separate():
    binding = (ROOT / "integrations/ninjatrader/ArmsSimNativeSubmitBridgeV2.ControlledV3.cs").read_text()
    model = (ROOT / "integrations/ninjatrader/ControlledSimOperationV3.cs").read_text()
    main = (ROOT / "integrations/ninjatrader/ArmsSimNativeSubmitBridgeV2.cs").read_text()
    assert "account.Flatten(" not in model and ".Flatten(" not in binding
    assert "NATIVE_SUBMIT_ENABLED = false" in main and "AUTO_RETRY_ALLOWED = false" in main
    assert "targetAlreadyFlat" not in main
    assert "QueueControlledExecution(execution)" in main and "ReconcileControlledV3();" in binding
    heartbeat = main[main.index("private void OnRuntimeSnapshotHeartbeat("):main.index("private void AttemptOneShotSubmit(")]
    assert "ReconcileControlledV3();" not in heartbeat and "AdvanceManualEmergencyRecovery();" not in heartbeat


def test_b1_queued_stop_fill_cannot_trigger_later_sibling_submission(bridge_binary, tmp_path):
    result = run_bridge(bridge_binary, artifacts(tmp_path), "b1_stop_fill_during_submit")
    assert not result["error"], result
    snapshot = json.loads((tmp_path / "sdk.snapshot.json").read_text())
    assert snapshot["positions"] == [], "the injected stop execution must close the synthetic exposure"
    assert next(o for o in snapshot["orders"] if o["name"].endswith(".S"))["state"] == "Filled"
    assert result["submit"] == 2, "entry plus one complete protective-pair boundary; no later sibling Submit"


def test_b2_ambiguous_execution_fence_survives_valid_entry_callback(bridge_binary, tmp_path):
    result = run_bridge(bridge_binary, artifacts(tmp_path), "b2_unknown_before_entry")
    assert not result["error"], result
    assert (result["status"], result["create"], result["submit"]) == (
        "RECONCILIATION_REQUIRED", 1, 1
    ), "an established reconciliation fence must prevent both subsequent protection mutations"


def test_b3_terminal_execution_cannot_complete_against_delayed_flat_position(bridge_binary, tmp_path):
    result = run_bridge(bridge_binary, artifacts(tmp_path), "b3_terminal_fill_delayed_position")
    assert result["remaining_quantity"] == 1, "the delayed observation must reveal real synthetic exposure"
    assert result["pending_before_position"] is True, "terminal execution evidence must invalidate stale FLAT completion"
    assert result["pending_after_position"] is True, "the later non-flat observation must leave recovery pending"
    assert result["cancel"] == result["flatten"] == 0


@pytest.mark.parametrize("mode,creates,submits", [("b1_target_fill_during_submit", 3, 2),
    ("b1_already_flat", 1, 1), ("b1_exit_during_create", 2, 1)])
def test_b1_no_later_native_mutation_after_observed_exit(bridge_binary, tmp_path, mode, creates, submits):
    result = run_bridge(bridge_binary, artifacts(tmp_path), mode)
    assert result["create"] == creates and result["submit"] == submits
    assert result["cancel"] == result["flatten"] == 0


@pytest.mark.parametrize("mode", ["b2_fenced_stop", "b2_fenced_target", "b2_fenced_guard"])
def test_b2_fence_survives_exit_and_reordered_callbacks_and_sdk_guard(bridge_binary, tmp_path, mode):
    result = run_bridge(bridge_binary, artifacts(tmp_path), mode)
    assert result["status"] == "RECONCILIATION_REQUIRED"
    assert (result["create"], result["submit"], result["cancel"], result["flatten"]) == (3, 2, 0, 0)
    assert bool(result["error"]) == mode.endswith("guard")
    calls = (tmp_path / "sdk.calls").read_bytes()
    restored = run_bridge(bridge_binary, tmp_path, "restore")
    assert restored["status"] == "RECONCILIATION_REQUIRED"
    assert (tmp_path / "sdk.calls").read_bytes() == calls


@pytest.mark.parametrize("mode", ["no_operator_recovery", "no_operator_disconnect", "stale_flat"])
def test_b3_unproven_position_stays_fenced_across_restart(bridge_binary, tmp_path, mode):
    result = run_bridge(bridge_binary, artifacts(tmp_path), mode)
    assert result["status"] == "RECONCILIATION_REQUIRED"
    assert not any(o["name"].endswith(".R") for o in result["orders"])
    calls = (tmp_path / "sdk.calls").read_bytes()
    for _ in range(2):
        restored = run_bridge(bridge_binary, tmp_path, "restore")
        assert restored["status"] == "RECONCILIATION_REQUIRED"
        assert (tmp_path / "sdk.calls").read_bytes() == calls


@pytest.mark.parametrize("field", ["execution_domain", "backend_account_id", "account", "provider", "instrument",
    "operation_id", "recovery_id", "runtime_generation", "checkpoint_digest", "executions_digest", "evidence_digest",
    "orders_digest", "native_executions_digest", "position_quantity", "position_side", "active_orders", "unresolved_orders", "nonce",
    "expired", "future", "signature", "token", "stale_position", "disconnect", "replay", "new_evidence", "ambiguous"])
def test_operator_reconciliation_rejects_wrong_stale_or_ambiguous_authority(bridge_binary, tmp_path, field):
    result = run_bridge(bridge_binary, artifacts(tmp_path), "permit_" + field)
    assert result["error"], result
    assert result["status"] == "RECONCILIATION_REQUIRED"
    assert (result["create"], result["submit"], result["cancel"], result["flatten"]) == (3, 2, 1, 0)
    assert not any(o["name"].endswith(".R") for o in result["orders"])


def test_operator_quantity_one_permit_is_durable_and_cannot_be_applied_twice(bridge_binary, tmp_path):
    result = run_bridge(bridge_binary, artifacts(tmp_path), "permit_double")
    assert result["error"]
    assert (result["create"], result["submit"], result["flatten"]) == (4, 3, 0)
    assert len(list((tmp_path / "state").glob("operator-reconciliation-*.consumed"))) == 1
    calls = (tmp_path / "sdk.calls").read_bytes()
    restored = run_bridge(bridge_binary, tmp_path, "restore")
    assert restored["status"] == "RECONCILIATION_REQUIRED"
    assert (tmp_path / "sdk.calls").read_bytes() == calls


def test_operator_flat_permit_completes_once_and_restart_does_not_mutate(bridge_binary, tmp_path):
    result = run_bridge(bridge_binary, artifacts(tmp_path), "flat_permit_twice")
    assert result["error"] and result["status"] == "RECOVERY_COMPLETE"
    assert (result["create"], result["submit"], result["cancel"], result["flatten"]) == (1, 1, 0, 0)
    assert len(list((tmp_path / "state").glob("operator-reconciliation-*.consumed"))) == 1
    calls = (tmp_path / "sdk.calls").read_bytes()
    restored = run_bridge(bridge_binary, tmp_path, "restore")
    assert restored["status"] == "RECOVERY_COMPLETE"
    assert (tmp_path / "sdk.calls").read_bytes() == calls


def test_fenced_recovery_execution_cannot_resume_mutation(bridge_binary, tmp_path):
    result = run_bridge(bridge_binary, artifacts(tmp_path), "b2_recovery_callback")
    assert not result["error"] and result["status"] == "RECONCILIATION_REQUIRED"
    assert (result["create"], result["submit"], result["cancel"], result["flatten"]) == (4, 3, 1, 0)
    calls = (tmp_path / "sdk.calls").read_bytes()
    restored = run_bridge(bridge_binary, tmp_path, "restore")
    assert restored["status"] == "RECONCILIATION_REQUIRED"
    assert (tmp_path / "sdk.calls").read_bytes() == calls


def test_fill_discovered_after_operator_flat_completion_restores_fence(bridge_binary, tmp_path):
    result = run_bridge(bridge_binary, artifacts(tmp_path), "flat_permit_late_fill")
    assert not result["error"] and result["status"] == "RECONCILIATION_REQUIRED"
    assert (result["create"], result["submit"], result["cancel"], result["flatten"]) == (1, 1, 0, 0)


@pytest.mark.parametrize("phase", ["RECONCILIATION_PERMIT_CONSUMED", "OPERATOR_RECONCILED"])
def test_operator_permit_crash_does_not_restore_mutation_authority(bridge_binary, tmp_path, phase):
    artifacts(tmp_path)
    run_bridge(bridge_binary, tmp_path, "crash_" + phase)
    calls = (tmp_path / "sdk.calls").read_bytes()
    result = run_bridge(bridge_binary, tmp_path, "entry")
    assert result["error"] and result["create"] == result["submit"] == 0
    assert (tmp_path / "sdk.calls").read_bytes() == calls
    assert len(list((tmp_path / "state").glob("operator-reconciliation-*.consumed"))) == 1


@pytest.mark.parametrize("mode,pending", [("manual_no_permit", True), ("manual_already_flat", False), ("manual_cancel_fill", True)])
def test_manual_reconciliation_and_one_shot_intent_survive_restart(bridge_binary, tmp_path, mode, pending):
    result = run_bridge(bridge_binary, artifacts(tmp_path), mode)
    assert result["manual_pending"] is pending
    calls = (tmp_path / "sdk.calls").read_bytes()
    restored = run_bridge(bridge_binary, tmp_path, "restore_manual")
    assert restored["manual_pending"] is pending
    assert restored["create"] == restored["submit"] == restored["cancel"] == restored["flatten"] == 0
    assert (tmp_path / "sdk.calls").read_bytes() == calls
