"""Fixture-first Phase 2 execution authority and owned-stop regressions."""

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path

import pytest

from backend.tests.test_arms_one_click_runtime_v1 import (
    IDENTITY, _reviewed_fixture,
)
from tools import arms_one_click_runtime_v1 as phase1
from tools import arms_one_click_runtime_phase2_v1 as phase2
from tools import arms_one_click_runtime_phase3_v1 as phase3


NOW = datetime(2026, 10, 6, 18, 30, tzinfo=timezone.utc)
NATIVE_ID = "11111111-2222-4333-8444-555555555555"
SESSION_ID = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"


def _write_runtime_artifacts(manifest, runtime_id=NATIVE_ID):
    runtime = Path(manifest["targets"]["runtime_parent"]) / runtime_id
    inbox = runtime / "inbox"
    catchup = runtime / "chart-catchup"
    inbox.mkdir(parents=True)
    catchup.mkdir()
    claim = {
        "run_id": runtime_id,
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
    (runtime / "claim.json").write_text(json.dumps(claim), encoding="utf-8")
    (runtime / "chart-catchup-request.json").write_text(
        json.dumps(request), encoding="utf-8")
    return runtime


class FakeProcessAdapter:
    def __init__(self, *, running=True, identity=(101, 202)):
        self.running = running
        self.identity = list(identity)
        self.start_calls = []
        self.native_wait_calls = []
        self.paper_wait_calls = []
        self.stop_calls = []

    def start(self, **kwargs):
        captured = dict(kwargs)
        captured["environment"] = dict(kwargs["environment"])
        self.start_calls.append(captured)
        return {
            "pid": 43210,
            "identity": list(self.identity),
            "command_sha256": sha256(
                phase1._canonical(list(kwargs["command"]))).hexdigest(),
            "spawn_challenge_sha256": "c" * 64,
            "runtime_directories_before_start": (
                phase2.WindowsProcessAdapter._runtime_directories(
                    kwargs["manifest"])),
        }

    def wait_native_setup(self, **kwargs):
        self.native_wait_calls.append(kwargs)
        _write_runtime_artifacts(kwargs["manifest"])
        binding = phase2.WindowsProcessAdapter._native_setup_binding(
            kwargs["manifest"], kwargs["ownership"])
        return {
            "analysis_runtime_process_alive": True,
            "supervisor_health": "PASS",
            "control_plane_observable": True,
            "frontend_observable": True,
            "paper_readiness_required": False,
            "paper_execution_enabled": False,
            "live_execution_allowed": False,
            "external_order_authority": False,
            "broker_live_order_authority": False,
            "ninjatrader_touched": False,
            "native_setup": binding,
        }

    def wait_running(self, **kwargs):
        self.paper_wait_calls.append(kwargs)
        return {
            "paper_runtime_process_alive": True,
            "analysis_runtime_process_alive": True,
            "supervisor_health": "PASS",
            "control_plane_observable": True,
            "paper_execution_enabled": False,
            "live_execution_allowed": False,
            "external_order_authority": False,
            "broker_live_order_authority": False,
            "ninjatrader_touched": False,
        }

    def matches(self, ownership):
        return (self.running and ownership["pid"] == 43210
                and ownership["identity"] == self.identity)

    def verify_cleanup_ownership(self, **kwargs):
        if not self.matches(kwargs["ownership"]):
            raise phase2.Phase2Blocked(
                "OWNED_SUPERVISOR_IDENTITY_MISMATCH")
        expected = sha256(phase1._canonical(
            kwargs["manifest"]["disabled_future_start_command"])).hexdigest()
        if kwargs["ownership"]["command_sha256"] != expected:
            raise phase2.Phase2Blocked(
                "OWNED_SUPERVISOR_EVIDENCE_MISMATCH")
        return {"state": "RUNNING"}

    def stop(self, **kwargs):
        if not self.matches(kwargs["ownership"]):
            raise phase2.Phase2Blocked("OWNED_SUPERVISOR_IDENTITY_MISMATCH")
        self.stop_calls.append(kwargs)
        self.running = False
        return {"controlled_stop_requested": True,
                "run_id": kwargs["manifest"]["run_id"],
                "run_scoped_process_count": 0,
                "run_scoped_ports_open": 0,
                "job_membership_remains": 0,
                "cleanup_evidence_status": "PASS",
                "child_cleanup_confirmed": True}


def _fixture(tmp_path):
    fixture = _reviewed_fixture(tmp_path)
    template = tmp_path / "inputs" / "calendar.xml"
    loaded = tmp_path / "inputs" / "loaded-calendar.jsonl"
    template.write_bytes(b"reviewed-template")
    loaded.write_bytes(b"reviewed-loaded-calendar\n")
    spec = {
        "schema": "arms.native-capture-spec.sprint13.v1",
        "provider_enum": "Provider31",
        "expiry": "2026-12-01",
        "calendar_evidence_file": str(template),
        "calendar_evidence_sha256": sha256(template.read_bytes()).hexdigest(),
        "loaded_calendar_evidence_file": str(loaded),
        "loaded_calendar_evidence_sha256": sha256(loaded.read_bytes()).hexdigest(),
        "contract": {
            "provider": "Provider31", "instrument": "NQ",
            "contract": "NQ DEC26",
            "trading_hours_template": "CME US Index Futures ETH",
            "valid_from": (NOW - timedelta(minutes=1)).isoformat(),
            "valid_until": (NOW + timedelta(days=1)).isoformat(),
        },
        "unknown_policy": "FAIL_CLOSED",
        "order_authority": False,
    }
    spec_raw = json.dumps(spec).encode()
    spec_path = Path(fixture.profile["native_spec"]["path"])
    spec_path.write_bytes(spec_raw)
    fixture.profile["native_spec"]["sha256"] = sha256(spec_raw).hexdigest()
    fixture.profile_path.write_text(json.dumps(fixture.profile), encoding="utf-8")
    prepared = phase1.prepare(
        fixture.profile_path, workspace=fixture.workspace,
        clock=lambda: NOW, identity=IDENTITY)
    return fixture, Path(prepared["run_directory"])


def _authorize(run, **kwargs):
    return phase2.authorize_start(
        run, clock=lambda: NOW, token_factory=lambda _: b"a" * 32, **kwargs)


def _start(run, authorization, adapter, token=None, clock=None):
    return phase2.start_authorized(
        run, authorization,
        authorization.token_for_immediate_consumption() if token is None else token,
        clock=clock or (lambda: NOW), process_adapter=adapter,
        readiness_timeout=1)


def _complete_phase3(run):
    runtime = Path(phase2.status(run)["native_setup"]["runtime_directory"])
    phase3.prepare_handoff(run, runtime, clock=lambda: NOW,
                           hello_timeout_seconds=1)
    authorization = phase3.operator_authorization(
        run, clock=lambda: NOW, token_factory=lambda _: b"s" * 32)

    class HelloObserver:
        @staticmethod
        def observe_evidence():
            handoff = phase3.status(run)["handoff"]
            control = json.loads(Path(
                handoff["native_binding"]["control_file"]).read_text(
                    encoding="utf-8"))
            claim = json.loads(control["claim_json"])
            return {
                "native_session_id": SESSION_ID,
                "native_runtime_id": NATIVE_ID,
                "provider": "Provider31",
                "binding_nonce": claim["binding_nonce"],
                "binding_claim_sha256": control["claim_sha256"],
                "handoff_file_sha256": claim["handoff_file_sha256"],
            }

    return phase3.begin_operator_apply(
        run, authorization["authorization_token"],
        authorization["handoff_file_sha256"],
        hello_observer=HelloObserver(), clock=lambda: NOW)


def test_prepared_offline_cannot_spawn_without_authorization(tmp_path):
    _, run = _fixture(tmp_path)
    adapter = FakeProcessAdapter()
    with pytest.raises(phase2.Phase2Blocked, match="AUTHORIZED_START_REQUIRED"):
        phase2.start_authorized(
            run, object(), b"x" * 32, clock=lambda: NOW,
            process_adapter=adapter)
    assert adapter.start_calls == []


def test_legacy_phase2_state_projection_does_not_invent_native_binding():
    event = phase2._phase2_event(
        run_id="legacy", sequence=1,
        timestamp="2026-10-06T18:30:00Z", previous=None,
        transition="START_AUTHORIZED", state=phase2.AUTHORIZED,
        bindings={"plan_sha256": "a" * 64}, details={})
    assert "native_setup" not in phase2._state_from_event(event)


def test_bad_token_cannot_spawn_and_authorization_is_consumed(tmp_path):
    _, run = _fixture(tmp_path)
    authorization = _authorize(run)
    adapter = FakeProcessAdapter()
    with pytest.raises(phase2.Phase2Blocked, match="TOKEN_INVALID"):
        _start(run, authorization, adapter, token=b"b" * 32)
    assert authorization.consumed is True
    assert adapter.start_calls == []
    with pytest.raises(phase2.Phase2Blocked, match="AUTHORIZED_START_REQUIRED"):
        _start(run, authorization, adapter)


def test_expired_authorization_cannot_spawn(tmp_path):
    _, run = _fixture(tmp_path)
    authorization = _authorize(run, ttl_seconds=1)
    adapter = FakeProcessAdapter()
    with pytest.raises(phase2.Phase2Blocked, match="AUTHORIZATION_EXPIRED"):
        _start(
            run, authorization, adapter,
            clock=lambda: NOW + timedelta(seconds=2))
    assert adapter.start_calls == []


@pytest.mark.parametrize("field", (
    "plan_sha256", "profile_sha256", "capture_spec_sha256",
))
def test_wrong_authorization_binding_cannot_spawn(tmp_path, field):
    _, run = _fixture(tmp_path)
    authorization = _authorize(run)
    setattr(authorization, field, "0" * 64)
    adapter = FakeProcessAdapter()
    with pytest.raises(phase2.Phase2Blocked, match="BINDING_MISMATCH"):
        _start(run, authorization, adapter)
    assert adapter.start_calls == []


def test_reused_token_cannot_spawn_second_time(tmp_path):
    _, run = _fixture(tmp_path)
    authorization = _authorize(run)
    token = authorization.token_for_immediate_consumption()
    adapter = FakeProcessAdapter()
    _start(run, authorization, adapter, token=token)
    with pytest.raises(phase2.Phase2Blocked, match="AUTHORIZED_START_REQUIRED"):
        _start(run, authorization, adapter, token=token)
    assert len(adapter.start_calls) == 1


def test_arbitrary_resealed_command_cannot_authorize_or_spawn(tmp_path):
    _, run = _fixture(tmp_path)
    manifest_path = run / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["disabled_future_start_command"] = ["arbitrary.exe"]
    manifest_raw = (json.dumps(manifest, sort_keys=True, indent=2).encode()
                    + b"\n")
    manifest_path.write_bytes(manifest_raw)
    digest = sha256(manifest_raw).hexdigest()
    seal_path = run / "seal.json"
    seal = json.loads(seal_path.read_text())
    seal["manifest_sha256"] = digest
    seal_path.write_text(json.dumps(seal), encoding="utf-8")
    state_path = run / "state.json"
    state = json.loads(state_path.read_text())
    state["manifest_sha256"] = digest
    state_path.write_text(json.dumps(state), encoding="utf-8")
    with pytest.raises(phase1.OfflineBlocked, match="COMMAND_CONTRACT_INVALID"):
        _authorize(run)


def test_valid_start_reaches_durable_native_setup_wait_without_paper(tmp_path):
    fixture, run = _fixture(tmp_path)
    authorization = _authorize(run)
    adapter = FakeProcessAdapter()
    result = _start(run, authorization, adapter)
    assert result["state"] == phase2.AWAITING_NATIVE_SETUP
    assert result["native_setup"]["native_runtime_id"] == NATIVE_ID
    assert len(adapter.native_wait_calls) == 1
    assert adapter.paper_wait_calls == []
    events = json.loads((run / "phase2-events.json").read_text())["events"]
    assert [event["state"] for event in events] == [
        phase2.AUTHORIZED, phase2.STARTING, phase2.STARTING,
        phase2.AWAITING_NATIVE_SETUP]
    assert all(event["paper_execution_enabled"] is False for event in events)
    assert all(event["live_execution_allowed"] is False for event in events)
    assert all(event["external_order_authority"] is False for event in events)
    assert all(event["ninjatrader_control_authority"] is False for event in events)
    command = adapter.start_calls[0]["command"]
    assert command == json.loads((run / "manifest.json").read_text())[
        "disabled_future_start_command"]
    assert command[0] == str(Path(fixture.profile["python_path"]).resolve())


def test_intermediate_state_binds_only_runtime_created_after_start(tmp_path):
    _, run = _fixture(tmp_path)
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    stale_id = "99999999-8888-4777-8666-555555555555"
    stale = _write_runtime_artifacts(manifest, stale_id)
    adapter = FakeProcessAdapter()
    result = _start(run, _authorize(run), adapter)
    assert result["native_setup"]["native_runtime_id"] == NATIVE_ID
    assert result["native_setup"]["runtime_directory"] != str(stale.resolve())
    assert str(stale.resolve()) in result["ownership"][
        "runtime_directories_before_start"]


def test_phase3_completion_allows_final_running_disabled_readiness(tmp_path):
    _, run = _fixture(tmp_path)
    adapter = FakeProcessAdapter()
    _start(run, _authorize(run), adapter)
    _complete_phase3(run)
    result = phase2.continue_after_native_setup(
        run, clock=lambda: NOW, process_adapter=adapter,
        readiness_timeout=1)
    assert result["state"] == phase2.RUNNING
    assert len(adapter.paper_wait_calls) == 1
    assert result["native_setup"]["native_runtime_id"] == NATIVE_ID
    assert result["paper_execution_enabled"] is False
    assert result["live_execution_allowed"] is False
    assert result["external_order_authority"] is False
    assert result["broker_live_order_authority"] is False
    assert result["ninjatrader_control_authority"] is False


def _final_readiness_evidence(tmp_path, **updates):
    parent = tmp_path / "native-runtimes"
    runtime = parent / NATIVE_ID
    inbox = runtime / "inbox"
    catchup = runtime / "chart-catchup"
    inbox.mkdir(parents=True)
    catchup.mkdir()
    evidence = {
        "run_id": NATIVE_ID,
        "status": "FAILED",
        "error_type": "ValueError",
        "error_code": "UNEXPECTED_DATA_GAP",
    }
    evidence.update(updates)
    (runtime / "shutdown-result.json").write_text(
        json.dumps(evidence), encoding="utf-8")
    manifest = {
        "ports": {"backend": 41001, "frontend": 41002, "paper": 41003},
        "targets": {
            "runtime_parent": str(parent.resolve()),
            "supervisor_report_directory": str((tmp_path / "reports").resolve()),
        },
    }
    native_setup = {
        "runtime_directory": str(runtime.resolve()),
        "native_runtime_id": NATIVE_ID,
        "live_inbox": str(inbox.resolve()),
        "catchup_output_directory": str(catchup.resolve()),
    }
    return manifest, native_setup, runtime


def test_valid_shutdown_evidence_surfaces_normalized_final_failure(
        tmp_path, monkeypatch):
    manifest, native_setup, _ = _final_readiness_evidence(tmp_path)
    adapter = phase2.WindowsProcessAdapter()
    monkeypatch.setattr(adapter, "matches", lambda ownership: False)

    with pytest.raises(
            phase2.Phase2Blocked,
            match="^FINAL_READINESS_FAILED:UNEXPECTED_DATA_GAP$"):
        adapter.wait_running(
            ownership={}, manifest=manifest, native_setup=native_setup,
            timeout_seconds=1)


@pytest.mark.parametrize("mutation", (
    "missing",
    "malformed",
    "wrong_run_id",
    "wrong_status",
    "unknown_code",
))
def test_invalid_shutdown_evidence_preserves_generic_exit_reason(
        tmp_path, mutation):
    updates = {}
    if mutation == "wrong_run_id":
        updates["run_id"] = "99999999-8888-4777-8666-555555555555"
    elif mutation == "wrong_status":
        updates["status"] = "PASS"
    elif mutation == "unknown_code":
        updates["error_code"] = "attacker-controlled"
    manifest, native_setup, runtime = _final_readiness_evidence(
        tmp_path, **updates)
    shutdown = runtime / "shutdown-result.json"
    if mutation == "missing":
        shutdown.unlink()
    elif mutation == "malformed":
        shutdown.write_bytes(b"not-json")

    assert phase2.WindowsProcessAdapter._final_readiness_exit_reason(
        manifest=manifest, native_setup=native_setup
    ) == "SUPERVISOR_EXITED_DURING_FINAL_READINESS"


def test_unrelated_runtime_path_cannot_supply_final_failure(tmp_path):
    manifest, native_setup, _ = _final_readiness_evidence(tmp_path / "bound")
    _, forged_setup, _ = _final_readiness_evidence(tmp_path / "foreign")
    forged_setup["native_runtime_id"] = native_setup["native_runtime_id"]

    assert phase2.WindowsProcessAdapter._final_readiness_exit_reason(
        manifest=manifest, native_setup=forged_setup
    ) == "SUPERVISOR_EXITED_DURING_FINAL_READINESS"


def test_phase3_failure_blocks_final_running_and_cleans_owned_runtime(tmp_path):
    _, run = _fixture(tmp_path)
    adapter = FakeProcessAdapter()
    _start(run, _authorize(run), adapter)
    runtime = Path(phase2.status(run)["native_setup"]["runtime_directory"])
    phase3.prepare_handoff(
        run, runtime, clock=lambda: NOW, hello_timeout_seconds=1)
    authorization = phase3.authorize_setup(
        run, clock=lambda: NOW, token_factory=lambda _: b"s" * 32)

    class SetupAdapter:
        @staticmethod
        def apply_once(*, handoff):
            return {
                "schema": phase3.RECEIPT_SCHEMA,
                "run_id": handoff["run_id"],
                "native_runtime_id": handoff["runtime"]["native_runtime_id"],
                "native_session_id": SESSION_ID,
                "chart_contract": handoff["chart_contract"],
                "settings": handoff["settings"],
                "apply_count": 1,
                "applied_utc": NOW.isoformat().replace("+00:00", "Z"),
                **phase3._ZERO_AUTHORITY,
            }

    class NoHello:
        @staticmethod
        def observe():
            return None

    ticks = iter((0.0, 2.0))
    with pytest.raises(phase3.Phase3Blocked, match="NATIVE_HELLO_TIMEOUT"):
        phase3.execute_authorized(
            run, authorization,
            authorization.token_for_immediate_consumption(),
            setup_adapter=SetupAdapter(), hello_observer=NoHello(),
            clock=lambda: NOW, monotonic=lambda: next(ticks),
            sleeper=lambda _: None)
    assert phase3.status(run)["state"] == phase3.FAILED
    with pytest.raises(phase2.Phase2Blocked,
                       match="PHASE3_HANDOFF_COMPLETE_REQUIRED"):
        phase2.continue_after_native_setup(
            run, clock=lambda: NOW, process_adapter=adapter,
            readiness_timeout=1)
    state = phase2.status(run)
    assert state["state"] == phase2.FAILED
    assert adapter.paper_wait_calls == []
    assert len(adapter.stop_calls) == 1
    assert state["paper_execution_enabled"] is False
    assert state["live_execution_allowed"] is False
    assert state["external_order_authority"] is False
    assert state["broker_live_order_authority"] is False
    assert state["ninjatrader_control_authority"] is False


def test_process_admin_token_and_quote_age_are_child_scoped_and_not_persisted(
        tmp_path, monkeypatch):
    _, run = _fixture(tmp_path)
    monkeypatch.setenv("ARMS_MAXIMUM_QUOTE_AGE_SECONDS", "999")
    authorization = _authorize(run)
    adapter = FakeProcessAdapter()
    _start(run, authorization, adapter)
    manifest = json.loads((run / "manifest.json").read_text())
    env_name = manifest["admin_token"]["environment_name"]
    child_environment = adapter.start_calls[0]["environment"]
    assert child_environment[env_name]
    assert {
        name: child_environment[name]
        for name in phase1.REVIEWED_RUNTIME_ENVIRONMENT
    } == phase1.REVIEWED_RUNTIME_ENVIRONMENT
    assert env_name not in __import__("os").environ
    serialized = b"".join(path.read_bytes() for path in run.glob("*.json"))
    assert child_environment[env_name].encode() not in serialized
    assert authorization.token_for_immediate_consumption() not in serialized


def test_exact_supervisor_process_identity_is_adopted(monkeypatch):
    report = {
        "run_id": "run", "supervisor_pid": 8123,
        "supervisor_identity": [91, 92],
        "spawn_challenge_sha256": "a" * 64,
    }
    monkeypatch.setattr(
        phase2.supervisor, "_pid_alive",
        lambda pid, identity: pid == 8123 and identity == (91, 92))
    owned = phase2.WindowsProcessAdapter._verified_supervisor_ownership(
        report=report, manifest={"run_id": "run"},
        challenge_sha256="a" * 64, command_sha256="b" * 64)
    assert owned["pid"] == report["supervisor_pid"]
    assert owned["identity"] == report["supervisor_identity"]


@pytest.mark.parametrize("mutation", (
    lambda value: value.update(supervisor_pid=8124),
    lambda value: value.update(supervisor_identity=[93, 94]),
    lambda value: value.update(spawn_challenge_sha256="c" * 64),
))
def test_mismatched_supervisor_identity_is_rejected(monkeypatch, mutation):
    report = {
        "run_id": "run", "supervisor_pid": 8123,
        "supervisor_identity": [91, 92],
        "spawn_challenge_sha256": "a" * 64,
    }
    mutation(report)
    monkeypatch.setattr(
        phase2.supervisor, "_pid_alive",
        lambda pid, identity: pid == 8123 and identity == (91, 92))
    with pytest.raises(phase2.Phase2Blocked, match="SPAWN_IDENTITY_MISMATCH"):
        phase2.WindowsProcessAdapter._verified_supervisor_ownership(
            report=report, manifest={"run_id": "run"},
            challenge_sha256="a" * 64, command_sha256="b" * 64)


def test_running_postcondition_rejects_any_authority_escalation(tmp_path):
    _, run = _fixture(tmp_path)
    authorization = _authorize(run)

    class Unsafe(FakeProcessAdapter):
        def wait_running(self, **kwargs):
            result = super().wait_running(**kwargs)
            result["paper_execution_enabled"] = True
            return result

    adapter = Unsafe()
    _start(run, authorization, adapter)
    _complete_phase3(run)
    with pytest.raises(phase2.Phase2Blocked, match="SAFETY_POSTCONDITION"):
        phase2.continue_after_native_setup(
            run, clock=lambda: NOW, process_adapter=adapter,
            readiness_timeout=1)
    assert adapter.stop_calls
    assert phase2.status(run)["state"] == phase2.FAILED


def test_controlled_stop_targets_only_exact_owned_process(tmp_path):
    _, run = _fixture(tmp_path)
    adapter = FakeProcessAdapter()
    _start(run, _authorize(run), adapter)
    result = phase2.stop(run, clock=lambda: NOW, process_adapter=adapter)
    assert result["state"] == phase2.STOPPED
    assert len(adapter.stop_calls) == 1
    assert adapter.paper_wait_calls == []
    assert adapter.stop_calls[0]["ownership"]["pid"] == 43210
    assert result["paper_execution_enabled"] is False
    assert result["live_execution_allowed"] is False


def test_cleanup_confirmation_requires_all_strong_evidence_fields():
    incomplete = {
        "run_id": "run", "controlled_stop_requested": True,
        "child_cleanup_confirmed": True,
    }
    assert phase2.WindowsProcessAdapter._cleanup_report_passes(
        incomplete, run_id="run", controlled_stop=True) is False
    complete = {
        **incomplete,
        "run_scoped_process_count": 0,
        "run_scoped_ports_open": 0,
        "job_membership_remains": 0,
        "cleanup_evidence_status": "PASS",
    }
    assert phase2.WindowsProcessAdapter._cleanup_report_passes(
        complete, run_id="run", controlled_stop=True) is True


def test_capture_expiry_never_blocks_owned_controlled_stop(tmp_path):
    _, run = _fixture(tmp_path)
    adapter = FakeProcessAdapter()
    _start(run, _authorize(run), adapter)
    result = phase2.stop(
        run, clock=lambda: NOW + timedelta(days=2),
        process_adapter=adapter)
    assert result["state"] == phase2.STOPPED
    assert len(adapter.stop_calls) == 1


def test_pid_reuse_cannot_target_unrelated_process(tmp_path):
    _, run = _fixture(tmp_path)
    adapter = FakeProcessAdapter()
    _start(run, _authorize(run), adapter)
    adapter.identity = [999, 999]
    with pytest.raises(phase2.Phase2Blocked, match="IDENTITY_MISMATCH"):
        phase2.stop(run, clock=lambda: NOW, process_adapter=adapter)
    assert adapter.stop_calls == []
    assert phase2.status(run)["state"] == phase2.AWAITING_NATIVE_SETUP


def _drift_historical_profile(run):
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    profile = Path(manifest["profile"]["path"])
    profile.write_text("{}", encoding="utf-8")


def _rewrite_phase2_events(run, mutate):
    path = run / "phase2-events.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    previous = None
    for event in value["events"]:
        mutate(event)
        event["previous_event_sha256"] = previous
        event["event_sha256"] = phase2._digest({
            key: item for key, item in event.items()
            if key != "event_sha256"
        })
        previous = event["event_sha256"]
    path.write_text(json.dumps(value), encoding="utf-8")
    state = phase2._state_from_event(value["events"][-1])
    (run / "phase2-state.json").write_text(
        json.dumps(state), encoding="utf-8")


def test_historical_source_drift_allows_only_verified_owned_cleanup(tmp_path):
    _, run = _fixture(tmp_path)
    adapter = FakeProcessAdapter()
    _start(run, _authorize(run), adapter)
    immutable = {
        name: (run / name).read_bytes()
        for name in ("manifest.json", "seal.json", "events.json", "state.json")
    }
    _drift_historical_profile(run)

    with pytest.raises(phase1.OfflineBlocked, match="PROFILE"):
        phase2.continue_after_native_setup(
            run, clock=lambda: NOW, process_adapter=adapter,
            readiness_timeout=1)
    with pytest.raises(phase1.OfflineBlocked, match="PROFILE"):
        phase2.stop(run, clock=lambda: NOW, process_adapter=adapter)

    result = phase2.stop_owned_stale_run_for_cleanup(
        run, clock=lambda: NOW, process_adapter=adapter)
    assert result["state"] == phase2.STOPPED
    assert len(adapter.stop_calls) == 1
    assert all((run / name).read_bytes() == raw
               for name, raw in immutable.items())
    assert all(result[name] is False for name in (
        "paper_execution_enabled", "live_execution_allowed",
        "external_order_authority", "broker_live_order_authority",
        "ninjatrader_control_authority"))


def test_historical_windows_cleanup_uses_sealed_report_directory(
        tmp_path, monkeypatch):
    _, run = _fixture(tmp_path)
    start_adapter = FakeProcessAdapter()
    _start(run, _authorize(run), start_adapter)
    _drift_historical_profile(run)

    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    ownership = phase2._load_phase2(run)[0]["ownership"]
    report_directory = Path(
        manifest["targets"]["supervisor_report_directory"])
    report_directory.mkdir(parents=True)
    expected_launcher = phase1._expected_future_command(manifest)
    separator = expected_launcher.index("--")
    phase1._atomic_json(report_directory / "supervisor-start.json", {
        "schema": phase2.supervisor.SCHEMA,
        "run_id": manifest["run_id"],
        "supervisor_pid": ownership["pid"],
        "supervisor_identity": ownership["identity"],
        "spawn_challenge_sha256": ownership["spawn_challenge_sha256"],
        "command": expected_launcher[separator + 1:],
    })
    phase1._atomic_json(
        report_directory / "external-shutdown-result.json", {
            "schema": phase2.supervisor.REPORT_SCHEMA,
            "run_id": manifest["run_id"],
            "supervisor_pid": ownership["pid"],
            "controlled_stop_requested": True,
            "run_scoped_process_count": 0,
            "run_scoped_ports_open": 0,
            "job_membership_remains": 0,
            "cleanup_evidence_status": "PASS",
            "child_cleanup_confirmed": True,
        })
    monkeypatch.setattr(
        phase2.supervisor, "_pid_identity",
        lambda pid: tuple(ownership["identity"]))

    class ExitedAfterRequest(phase2.WindowsProcessAdapter):
        def matches(self, candidate):
            return False

    result = phase2.stop_owned_stale_run_for_cleanup(
        run, clock=lambda: NOW, process_adapter=ExitedAfterRequest())

    assert result["state"] == phase2.STOPPED
    assert Path(manifest["targets"]["supervisor_stop_request"]).is_file()
    assert all(result[name] is False for name in (
        "paper_execution_enabled", "live_execution_allowed",
        "external_order_authority", "broker_live_order_authority",
        "ninjatrader_control_authority"))


@pytest.mark.parametrize("value", (
    None,
    "",
    "relative/run/supervisor",
))
def test_historical_cleanup_report_directory_must_be_absolute(value):
    manifest = {"run_id": "20261008T002941Z-oneclick-ff240a7dc948",
                "targets": {"supervisor_report_directory": value}}
    with pytest.raises(phase2.Phase2Blocked,
                       match="HISTORICAL_REPORT_PATH_INVALID"):
        phase2._historical_supervisor_report_directory(manifest)


def test_historical_cleanup_report_directory_must_be_run_scoped(tmp_path):
    manifest = {"run_id": "20261008T002941Z-oneclick-ff240a7dc948",
                "targets": {"supervisor_report_directory": str(
                    (tmp_path / "different-run" / "supervisor").resolve())}}
    with pytest.raises(phase2.Phase2Blocked,
                       match="HISTORICAL_REPORT_PATH_INVALID"):
        phase2._historical_supervisor_report_directory(manifest)


def test_historical_cleanup_can_terminalize_proven_prior_exit(tmp_path):
    _, run = _fixture(tmp_path)
    start_adapter = FakeProcessAdapter()
    _start(run, _authorize(run), start_adapter)
    _drift_historical_profile(run)

    class AlreadyExited(FakeProcessAdapter):
        def __init__(self):
            super().__init__(running=False)

        def verify_cleanup_ownership(self, **kwargs):
            return {
                "state": "ALREADY_EXITED",
                "shutdown": {
                    "run_id": kwargs["manifest"]["run_id"],
                    "supervisor_pid": kwargs["ownership"]["pid"],
                    "controlled_stop_requested": False,
                    "run_scoped_process_count": 0,
                    "run_scoped_ports_open": 0,
                    "job_membership_remains": 0,
                    "cleanup_evidence_status": "PASS",
                    "child_cleanup_confirmed": True,
                },
            }

        def stop(self, **kwargs):
            raise AssertionError("an exited process must never be stopped")

    adapter = AlreadyExited()
    result = phase2.stop_owned_stale_run_for_cleanup(
        run, clock=lambda: NOW, process_adapter=adapter)
    assert result["state"] == phase2.STOPPED
    assert adapter.stop_calls == []
    events = json.loads((run / "phase2-events.json").read_text())["events"]
    assert events[-1]["details"]["cleanup_basis"] == (
        "EXISTING_SHUTDOWN_REPORT")


@pytest.mark.parametrize("failure", ("pid_missing", "pid_reused"))
def test_historical_cleanup_pid_identity_failure_never_stops(
        tmp_path, failure):
    _, run = _fixture(tmp_path)
    adapter = FakeProcessAdapter()
    _start(run, _authorize(run), adapter)
    _drift_historical_profile(run)
    if failure == "pid_missing":
        adapter.running = False
    else:
        adapter.identity = [999, 999]

    with pytest.raises(phase2.Phase2Blocked, match="IDENTITY_MISMATCH"):
        phase2.stop_owned_stale_run_for_cleanup(
            run, clock=lambda: NOW, process_adapter=adapter)
    assert adapter.stop_calls == []
    assert phase2._load_phase2(run)[0]["state"] == (
        phase2.AWAITING_NATIVE_SETUP)


def test_historical_cleanup_requires_recorded_ownership(tmp_path):
    _, run = _fixture(tmp_path)
    adapter = FakeProcessAdapter()
    _start(run, _authorize(run), adapter)
    _drift_historical_profile(run)

    def remove_ownership(event):
        if event["state"] == phase2.AWAITING_NATIVE_SETUP:
            event["details"]["ownership"] = None

    _rewrite_phase2_events(run, remove_ownership)
    with pytest.raises(phase2.Phase2Blocked, match="OWNERSHIP_INVALID"):
        phase2.stop_owned_stale_run_for_cleanup(
            run, clock=lambda: NOW, process_adapter=adapter)
    assert adapter.stop_calls == []


def test_historical_cleanup_rejects_any_authority_true(tmp_path):
    _, run = _fixture(tmp_path)
    adapter = FakeProcessAdapter()
    _start(run, _authorize(run), adapter)
    _drift_historical_profile(run)

    def escalate(event):
        if event["state"] == phase2.AWAITING_NATIVE_SETUP:
            event["paper_execution_enabled"] = True

    _rewrite_phase2_events(run, escalate)
    with pytest.raises(phase2.Phase2Blocked, match="EVENT_CHAIN_INVALID"):
        phase2.stop_owned_stale_run_for_cleanup(
            run, clock=lambda: NOW, process_adapter=adapter)
    assert adapter.stop_calls == []


def test_historical_cleanup_rejects_command_identity_drift(tmp_path):
    _, run = _fixture(tmp_path)
    adapter = FakeProcessAdapter()
    _start(run, _authorize(run), adapter)
    _drift_historical_profile(run)

    def forge_command(event):
        ownership = event.get("details", {}).get("ownership")
        if ownership is not None:
            ownership["command_sha256"] = "f" * 64

    _rewrite_phase2_events(run, forge_command)
    with pytest.raises(phase2.Phase2Blocked,
                       match="COMMAND_IDENTITY_MISMATCH"):
        phase2.stop_owned_stale_run_for_cleanup(
            run, clock=lambda: NOW, process_adapter=adapter)
    assert adapter.stop_calls == []


def test_canonical_history_is_unchanged_by_start_and_stop(tmp_path):
    _, run = _fixture(tmp_path)
    history = tmp_path / "canonical-history.sqlite"
    history.write_bytes(b"142 canonical signals;0 duplicates;0 trades")
    before = sha256(history.read_bytes()).hexdigest()
    adapter = FakeProcessAdapter()
    _start(run, _authorize(run), adapter)
    phase2.stop(run, clock=lambda: NOW, process_adapter=adapter)
    assert sha256(history.read_bytes()).hexdigest() == before


def test_supervisor_stop_request_rejects_wrong_pid_identity(tmp_path):
    request = tmp_path / "stop.json"
    request.write_text(json.dumps({
        "schema": "arms.windows-runtime-stop-request.v1",
        "run_id": "run", "supervisor_pid": 123,
        "supervisor_identity": [1, 2],
    }), encoding="utf-8")
    from tools import windows_runtime_supervisor_v1 as supervisor
    with pytest.raises(RuntimeError, match="STOP_REQUEST_INVALID"):
        supervisor._controlled_stop_requested(
            request, run_id="run", supervisor_pid=123,
            supervisor_identity=(9, 9))
