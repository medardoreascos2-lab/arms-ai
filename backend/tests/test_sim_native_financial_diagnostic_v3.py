"""Offline failure evidence; all authorities, phases and paths are synthetic."""
from contextlib import contextmanager
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import random
import stat

import pytest

from backend.services import durable_execution_state_v2 as durable
from backend.services import execution_state_store_v2 as state_module
from backend.services import sim_native_financial_runtime_service_v3 as service_module
from backend.services import sim_native_financial_projection_v3 as projection_module
from backend.services.sim_native_financial_checkpoint_v3 import NativeSimFinancialCheckpointV3
from backend.services.sim_native_financial_diagnostic_v3 import SCHEMA, STAGES, SimNativeFinancialDiagnosticV3, stage
from backend.services.sim_native_integration_v3 import NativeSimIntegrationV3
from backend.tests.test_sim_native_financial_runtime_service_v3 import environment, service, seed
from backend.tests.test_sim_native_integration_v3 import bridge_binary, artifacts, run_bridge


def prepare(environment, bridge_binary, tmp_path):
    native = artifacts(tmp_path / "bridge")
    assert not run_bridge(bridge_binary, native, "valid")["error"]
    seed(environment, native)
    return next((environment[0] / "runtime/financial").rglob("runtime-state.json"))


def diagnostic_path(environment):
    return environment[0] / "diagnostics/financial-latest-failure.json"


def assert_failure(svc, environment, expected):
    assert svc.get_snapshot()["status"] == "UNAVAILABLE"
    value = json.loads(diagnostic_path(environment).read_bytes())
    assert value == svc._diagnostic.latest
    assert value["schema"] == SCHEMA
    assert value["stage"] == expected
    assert value["error_code"] == expected + "_FAILED"
    assert value["status"] == "UNAVAILABLE"
    assert svc._diagnostic.write_status == "WRITTEN"
    assert "SECRET" not in json.dumps(value)
    assert str(environment[0]) not in json.dumps(value)
    if svc._runtime:
        assert svc._runtime.store._durability._lease is None
    return value


def assert_open_once(svc):
    value = svc.get_snapshot()
    assert value["status"] == "OPEN", (value, svc._diagnostic.latest)
    assert value["journal_count"] == value["open_position_count"] == value["processed_event_count"] == 1
    assert value["realized_pnl"] == value["closed_position_count"] == value["pending_dashboard_events"] == 0
    state = svc._runtime.store.capture_state()
    assert state["execution_records"]["paper"] is None
    assert len(state["native_financial"]["executions"]) == len(state["native_financial"]["delivered"]) == 1
    return state["account_portfolio"]


def fail(*args, **kwargs):
    raise OSError("SECRET private user path and arbitrary sensitive exception data")


FAULTS = [
    ("checkpoint_open", "CHECKPOINT_OPEN"), ("checkpoint_verify", "CHECKPOINT_VERIFY"),
    ("checkpoint_restore", "CHECKPOINT_RESTORE"), ("phase_enumeration", "PHASE_DISCOVERY"),
    ("phase_read", "PHASE_READ"), ("phase_hmac", "PHASE_VERIFY"), ("phase_apply", "PHASE_APPLY"),
    ("checkpoint_commit", "CHECKPOINT_COMMIT"), ("receipt", "RECEIPT_WRITE"),
    ("projection_replace", "PROJECTION_APPLY"), ("delivery_ack", "OUTBOX_DELIVERY")]


