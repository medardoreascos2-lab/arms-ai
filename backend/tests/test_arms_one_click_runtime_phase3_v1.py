"""Phase 3 sealed native-setup handoff and zero-authority regressions."""

from copy import deepcopy
from datetime import timedelta
import json
from pathlib import Path
from uuid import UUID

import pytest

from backend.tests.test_arms_one_click_runtime_phase2_v1 import (
    NOW, _fixture as phase2_fixture,
)
from tools import arms_one_click_runtime_phase2_v1 as phase2
from tools import arms_one_click_runtime_phase3_v1 as phase3


NATIVE_ID = "11111111-2222-4333-8444-555555555555"
SESSION_ID = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"


class FakeSetupAdapter:
    def __init__(self, mutate=None):
        self.calls = []
        self.mutate = mutate

    def apply_once(self, *, handoff):
        self.calls.append(deepcopy(handoff))
        receipt = {
            "schema": phase3.RECEIPT_SCHEMA,
            "run_id": handoff["run_id"],
            "native_runtime_id": handoff["runtime"]["native_runtime_id"],
            "native_session_id": SESSION_ID,
            "chart_contract": deepcopy(handoff["chart_contract"]),
            "settings": deepcopy(handoff["settings"]),
            "apply_count": 1,
            "applied_utc": NOW.isoformat().replace("+00:00", "Z"),
            **phase3._ZERO_AUTHORITY,
        }
        if self.mutate is not None:
            self.mutate(receipt)
        return receipt


class FakeHelloObserver:
    def __init__(self, values):
        self.values = list(values)

    def observe(self):
        return self.values.pop(0) if self.values else None


class FakeTime:
    def __init__(self):
        self.value = 0.0

    def monotonic(self):
        return self.value

    def sleep(self, _seconds):
        self.value += 1.0


