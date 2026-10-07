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


NOW = datetime(2026, 10, 6, 18, 30, tzinfo=timezone.utc)


class FakeProcessAdapter:
    def __init__(self, *, running=True, identity=(101, 202)):
        self.running = running
        self.identity = list(identity)
        self.start_calls = []
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
        }

    def wait_running(self, **_kwargs):
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


def test_prepared_offline_cannot_spawn_without_authorization(tmp_path):
    _, run = _fixture(tmp_path)
    adapter = FakeProcessAdapter()
    with pytest.raises(phase2.Phase2Blocked, match="AUTHORIZED_START_REQUIRED"):
        phase2.start_authorized(
            run, object(), b"x" * 32, clock=lambda: NOW,
            process_adapter=adapter)
    assert adapter.start_calls == []


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


def test_valid_start_transitions_through_starting_to_running_disabled(tmp_path):
    fixture, run = _fixture(tmp_path)
    authorization = _authorize(run)
    adapter = FakeProcessAdapter()
    result = _start(run, authorization, adapter)
    assert result["state"] == phase2.RUNNING
    events = json.loads((run / "phase2-events.json").read_text())["events"]
    assert [event["state"] for event in events] == [
        phase2.AUTHORIZED, phase2.STARTING, phase2.STARTING, phase2.RUNNING]
    assert all(event["paper_execution_enabled"] is False for event in events)
    assert all(event["live_execution_allowed"] is False for event in events)
    assert all(event["external_order_authority"] is False for event in events)
    assert all(event["ninjatrader_control_authority"] is False for event in events)
    command = adapter.start_calls[0]["command"]
    assert command == json.loads((run / "manifest.json").read_text())[
        "disabled_future_start_command"]
    assert command[0] == str(Path(fixture.profile["python_path"]).resolve())


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
    with pytest.raises(phase2.Phase2Blocked, match="SAFETY_POSTCONDITION"):
        _start(run, authorization, adapter)
    assert adapter.stop_calls
    assert phase2.status(run)["state"] == phase2.FAILED


def test_controlled_stop_targets_only_exact_owned_process(tmp_path):
    _, run = _fixture(tmp_path)
    adapter = FakeProcessAdapter()
    _start(run, _authorize(run), adapter)
    result = phase2.stop(run, clock=lambda: NOW, process_adapter=adapter)
    assert result["state"] == phase2.STOPPED
    assert len(adapter.stop_calls) == 1
    assert adapter.stop_calls[0]["ownership"]["pid"] == 43210


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
    assert phase2.status(run)["state"] == phase2.RUNNING


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
