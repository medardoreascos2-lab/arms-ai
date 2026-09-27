"""Cross-language contract tests; every native call is a recording double."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import hmac
import json
import os
from pathlib import Path
import subprocess

import pytest

from backend.services.sim_admission_envelope_v3 import (
    DOMAIN, FIELDS, GATES, NativeAdmissionAuthorityV3, canonical,
)
from backend.accounts.sim_native_account_v3 import SimNativeAccountV3

ROOT = Path(__file__).resolve().parents[2]
NOW = 2_000_000_000_000_000
# Synthetic fixture only. Never used as an installation or production key.
KEY = bytes(range(32))
BINDING = SimNativeAccountV3.load(execution_domain="SIM_NATIVE", provider="Simulator", native_account_name="Sim101")


def fields():
    result = {name: name.replace("_", "-") for name in FIELDS}
    result.update(account="Sim101", provider="Simulator", instrument="NQ DEC26",
        runtime_generation="1", side="BUY", quantity="1", operation_id="operation-1",
        client_order_id="operation-1", risk_version="risk-v1", stop_price="90", target_price="120",
        entry_price="100", point_value="20", risk_ceiling="200",
        signal_us=str(NOW-1_000_000), quote_us=str(NOW-1_000_000), runtime_us=str(NOW-1_000_000),
        issued_us=str(NOW), expires_us=str(NOW+1_000_000), risk_expires_us=str(NOW+2_000_000),
        max_signal_age_us="300000000", max_quote_age_us="30000000", max_runtime_age_us="15000000",
        protection_timeout_us="1000000", recovery_timeout_us="20000000")
    result.update({g+"_approval":"APPROVED" for g in GATES})
    result.update(BINDING.claims())
    return result


def authority(guard=lambda: None):
    return NativeAdmissionAuthorityV3(key=KEY, execution_scope_guard=guard, account_binding=BINDING)


CONTEXT = dict(now_us=NOW, instrument="NQ DEC26", runtime_generation=1, risk_version="risk-v1")


@pytest.fixture(scope="module")
def binary(tmp_path_factory):
    target = tmp_path_factory.mktemp("sim-v3-offline") / "harness.exe"
    compiler = Path(os.environ.get("WINDIR", "C:/Windows")) / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"
    result = subprocess.run([str(compiler), "/nologo", "/langversion:5", "/target:exe", "/out:"+str(target),
        "/r:System.Core.dll", "/r:System.Web.Extensions.dll",
        str(ROOT/"integrations/ninjatrader/ControlledSimOperationV3.cs"),
        str(ROOT/"backend/tests/fixtures/controlled_sim_operation_v3_harness.cs")], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout+result.stderr
    return target


def run(binary, tmp_path, mode, values=None, *, corrupt=False):
    tmp_path.mkdir(exist_ok=True)
    (tmp_path/"state").mkdir(exist_ok=True)
    (tmp_path/"key.bin").write_bytes(KEY)
    (tmp_path/"expected.binding.json").write_text(json.dumps(BINDING.claims()), encoding="ascii")
    data = canonical(fields() if values is None else values)
    # Deliberately bypass the producer in malformed-consumer cases: the native
    # reader must reject even a signed record with invalid semantics.
    signature = hmac.new(KEY, DOMAIN+data, hashlib.sha256).hexdigest()
    wire = b"ARMS_SIM_ADMISSION_V3\n"+hashlib.sha256(data).hexdigest().encode()+b"\n"+signature.encode()+b"\n"+data
    if corrupt:
        wire = wire.replace(b"Sim101", b"Sim102")
    (tmp_path/"input.admission").write_bytes(wire)
    result = subprocess.run([str(binary), mode, str(tmp_path)], capture_output=True, text=True, timeout=30)
    if mode.startswith("crash_"):
        assert result.returncode == 86, result.stdout+result.stderr
        return
    assert result.returncode == 0, result.stdout+result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize("mode", ["account", "provider", "instrument", "generation", "risk_version", "nonflat",
    "active_order", "disconnected", "stale_snapshot", "command_id", "command_digest", "activation_id",
    "activation_digest", "missing_activation", "consumed_activation", "disabled"])
def test_native_admission_rejects_before_any_native_call(binary, tmp_path, mode):
    result = run(binary, tmp_path, mode)
    assert result["error"]
    assert (result["create"], result["submit"], result["cancel"], result["flatten"]) == (0,0,0,0)
    assert not (tmp_path/"consumed").exists()


@pytest.mark.parametrize("field,value", [(g+"_approval", "REJECTED") for g in GATES] + [
    ("expires_us", str(NOW)), ("risk_expires_us", str(NOW)), ("signal_us", str(NOW-400_000_000)),
    ("quote_us", str(NOW-40_000_000)), ("runtime_us", str(NOW-20_000_000)),
    ("stop_price", "101"), ("quantity", "2"), ("client_order_id", "wrong"), ("risk_ceiling", "1")])
def test_signed_invalid_admission_still_has_zero_native_calls(binary, tmp_path, field, value):
    data = fields(); data[field] = value
    with pytest.raises(ValueError):
        authority().issue(data, **CONTEXT)
    result = run(binary, tmp_path, "entry_only", data)
    assert result["error"] and result["create"] == result["submit"] == 0


def test_digest_is_not_writer_authority(binary, tmp_path):
    result = run(binary, tmp_path, "entry_only", corrupt=True)
    assert result["error"] and result["create"] == 0
    record = authority().issue(fields(), **CONTEXT)
    with pytest.raises(ValueError):
        NativeAdmissionAuthorityV3(key=b"different-offline-test-key-value-32", execution_scope_guard=lambda: None,
                                  account_binding=BINDING).verify(record, **CONTEXT)


def test_producer_requires_execution_scope_and_does_not_mutate_input(tmp_path):
    before = fields(); original = deepcopy(before)
    def blocked():
        raise RuntimeError("canonical runtime admission required")
    with pytest.raises(RuntimeError):
        authority(blocked).issue(before, **CONTEXT)
    issuer = authority(); record = issuer.issue(before, **CONTEXT)
    destination = issuer.persist(tmp_path, record)
    original_bytes = destination.read_bytes()
    assert issuer.persist(tmp_path, record) == destination
    assert destination.read_bytes() == original_bytes and before == original
    with pytest.raises(ValueError):
        issuer.persist(tmp_path, replace(record, digest="0"*64))


@pytest.mark.parametrize("mode", ["protected", "duplicate", "lagging_partial", "reordered"])
def test_one_fill_one_exact_stop_target_pair(binary, tmp_path, mode):
    result = run(binary, tmp_path, mode)
    assert not result["error"], result
    assert result["create"] == result["submit"] == 3
    entry, stop, target = result["orders"]
    assert stop["role"] == "PROTECTIVE_STOP" and target["role"] == "PROFIT_TARGET"
    assert stop["price"] == 90 and target["price"] == 120
    assert stop["oco"] == target["oco"] and stop["oco"]
    assert stop["action"] == target["action"] == "SELL"
    assert all(o["quantity"] == 1 and o["instrument"] == "NQ DEC26" for o in result["orders"])


@pytest.mark.parametrize("mode", ["entry_rejected", "entry_cancelled", "partial_label"])
def test_order_labels_never_invent_exposure(binary, tmp_path, mode):
    result = run(binary, tmp_path, mode)
    assert result["create"] == result["submit"] == 1 and result["flatten"] == 0


@pytest.mark.parametrize("mode", ["fractional", "overfill", "conflict", "second_execution"])
def test_contradictory_execution_requires_reconciliation(binary, tmp_path, mode):
    result = run(binary, tmp_path, mode)
    assert result["status"] == "RECONCILIATION_REQUIRED"


@pytest.mark.parametrize("mode", ["stop_rejected", "target_rejected"])
def test_protection_rejection_is_explicit(binary, tmp_path, mode):
    assert run(binary, tmp_path, mode)["status"] == "PROTECTION_RECOVERY_REQUIRED"


@pytest.mark.parametrize("mode", ["adverse", "invalid_stop"])
def test_adverse_fill_never_widens_or_replaces_stop(binary, tmp_path, mode):
    result = run(binary, tmp_path, mode)
    assert result["status"] == "ADVERSE_FILL_RECOVERY_REQUIRED"
    assert result["create"] == result["submit"] == 2 and result["flatten"] == 0
    assert result["orders"][-1]["role"] == "RECOVERY_CLOSE"


@pytest.mark.parametrize("mode", ["timeout", "cancel_race", "duplicate_recovery", "already_flat", "recovery_disconnect"])
def test_recovery_is_idempotent_and_waits_for_terminal_evidence(binary, tmp_path, mode):
    result = run(binary, tmp_path, mode)
    assert result["cancel"] == 1
    assert result["flatten"] == 0
    assert result["create"] == result["submit"] == (3 if mode in {"already_flat", "recovery_disconnect", "cancel_race"} else 4)
    if mode == "cancel_race": assert result["status"] == "RECONCILIATION_REQUIRED"
    assert result["status"] != "COMPLETED"  # no financial checkpoint receipt


@pytest.mark.parametrize("mode", ["target_fill", "stop_fill"])
def test_exit_fill_reconciles_sibling_without_directional_order(binary, tmp_path, mode):
    result = run(binary, tmp_path, mode)
    assert result["cancel"] == 1 and result["flatten"] == 0
    assert result["create"] == result["submit"] == 3


@pytest.mark.parametrize("phase", ["CONSUMED", "CREATE_INTENT", "CREATED", "SUBMIT_INTENT", "SUBMIT_RETURNED"])
def test_real_process_exit_never_reuses_activation(binary, tmp_path, phase):
    run(binary, tmp_path, "crash_"+phase)
    result = run(binary, tmp_path, "resume")
    assert result["error"]
    assert result["create"] == (0 if phase in {"CONSUMED", "CREATE_INTENT"} else 1)
    assert result["submit"] == (1 if phase == "SUBMIT_RETURNED" else 0)


def test_production_native_switches_unchanged():
    source = (ROOT/"integrations/ninjatrader/ArmsSimNativeSubmitBridgeV2.cs").read_text()
    assert "private const bool NATIVE_SUBMIT_ENABLED = false;" in source
    assert "private const bool AUTO_RETRY_ALLOWED = false;" in source


@pytest.mark.parametrize("mode,status", [("create_failure", "RECONCILIATION_REQUIRED"),
                                       ("submit_failure", "UNKNOWN_SUBMIT_OUTCOME")])
def test_native_call_exception_persists_uncertainty_and_never_retries(binary, tmp_path, mode, status):
    result = run(binary, tmp_path, mode)
    assert result["error"] and result["status"] == status
    before = (result["create"], result["submit"])
    resumed = run(binary, tmp_path, "resume")
    assert (resumed["create"], resumed["submit"]) == before
    assert resumed["cancel"] == resumed["flatten"] == 0