@pytest.mark.parametrize("fault,expected", FAULTS)
def test_injected_boundary_is_durable_sanitized_and_restart_is_deterministic(
        environment, bridge_binary, tmp_path, monkeypatch, fault, expected):
    checkpoint = prepare(environment, bridge_binary, tmp_path)
    baseline = json.loads(checkpoint.read_bytes())["account_portfolio"]
    svc = service(environment)
    original_open, original_glob, replace = Path.open, Path.glob, os.replace
    with monkeypatch.context() as patch:
        if fault == "checkpoint_open":
            def opened(path, *a, **k):
                if path == checkpoint and (a[0] if a else k.get("mode", "r")) == "r": fail()
                return original_open(path, *a, **k)
            patch.setattr(Path, "open", opened)
        elif fault == "checkpoint_verify": patch.setattr(state_module, "verify", fail)
        elif fault == "checkpoint_restore": patch.setattr(NativeSimFinancialCheckpointV3, "restore_state", fail)
        elif fault == "phase_enumeration":
            def glob(path, *a, **k):
                if path == environment[1]["state_directory"]: fail()
                return original_glob(path, *a, **k)
            patch.setattr(Path, "glob", glob)
        elif fault == "phase_read":
            def opened(path, *a, **k):
                if path.suffix == ".state": fail()
                return original_open(path, *a, **k)
            patch.setattr(Path, "open", opened)
        elif fault == "phase_hmac": patch.setattr(service_module, "native_phase", fail)
        elif fault == "phase_apply": patch.setattr(NativeSimFinancialCheckpointV3, "apply_phase", fail)
        elif fault == "receipt": patch.setattr(NativeSimIntegrationV3, "_create", fail)
        elif fault in {"checkpoint_commit", "projection_replace"}:
            def replacement(source, destination):
                if ((fault == "projection_replace" and destination.name == "dashboard-projection.json"
                     and json.loads(source.read_bytes())["events"]) or
                    (fault == "checkpoint_commit" and destination == checkpoint
                     and json.loads(source.read_bytes())["durability"]["phase"] == "COMMITTED"
                     and json.loads(source.read_bytes())["native_financial"]["executions"])): fail()
                return replace(source, destination)
            patch.setattr(os, "replace", replacement)
        else:
            publish = projection_module.SimNativeFinancialProjectionV3.publish
            def unacknowledged(self, **event):
                publish(self, **event)
                return {"published": False}
            patch.setattr(projection_module.SimNativeFinancialProjectionV3, "publish", unacknowledged)
        svc.start()
        evidence = assert_failure(svc, environment, expected)
    disk = json.loads(checkpoint.read_bytes())
    assert len(disk["native_financial"]["executions"]) <= 1
    if fault not in {"projection_replace", "delivery_ack"}:
        assert disk["account_portfolio"] == baseline
    else:
        assert len(disk["account_portfolio"]["open_positions"]) == 1
    assert len(svc._runtime.lifecycle.trade_journal_v2.trades) <= 1
    svc.stop()
    for _ in range(2):
        restored = service(environment); restored.start()
        try:
            if fault == "checkpoint_commit":
                # PENDING / leftover checkpoint temporary file is never repaired
                # by diagnostics: explicit reconciliation remains mandatory.
                assert_failure(restored, environment, "CHECKPOINT_START")
                assert json.loads(checkpoint.read_bytes()) == disk
            else:
                assert_open_once(restored)
                assert json.loads(diagnostic_path(environment).read_bytes()) == evidence
        finally: restored.stop()


@pytest.mark.parametrize("boundary,expected", [("authority", "AUTHORITY_LOAD"), ("config", "CONFIG_VERIFY"),
    ("build", "RUNTIME_BUILD"), ("capture", "SERVICE_PUBLISH")])
def test_startup_and_publication_failures(environment, monkeypatch, boundary, expected):
    target, name = {"authority": (service_module.authority, "load_authority"),
        "config": (service_module.authority, "read_authenticated_config"),
        "build": (service_module, "build_native_sim_runtime"),
        "capture": (service_module.SimNativeFinancialRuntimeServiceV3, "_capture")}[boundary]
    monkeypatch.setattr(target, name, fail)
    svc = service(environment); svc.start()
    assert_failure(svc, environment, expected)
    svc.stop()


@pytest.mark.parametrize("failure", ["replace", "collision", "redirected"])
def test_diagnostic_storage_failure_never_masks_failure_or_erases_previous(environment, monkeypatch, failure):
    observer = SimNativeFinancialDiagnosticV3()
    observer.record(ValueError("SECRET"))
    path = diagnostic_path(environment)
    previous = path.read_bytes()
    with monkeypatch.context() as patch:
        if failure == "replace": patch.setattr(os, "replace", fail)
        elif failure == "collision": path.with_suffix(".json.tmp").write_bytes(b"prior evidence")
        else: patch.setattr(service_module.authority, "safe_path", fail)
        patch.setattr(service_module.authority, "load_authority", fail)
        svc = service(environment); svc.start()
        assert svc.get_snapshot()["status"] == "UNAVAILABLE"
        assert svc._diagnostic.write_status == "FAILED"
        assert svc._diagnostic.latest["status"] == "UNAVAILABLE"
        assert path.read_bytes() == previous
        svc.stop()
    if failure == "collision": assert path.with_suffix(".json.tmp").read_bytes() == b"prior evidence"