def _write_json(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


def _runtime_artifacts(manifest, runtime):
    inbox = runtime / "inbox"
    catchup = runtime / "chart-catchup"
    inbox.mkdir(parents=True)
    catchup.mkdir()
    claim = {
        "run_id": NATIVE_ID,
        "pid": 1234,
        "process_start": 5678,
        "mode": "ANALYSIS_ONLY",
        "exporter_identity": {"authored_sha256": "a" * 64},
        "bootstrap_sha256": manifest["inputs"]["bootstrap_evidence"]["sha256"],
        "startup_chart_catchup_required": True,
        "backend_url": f"http://127.0.0.1:{manifest['ports']['backend']}",
        "dashboard_url": (
            f"http://127.0.0.1:{manifest['ports']['frontend']}/market-analysis"),
        "input_directory": str(inbox.resolve()),
    }
    request = {
        "schema": "arms.startup-chart-catchup-request.v1",
        "indicator": "ArmsChartCatchupBridgeV1",
        "capture_enabled": True,
        "output_directory": str(catchup.resolve()),
        "live_output_directory": str(inbox.resolve()),
        "expected_provider_enum": "Provider31",
        "from_close_utc": "2026-10-06T17:38:00Z",
        "through_close_utc": "LATEST_CLOSED",
        "through_selection": "CHART_LATEST_CLOSED",
        "absolute_time_authority": "NONE",
        "range_contract": "EXACT_CONTIGUOUS_NO_TRUNCATION",
        "range_duration_seconds": 26220,
        "range_maximum_seconds": 172800,
        "observation_only": True,
        "runtime_admission": False,
        "execution_authority": False,
    }
    _write_json(runtime / "claim.json", claim)
    _write_json(runtime / "chart-catchup-request.json", request)
    return claim, request


def _fixture(tmp_path):
    fixture, run = phase2_fixture(tmp_path)
    fixture.active.write_text("DO NOT TOUCH", encoding="utf-8")
    directory, manifest, phase1_state, _, _ = phase2._load_plan(
        run, now=NOW)
    bindings = phase2._bindings(manifest, phase1_state)
    authorization = phase2.authorize_start(
        run, clock=lambda: NOW, token_factory=lambda _: b"p" * 32)
    phase2._transition(
        directory, manifest, bindings, state=phase2.STARTING,
        transition="PROCESS_STARTING", clock=lambda: NOW,
        expected_states=(phase2.AUTHORIZED,))
    ownership = {
        "pid": 43210, "identity": [101, 202],
        "command_sha256": "b" * 64, "spawn_challenge_sha256": "c" * 64,
    }
    phase2._transition(
        directory, manifest, bindings, state=phase2.STARTING,
        transition="PROCESS_OWNERSHIP_RECORDED", clock=lambda: NOW,
        details={"ownership": ownership}, expected_states=(phase2.STARTING,))
    runtime = Path(manifest["targets"]["runtime_parent"]) / NATIVE_ID
    claim, request = _runtime_artifacts(manifest, runtime)
    return fixture, run, runtime, claim, request, authorization


def _prepare(tmp_path, *, timeout=2):
    fixture, run, runtime, claim, request, phase2_authorization = _fixture(tmp_path)
    result = phase3.prepare_handoff(
        run, runtime, clock=lambda: NOW, hello_timeout_seconds=timeout)
    return fixture, run, runtime, claim, request, phase2_authorization, result


def _authorize(run, *, now=NOW, ttl=30):
    return phase3.authorize_setup(
        run, clock=lambda: now, ttl_seconds=ttl,
        token_factory=lambda _: b"s" * 32)


def _execute(run, authorization, adapter, observer, *, now=NOW):
    fake_time = FakeTime()
    return phase3.execute_authorized(
        run, authorization, authorization.token_for_immediate_consumption(),
        setup_adapter=adapter, hello_observer=observer,
        clock=lambda: now, monotonic=fake_time.monotonic,
        sleeper=fake_time.sleep)


def test_handoff_derives_exact_dynamic_paths_and_preserves_zero_authority(tmp_path):
    fixture, run, runtime, _, request, _, result = _prepare(tmp_path)
    handoff = result["handoff"]
    assert handoff["runtime"]["live_inbox"] == str((runtime / "inbox").resolve())
    assert handoff["runtime"]["catchup_output_directory"] == str(
        (runtime / "chart-catchup").resolve())
    assert handoff["runtime"]["from_close_utc"] == request["from_close_utc"]
    assert handoff["runtime"]["through_close_utc"] == "LATEST_CLOSED"
    assert handoff["chart_contract"] == phase3._CHART
    assert handoff["settings"]["ArmsReadOnlyMarketV1"] == {
        "OutputDirectory": str((runtime / "inbox").resolve()),
        "ExpectedProvider": "Provider31",
    }
    assert handoff["settings"]["ArmsChartCatchupBridgeV1"]["CaptureEnabled"] is True
    assert result["ninjatrader_setup_authority"] is False
    assert all(result[key] is False for key in phase3._ZERO_AUTHORITY)
    assert phase2.status(run)["ninjatrader_control_authority"] is False
    assert fixture.active.read_text(encoding="utf-8") == "DO NOT TOUCH"


@pytest.mark.parametrize(("field", "value"), [
    ("output_directory", "C:/stale/previous-run/chart-catchup"),
    ("live_output_directory", "C:/stale/previous-run/inbox"),
    ("expected_provider_enum", "Provider32"),
    ("capture_enabled", False),
    ("through_close_utc", "2026-10-06T18:00:00Z"),
])
def test_invalid_or_stale_runtime_request_is_rejected(tmp_path, field, value):
    _, run, runtime, _, request, _ = _fixture(tmp_path)
    request[field] = value
    _write_json(runtime / "chart-catchup-request.json", request)
    with pytest.raises(phase3.Phase3Blocked, match="CHART_REQUEST_CONTRACT_INVALID"):
        phase3.prepare_handoff(run, runtime, clock=lambda: NOW)
    assert not (run / "phase3-handoff.json").exists()


@pytest.mark.parametrize("mutation", [
    lambda r: r["chart_contract"].update(instrument="ES DEC26"),
    lambda r: r["chart_contract"].update(bars_value=5),
    lambda r: r["chart_contract"].update(trading_hours="Default 24 x 7"),
    lambda r: r["chart_contract"].update(provider="Provider32"),
    lambda r: r["settings"]["ArmsChartCatchupBridgeV1"].update(
        CaptureEnabled=False),
    lambda r: r["settings"]["ArmsChartCatchupBridgeV1"].update(
        FromCloseUtc="2026-10-06T17:39:00Z"),
    lambda r: r["settings"]["ArmsChartCatchupBridgeV1"].update(
        ThroughCloseUtc="2026-10-06T18:00:00Z"),
    lambda r: r["settings"]["ArmsChartCatchupBridgeV1"].update(
        LiveOutputDirectory="C:/foreign/inbox"),
])
def test_apply_receipt_must_match_exact_chart_and_settings(tmp_path, mutation):
    _, run, *_ = _prepare(tmp_path)
    authorization = _authorize(run)
    adapter = FakeSetupAdapter(mutation)
    with pytest.raises(phase3.Phase3Blocked, match="NATIVE_APPLY_RECEIPT_INVALID"):
        _execute(run, authorization, adapter, FakeHelloObserver([SESSION_ID]))
    assert len(adapter.calls) == 1
    state = phase3.status(run)
    assert state["state"] == phase3.FAILED
    assert state["apply_count"] == 1
    assert state["ninjatrader_setup_authority"] is False


def test_exactly_one_apply_and_second_attempt_is_blocked(tmp_path):
    _, run, *_ = _prepare(tmp_path)
    authorization = _authorize(run)
    adapter = FakeSetupAdapter()
    result = _execute(
        run, authorization, adapter, FakeHelloObserver([None, SESSION_ID]))
    assert result["state"] == phase3.COMPLETE
    assert result["apply_count"] == len(adapter.calls) == 1
    assert result["ninjatrader_setup_authority"] is False
    assert all(result[key] is False for key in phase3._ZERO_AUTHORITY)
    with pytest.raises(phase3.Phase3Blocked, match="SETUP_AUTHORIZATION_REQUIRED"):
        _execute(run, authorization, adapter, FakeHelloObserver([SESSION_ID]))
    assert len(adapter.calls) == 1


def test_expired_authorization_is_consumed_relinquished_and_cannot_be_reused(tmp_path):
    _, run, *_ = _prepare(tmp_path)
    authorization = _authorize(run, ttl=1)
    adapter = FakeSetupAdapter()
    with pytest.raises(phase3.Phase3Blocked, match="SETUP_AUTHORIZATION_EXPIRED"):
        _execute(
            run, authorization, adapter, FakeHelloObserver([SESSION_ID]),
            now=NOW + timedelta(seconds=2))
    assert authorization.consumed is True
    assert adapter.calls == []
    state = phase3.status(run)
    assert state["state"] == phase3.REVOKED
    assert state["ninjatrader_setup_authority"] is False
    with pytest.raises(phase3.Phase3Blocked, match="SETUP_AUTHORIZATION_REQUIRED"):
        _execute(run, authorization, adapter, FakeHelloObserver([SESSION_ID]))


@pytest.mark.parametrize("target", ["source", "profile", "request"])
def test_source_config_or_request_digest_drift_blocks_before_apply(tmp_path, target):
    fixture, run, runtime, _, request, _, _ = _prepare(tmp_path)
    if target == "source":
        descriptor = fixture.profile["reviewed_source_pins"][phase3.PHASE3_SOURCE]
        Path(descriptor["path"]).write_bytes(b"drift")
    elif target == "profile":
        fixture.profile_path.write_text("{}", encoding="utf-8")
    else:
        request["from_close_utc"] = "2026-10-06T17:39:00Z"
        _write_json(runtime / "chart-catchup-request.json", request)
    with pytest.raises((phase3.Phase3Blocked, phase2.phase1.OfflineBlocked)):
        phase3.authorize_setup(run, clock=lambda: NOW)


def test_missing_hello_times_out_and_fails_closed_after_one_apply(tmp_path):
    _, run, *_ = _prepare(tmp_path, timeout=1)
    authorization = _authorize(run)
    adapter = FakeSetupAdapter()
    with pytest.raises(phase3.Phase3Blocked, match="NATIVE_HELLO_TIMEOUT"):
        _execute(run, authorization, adapter, FakeHelloObserver([]))
    state = phase3.status(run)
    assert state["state"] == phase3.FAILED
    assert state["apply_count"] == len(adapter.calls) == 1
    assert all(state[key] is False for key in phase3._ZERO_AUTHORITY)


def test_foreign_hello_session_is_rejected(tmp_path):
    _, run, *_ = _prepare(tmp_path)
    authorization = _authorize(run)
    foreign = str(UUID("ffffffff-eeee-4ddd-8ccc-bbbbbbbbbbbb"))
    with pytest.raises(phase3.Phase3Blocked, match="FOREIGN_NATIVE_HELLO_SESSION"):
        _execute(
            run, authorization, FakeSetupAdapter(), FakeHelloObserver([foreign]))
    assert phase3.status(run)["state"] == phase3.FAILED


def test_status_rejects_tampered_authority_evidence(tmp_path):
    _, run, *_ = _prepare(tmp_path)
    events_path = run / "phase3-events.json"
    events = json.loads(events_path.read_text(encoding="utf-8"))
    events["events"][0]["order_authority"] = True
    _write_json(events_path, events)
    with pytest.raises(phase3.Phase3Blocked, match="PHASE3_EVENT_CHAIN_INVALID"):
        phase3.status(run)
