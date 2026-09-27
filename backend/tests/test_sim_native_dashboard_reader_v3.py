"""Synthetic heartbeat files; no native processes or production file writes."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from backend.services import sim_native_dashboard_reader_v3 as module

NOW = datetime(2026, 9, 27, 18, tzinfo=timezone.utc)


@pytest.fixture
def snapshots(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    root = tmp_path / "ARMS-AI/sim-native-v3/runtime/snapshots"
    root.mkdir(parents=True)
    commissioning = {"schema": "ARMS_CONTROLLED_COMMISSIONING_V3", "observed_at": NOW.isoformat(),
        "restore_status": "NO_PERSISTED_OPERATION", "last_configuration_error": "", "reconciliation_fence": False,
        "configuration_generation": "1", "runtime_generation": "1", "authority_id": "a"*64,
        "backend_account_id": "SIM_NATIVE-917E15181DBB4F8F8D625716795704A3", "native_account": "Sim101",
        "provider": "Simulator", "instrument": "NQ DEC26", **{k: True for k in module.BOOLEAN_FIELDS}}
    commissioning.update(native_submit_enabled=False, auto_retry_allowed=False)
    runtime = {"schema": module.RuntimeSchema.SCHEMA, "observed_at": NOW.isoformat(), "account_name": "Sim101",
        "provider": "Simulator", "instrument": "NQ DEC26", "connection_status": "Connected",
        "physical_test_readiness": "PHYSICAL_TEST_READY", "position_state": "FLAT", "active_order_count": 0,
        "native_submit_enabled": False, "auto_retry_allowed": False}
    def write():
        for name, values in ((module.COMMISSIONING_FILE, commissioning), (module.RuntimeSchema.FILE_NAME, runtime)):
            (root / name).write_text(json.dumps(values), encoding="utf-8")
    write()
    return SimpleNamespace(root=root, commissioning=commissioning, runtime=runtime, write=write,
                           reader=module.SimNativeDashboardReaderV3(clock=lambda: NOW))


def test_healthy_read_is_exact_and_preserves_files(snapshots):
    before = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in snapshots.root.iterdir()}
    value = snapshots.reader.get_snapshot()
    assert value["status"] == "HEALTHY"
    assert value["heartbeat_fresh"] is True and value["heartbeat_age_seconds"] == 0
    assert value["heartbeat_maximum_age_seconds"] == module._MAX_EVIDENCE_AGE.total_seconds() == 15
    assert value["execution_domain"] == "SIM_NATIVE" and value["native_account"] == "Sim101"
    assert value["position_state"] == "FLAT" and value["active_order_count"] == 0
    assert value["native_submit_enabled"] is value["auto_retry_allowed"] is False
    assert before == {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in snapshots.root.iterdir()}


def test_closed_session_is_valid_observation(snapshots):
    snapshots.runtime["physical_test_readiness"] = "MARKET_SESSION_CLOSED"
    snapshots.write()
    value = snapshots.reader.get_snapshot()
    assert value["status"] == "SESSION_CLOSED" and value["heartbeat_fresh"] is True
    assert value["config_signature_valid"] is True


@pytest.mark.parametrize("source", ["commissioning", "runtime"])
@pytest.mark.parametrize("age,status", [(15, "HEALTHY"), (15.001, "STALE"), (-.001, "INVALID")])
def test_either_heartbeat_controls_freshness(snapshots, source, age, status):
    getattr(snapshots, source)["observed_at"] = (NOW-timedelta(seconds=age)).isoformat()
    snapshots.write()
    value = snapshots.reader.get_snapshot()
    assert value["status"] == status
    assert value["heartbeat_fresh"] is (status == "HEALTHY")


@pytest.mark.parametrize("source,field,value", [
    ("runtime", "account_name", "Sim102"), ("runtime", "provider", "Other"), ("runtime", "instrument", "MNQ DEC26"),
    ("commissioning", "backend_account_id", "other"), ("commissioning", "native_account", "Sim102"),
    ("commissioning", "provider", "Other"), ("commissioning", "instrument", "NQ MAR27"),
    ("runtime", "native_submit_enabled", True), ("runtime", "auto_retry_allowed", True),
    ("commissioning", "native_submit_enabled", True), ("commissioning", "auto_retry_allowed", True),
    ("commissioning", "config_signature_valid", False), ("commissioning", "controlled_v3_configured", False),
    ("commissioning", "authority_loaded", False), ("runtime", "active_order_count", True),
    ("runtime", "native_submit_enabled", 0), ("commissioning", "authority_loaded", 1),
    ("runtime", "observed_at", "2026-09-27T18:00:00"), ("runtime", "observed_at", "2026-09-27T18:00:00+01:00"),
    ("runtime", "schema", "other"), ("commissioning", "schema", "other"),
])
def test_bad_identity_safety_types_or_clock_fail_closed(snapshots, source, field, value):
    getattr(snapshots, source)[field] = value
    snapshots.write()
    assert snapshots.reader.get_snapshot()["status"] == "INVALID"


@pytest.mark.parametrize("source,field,value,status", [
    ("commissioning", "reconciliation_fence", True, "DEGRADED"),
    ("commissioning", "reconciliation_fence", "UNKNOWN", "DEGRADED"),
    ("commissioning", "state_path_ready", False, "DEGRADED"),
    ("runtime", "connection_status", "Disconnected", "DISCONNECTED"),
    ("runtime", "active_order_count", 1, "DEGRADED"), ("runtime", "position_state", "LONG", "DEGRADED"),
])
def test_degraded_observations_are_never_healthy(snapshots, source, field, value, status):
    getattr(snapshots, source)[field] = value; snapshots.write()
    assert snapshots.reader.get_snapshot()["status"] == status


@pytest.mark.parametrize("name", [module.COMMISSIONING_FILE, module.RuntimeSchema.FILE_NAME])
@pytest.mark.parametrize("case", ["missing", "partial", "oversized", "duplicate", "unknown", "missing_key", "nonfinite", "unreadable"])
def test_invalid_files_never_return_healthy(snapshots, monkeypatch, name, case):
    path = snapshots.root / name
    if case == "missing": path.unlink()
    elif case == "partial": path.write_bytes(b'{"schema":')
    elif case == "oversized": path.write_bytes(b" "*(module.RuntimeSchema.MAX_FILE_BYTES+1))
    elif case == "duplicate": path.write_text('{"schema":"duplicate",'+path.read_text()[1:])
    elif case == "nonfinite": path.write_text(path.read_text()[:-1]+',"bad":NaN}')
    elif case == "unreadable":
        original = Path.open
        def denied(self, *args, **kwargs):
            if self == path: raise PermissionError("private detail must not leak")
            return original(self, *args, **kwargs)
        monkeypatch.setattr(Path, "open", denied)
    else:
        payload = json.loads(path.read_text())
        if case == "unknown": payload["secret"] = "must-not-leak"
        else: del payload["schema"]
        path.write_text(json.dumps(payload))
    result = snapshots.reader.get_snapshot()
    assert result["status"] in {"INVALID", "UNAVAILABLE"}
    assert result["heartbeat_fresh"] is False
    assert "must-not-leak" not in json.dumps(result) and "private detail" not in json.dumps(result)


def test_redirected_path_fails_closed(snapshots, monkeypatch):
    original = Path.lstat
    monkeypatch.setattr(Path, "lstat", lambda self: SimpleNamespace(st_file_attributes=0x400)
                        if self == snapshots.root else original(self))
    assert snapshots.reader.get_snapshot()["status"] == "INVALID"


def test_registered_gets_cannot_mutate_paper_or_publish_artifacts(snapshots, tmp_path, monkeypatch):
    from backend.api.app import create_app
    from backend.tests.test_dashboard_read_execution_safety_v2 import capture, forbid_mutations
    app = create_app(risk_event_store_path_v2=tmp_path / "risk-events.json")
    before = capture(app)
    guards = forbid_mutations(app, monkeypatch)
    paths_before = {str(p): p.read_bytes() for p in snapshots.root.rglob("*") if p.is_file()}
    client = TestClient(app)
    url = "/api/v3/dashboard/sim-native-runtime"
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(pool.map(lambda _: client.get(url), range(8)))
    assert all(r.status_code == 200 and r.json()["execution_domain"] == "SIM_NATIVE" for r in responses)
    assert all(r.headers["cache-control"] == "no-store" for r in responses)
    assert client.post(url, json={"command": "SUBMIT_ORDER"}).status_code == 405
    assert before == capture(app)
    assert all(guard.call_count == 0 for guard in guards)
    assert paths_before == {str(p): p.read_bytes() for p in snapshots.root.rglob("*") if p.is_file()}