def test_first_inner_failure_survives_outer_rollback_error_and_context_is_reset(environment):
    observer = SimNativeFinancialDiagnosticV3()
    with observer.operation():
        try:
            with stage("PHASE_APPLY"):
                try:
                    with stage("CHECKPOINT_COMMIT"): fail()
                finally: raise RuntimeError("rollback SECRET")
        except Exception as exc: observer.record(exc)
    assert observer.latest["stage"] == "CHECKPOINT_COMMIT"
    assert observer.latest["exception_type"] == "OSError"
    with pytest.raises(ValueError):
        with stage("PHASE_VERIFY"): raise ValueError("inert")
    assert observer.failure == ("CHECKPOINT_COMMIT", "OSError")
    with observer.operation():
        assert observer.failure is None


def test_diagnostic_schema_is_bounded_and_custom_exception_names_are_not_serialized(environment):
    secret_error = type("SECRET_CUSTOM_CLASS", (Exception,), {})
    observer = SimNativeFinancialDiagnosticV3()
    observer.record(secret_error("SECRET"), runtime_generation=2**100, configuration_generation="SECRET")
    value = json.loads(diagnostic_path(environment).read_bytes())
    assert set(value) == {"schema", "observed_at", "stage", "status", "error_code", "exception_type",
        "runtime_generation", "configuration_generation", "native_phase_generation", "checkpoint_present", "projection_present"}
    assert value["exception_type"] == "Exception"
    assert value["runtime_generation"] is value["configuration_generation"] is None
    assert value["checkpoint_present"] is value["projection_present"] is False
    assert len(diagnostic_path(environment).read_bytes()) < 1024
    assert "SECRET" not in json.dumps(value)
    for name in STAGES:
        with observer.operation():
            try:
                with stage(name): raise ValueError("SECRET")
            except ValueError as exc: observer.record(exc)
        assert observer.latest["error_code"] == name + "_FAILED"
    assert len(list(diagnostic_path(environment).parent.iterdir())) == 1


def test_mid_apply_failure_rolls_back_journal_and_preserves_pending_fence(environment, bridge_binary, tmp_path, monkeypatch):
    checkpoint = prepare(environment, bridge_binary, tmp_path)
    baseline = json.loads(checkpoint.read_bytes())["account_portfolio"]
    from backend.journal.trade_journal_v2 import TradeJournalV2
    record = TradeJournalV2.record_open_trade
    with monkeypatch.context() as patch:
        def recorded_then_failed(self, *a, **k):
            record(self, *a, **k)
            fail()
        patch.setattr(TradeJournalV2, "record_open_trade", recorded_then_failed)
        svc = service(environment); svc.start()
        assert_failure(svc, environment, "PHASE_APPLY")
    assert svc._runtime.store.capture_state()["account_portfolio"] == baseline
    assert svc._runtime.lifecycle.trade_journal_v2.trades == []
    assert json.loads(checkpoint.read_bytes())["account_portfolio"] == baseline
    evidence = json.loads(checkpoint.with_suffix(".json.evidence.json").read_bytes())
    assert evidence["stage"] == "ROLLED_BACK"
    svc.stop()
    for _ in range(2):
        restored = service(environment); restored.start()
        assert_failure(restored, environment, "CHECKPOINT_VERIFY")
        restored.stop()


@contextmanager
def deny_windows_sharing(path):
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
        ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.CreateFileW(str(path), 0x80000000, 0, None, 3, 0x80, None)
    assert handle != ctypes.c_void_p(-1).value, ctypes.get_last_error()
    try: yield
    finally: assert kernel.CloseHandle(handle)


WINDOWS_CASES = ["existing_destination", "missing_parent", "read_only", "temporary_collision",
    "held_open", "replace_failure", "interrupted_projection", "stale_lock", "checkpoint_lock"]


@pytest.mark.skipif(os.name != "nt", reason="real Windows filesystem semantics required")
@pytest.mark.parametrize("case", WINDOWS_CASES)
def test_windows_filesystem_classification(environment, bridge_binary, tmp_path, monkeypatch, case):
    checkpoint = prepare(environment, bridge_binary, tmp_path)
    projection = environment[0] / "runtime/financial/dashboard-projection.json"
    projection.parent.mkdir(parents=True, exist_ok=True)
    # Construct the genuine empty projection before replay.
    svc = service(environment)
    with monkeypatch.context() as patch:
        patch.setattr(service_module.SimNativeFinancialRuntimeServiceV3, "observe", lambda self: None)
        svc.start()
    svc.stop()
    before = checkpoint.read_bytes()
    classification = "RECOVERABLE_ON_RESTART"
    with monkeypatch.context() as patch:
        if case == "missing_parent":
            # Diagnostic parent starts missing and must be created independently.
            assert not diagnostic_path(environment).parent.exists()
            patch.setattr(service_module.authority, "load_authority", fail)
        elif case == "read_only": projection.chmod(stat.S_IREAD)
        elif case == "temporary_collision":
            checkpoint.with_suffix(".json.tmp").write_bytes(b"interrupted checkpoint")
            classification = "OPERATOR_REVIEW_REQUIRED"
        elif case == "replace_failure":
            replace = os.replace
            patch.setattr(os, "replace", lambda src, dst: fail() if dst == projection else replace(src, dst))
        elif case == "interrupted_projection":
            projection.with_suffix(".json.tmp").write_bytes(b'{"interrupted":')
        elif case == "stale_lock": checkpoint.with_suffix(".json.lock").write_bytes(b"stale unlocked lease")
        restored = service(environment)
        if case == "held_open":
            with deny_windows_sharing(projection): restored.start()
        elif case == "checkpoint_lock":
            holder = service(environment); holder.start()
            try: restored.start()
            finally: holder.stop()
        else: restored.start()
        try:
            if case in {"existing_destination", "interrupted_projection", "stale_lock"}:
                assert_open_once(restored)
            else:
                expected = {"missing_parent": "AUTHORITY_LOAD", "read_only": "PROJECTION_APPLY",
                    "temporary_collision": "CHECKPOINT_START", "held_open": "PROJECTION_APPLY",
                    "replace_failure": "PROJECTION_APPLY", "checkpoint_lock": "CHECKPOINT_OPEN"}[case]
                assert_failure(restored, environment, expected)
                if case in {"missing_parent", "temporary_collision"}: assert checkpoint.read_bytes() == before
        finally:
            restored.stop()
            if case == "read_only": projection.chmod(stat.S_IREAD | stat.S_IWRITE)
    again = service(environment); again.start()
    try:
        if classification == "OPERATOR_REVIEW_REQUIRED":
            assert_failure(again, environment, "CHECKPOINT_START")
        else: assert_open_once(again)
    finally: again.stop()


SEEDS = tuple(range(31000, 31050))


@pytest.mark.parametrize("seed_value", SEEDS)
def test_seeded_offline_restart_and_duplicate_order(environment, bridge_binary, tmp_path, monkeypatch, seed_value):
    prepare(environment, bridge_binary, tmp_path)
    rng = random.Random(seed_value)
    svc = service(environment)
    # Three actual restart cuts, evenly covered by deterministic seeds.
    cut = seed_value % 3
    with monkeypatch.context() as patch:
        if cut == 0: patch.setattr(service_module.SimNativeFinancialRuntimeServiceV3, "observe", lambda self: None)
        elif cut == 1: patch.setattr(NativeSimIntegrationV3, "_publish_dashboard", fail)
        else:
            publish = projection_module.SimNativeFinancialProjectionV3.publish
            def after_projection(self, **event):
                publish(self, **event)
                fail()
            patch.setattr(projection_module.SimNativeFinancialProjectionV3, "publish", after_projection)
        svc.start()
        assert svc.get_snapshot()["status"] == "UNAVAILABLE"
    svc.stop()
    svc = service(environment); svc.start()
    try:
        money = assert_open_once(svc)
        projection = svc._projection.path.read_bytes()
        phases = {p.name: p.read_bytes() for p in environment[1]["state_directory"].glob("*.state")}
        operations = ["restart", "old_phase", "duplicate_event", "existing_receipt", "existing_projection"] * 2
        rng.shuffle(operations)
        for operation in operations:
            if operation == "restart":
                svc.stop(); svc = service(environment); svc.start()
            elif operation in {"old_phase", "existing_receipt"}:
                # All original phase files and receipts remain, including older
                # generations. Reconciliation must verify and skip old effects.
                svc.observe()
            else:
                items = list(svc._runtime.store._native["outbox"].items())
                rng.shuffle(items)
                for event_id, event in items:
                    svc._integration._publish_dashboard(event_id=event_id, event=event)
            assert assert_open_once(svc) == money
            assert svc._projection.path.read_bytes() == projection
            assert {p.name: p.read_bytes() for p in environment[1]["state_directory"].glob("*.state")} == phases
    finally:
        svc.stop()
        assert svc._runtime.store._durability._lease is None
