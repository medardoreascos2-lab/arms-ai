"""Deterministic single-command One Click operator orchestration tests."""

import json
from pathlib import Path

import pytest

from tools import arms_one_click_operator_v1 as operator
from tools import arms_one_click_runtime_phase2_v1 as phase2
from tools import arms_one_click_runtime_phase3_v1 as phase3
from tools import arms_one_click_runtime_v1 as phase1


RUN_ID = "20261007T120000Z-oneclick-123456789abc"
RUNTIME_ID = "11111111-2222-4333-8444-555555555555"


def zero(value):
    return {**value, **operator.ZERO_AUTHORITY}


class FakeServices:
    def __init__(self, tmp_path, *, fail=None, ports=None):
        self.tmp_path = tmp_path
        self.fail = fail
        self.ports = ports or {54920: set(), 54921: set(), 54922: set()}
        self.calls = []
        self.stale = {}
        self.stop_calls = []
        self.observed_internal_token = None
        self.observed_internal_sha = None
        self.receipt_detected = False
        self.hello_detected = False

    def _call(self, name):
        self.calls.append(name)
        if self.fail == name:
            raise RuntimeError(name.upper() + "_FAILED")

    def validate_profile(self, profile):
        self._call("precheck")
        return {
            "profile": {
                "execution_authority": False, "live_authority": False,
                "external_order_authority": False,
                "future_runtime_execution_enabled": False,
            },
            "profile_sha256": "a" * 64,
            "parents": {"runtime_parent": self.tmp_path / "native"},
            "ports": {"backend": 54920, "frontend": 54921, "paper": 54922},
        }

    @staticmethod
    def branch():
        return operator.EXPECTED_BRANCH

    def port_states(self, ports):
        assert set(ports) == {54920, 54921, 54922}
        return self.ports

    def phase2_state(self, run):
        if Path(run).name in self.stale:
            return self.stale[Path(run).name]
        if "phase2" in self.calls:
            return zero({
                "state": phase2.AWAITING_NATIVE_SETUP,
                "ownership": {"pid": 123, "identity": [1, 2]},
            })
        return None

    @staticmethod
    def ownership_matches(ownership):
        return ownership.get("owned", False)

    def stop(self, run):
        self.stop_calls.append(Path(run).name)
        return zero({"state": phase2.STOPPED})

    def prepare_phase1(self, profile, workspace):
        self._call("phase1")
        run = Path(workspace) / RUN_ID
        run.mkdir(parents=True, exist_ok=False)
        return {
            "state": phase1.PREPARED, "run_id": RUN_ID,
            "run_directory": str(run), "profile_status": "VALID",
            "source_binding": phase1.SOURCE_BINDING_PASS,
        }

    def audit_phase1(self, run):
        return {"status": "PASS"}

    def start_phase2(self, run):
        self._call("phase2")
        runtime = self.tmp_path / "native" / RUNTIME_ID
        runtime.mkdir(parents=True)
        return zero({
            "state": phase2.AWAITING_NATIVE_SETUP,
            "native_setup": {
                "native_runtime_id": RUNTIME_ID,
                "runtime_directory": str(runtime),
                "live_inbox": str(runtime / "inbox"),
                "catchup_output_directory": str(runtime / "chart-catchup"),
                "request_sha256": "b" * 64, "claim_sha256": "c" * 64,
            },
        })

    def prepare_phase3(self, run, runtime):
        self._call("phase3_prepare")
        binding = (Path(runtime).parent.parent
                   / phase3._BINDING_DIRECTORY_NAME / phase3._BINDING_FILE_NAME)
        return zero({
            "state": phase3.PREPARED, "apply_count": 0,
            "native_runtime_id": RUNTIME_ID,
            "handoff": {
                "chart_contract": dict(phase3._CHART),
                "native_binding": {"control_file": str(binding)},
                "settings": {
                    "ArmsReadOnlyMarketV1": {
                        "OneClickBindingFile": str(binding)},
                    "ArmsChartCatchupBridgeV1": {
                        "OneClickBindingFile": str(binding)},
                },
            },
        })

    def authorize_phase3(self, run):
        self._call("authorize")
        return zero({
            "state": phase3.AUTHORIZED, "apply_limit": 1,
            "authorization_token": "secret-token",
            "handoff_file_sha256": "d" * 64,
        })

    def begin_apply(self, run, token, handoff_sha, callback):
        self._call("begin_apply")
        self.observed_internal_token = token
        self.observed_internal_sha = handoff_sha
        callback(zero({"state": phase3.APPLYING, "apply_count": 1}))
        self.receipt_detected = True
        self.hello_detected = True
        return zero({"state": phase3.COMPLETE, "apply_count": 1})

    def continue_phase2(self, run):
        self._call("continue")
        return zero({"state": phase2.RUNNING})


def execute(tmp_path, services=None):
    profile = tmp_path / "profile.json"
    profile.write_text("{}", encoding="utf-8")
    workspace = tmp_path / "workspace"
    messages = []
    result = operator.run(
        profile, workspace=workspace,
        services=services or FakeServices(tmp_path), output=messages.append)
    return result, messages


def test_full_happy_path_is_one_command_and_one_apply_instruction(tmp_path):
    services = FakeServices(tmp_path)
    result, messages = execute(tmp_path, services)
    transcript = "\n".join(messages)
    assert result["state"] == phase2.RUNNING
    assert result["run_id"] == RUN_ID
    assert result["native_runtime_id"] == RUNTIME_ID
    assert result["apply_count"] == 1
    assert services.calls == [
        "precheck", "phase1", "phase2", "phase3_prepare", "authorize",
        "begin_apply", "continue"]
    assert services.observed_internal_token == "secret-token"
    assert services.observed_internal_sha == "d" * 64
    assert services.receipt_detected is True
    assert services.hello_detected is True
    assert transcript.count("AHORA SI PRESIONA APPLY") == 1
    assert transcript.index(operator.DO_NOT_APPLY) < transcript.index(
        "AHORA SI PRESIONA APPLY")
    assert transcript.index(operator.APPLY_DETECTED) > transcript.index(
        "AHORA SI PRESIONA APPLY")
    assert "HANDOFF_COMPLETE=PASS" in transcript
    assert "FINAL_STATE=RUNNING_DISABLED" in transcript
    assert "secret-token" not in transcript
    assert "d" * 64 not in transcript
    assert all(result[key] is False for key in operator.ZERO_AUTHORITY)


def test_time_wait_is_harmless_but_listening_fails_closed(tmp_path):
    time_wait = FakeServices(
        tmp_path, ports={54920: {"TIME_WAIT"}, 54921: set(), 54922: set()})
    result, _ = execute(tmp_path, time_wait)
    assert result["state"] == phase2.RUNNING

    other = tmp_path / "listening"
    other.mkdir()
    listening = FakeServices(
        other, ports={54920: {"LISTENING"}, 54921: {"TIME_WAIT"}, 54922: set()})
    result, messages = execute(other, listening)
    assert result["state"] == phase1.BLOCKED
    assert result["failed_stage"] == "PRECHECK"
    assert result["primary_reason"] == "REQUIRED_PORT_LISTENING:54920"
    assert "phase1" not in listening.calls
    assert "AHORA SI PRESIONA APPLY" not in "\n".join(messages)


@pytest.mark.parametrize(("mutation", "reason"), [
    (lambda value: value.update(claim_sha256="0" * 64),
     "FIXED_BINDING_STATE_INVALID"),
    (lambda value: value.update(claim_json=json.dumps({
        **json.loads(value["claim_json"]), "live_execution_allowed": True},
        sort_keys=True, separators=(",", ":"))),
     "FIXED_BINDING_STATE_INVALID"),
])
def test_invalid_existing_active_binding_fails_before_phase1(
        tmp_path, mutation, reason):
    control = tmp_path / phase3._BINDING_DIRECTORY_NAME
    control.mkdir()
    claim = {"expires_utc": "2020-01-01T00:00:00Z", **phase3._ZERO_AUTHORITY}
    claim_json = json.dumps(claim, sort_keys=True, separators=(",", ":"))
    value = {
        "schema": phase3.BINDING_CONTROL_SCHEMA, "state": "ACTIVE",
        "claim_json": claim_json,
        "claim_sha256": operator.sha256(claim_json.encode("utf-8")).hexdigest(),
    }
    mutation(value)
    (control / phase3._BINDING_FILE_NAME).write_text(
        json.dumps(value), encoding="utf-8")
    services = FakeServices(tmp_path)
    result, _ = execute(tmp_path, services)
    assert result["state"] == phase1.BLOCKED
    assert result["primary_reason"] == reason
    assert "phase1" not in services.calls


def test_stale_owned_run_uses_only_verified_phase2_stop(tmp_path):
    workspace = tmp_path / "workspace"
    stale_id = "20261007T110000Z-oneclick-aaaaaaaaaaaa"
    (workspace / stale_id).mkdir(parents=True)
    services = FakeServices(tmp_path, fail="phase1")
    services.stale[stale_id] = zero({
        "state": phase2.AWAITING_NATIVE_SETUP,
        "ownership": {"pid": 9, "identity": [1, 2], "owned": True},
    })
    result, _ = execute(tmp_path, services)
    assert result["state"] == phase1.BLOCKED
    assert services.stop_calls == [stale_id]
    assert result["run_id"] is None


def test_unrelated_or_uncontrollable_process_is_never_stopped(tmp_path):
    workspace = tmp_path / "workspace"
    stale_id = "20261007T110000Z-oneclick-bbbbbbbbbbbb"
    (workspace / stale_id).mkdir(parents=True)
    services = FakeServices(tmp_path, fail="phase1")
    services.stale[stale_id] = zero({
        "state": phase2.FAILED,
        "ownership": {"pid": 9, "identity": [1, 2], "owned": False},
    })
    result, _ = execute(tmp_path, services)
    assert result["state"] == phase1.BLOCKED
    assert services.stop_calls == []

    owned = tmp_path / "owned"
    owned.mkdir()
    workspace = owned / "workspace"
    (workspace / stale_id).mkdir(parents=True)
    services = FakeServices(owned)
    services.stale[stale_id] = zero({
        "state": phase2.FAILED,
        "ownership": {"pid": 9, "identity": [1, 2], "owned": True},
    })
    result, _ = execute(owned, services)
    assert result["primary_reason"].startswith(
        "CONFLICTING_RUNTIME_NOT_SAFELY_STOPPABLE")
    assert services.stop_calls == []


@pytest.mark.parametrize(("failure", "stage"), [
    ("precheck", "PRECHECK"),
    ("phase1", "PHASE1"),
    ("phase2", "PHASE2_START"),
    ("phase3_prepare", "PHASE3_PREPARE"),
    ("authorize", "AUTHORIZATION"),
    ("begin_apply", "APPLY_AND_HANDOFF"),
    ("continue", "PHASE2_CONTINUE"),
])
def test_each_failure_stops_advancement_and_writes_one_diagnostic(
        tmp_path, failure, stage):
    services = FakeServices(tmp_path, fail=failure)
    result, messages = execute(tmp_path, services)
    transcript = "\n".join(messages)
    assert result["state"] == phase1.BLOCKED
    assert result["failed_stage"] == stage
    assert Path(result["diagnostic_report"]).is_file()
    assert transcript.count("ARMS AI ONE CLICK — BLOCKED") == 1
    assert transcript.count("AHORA SI PRESIONA APPLY") <= 1
    if failure not in {"begin_apply", "continue"}:
        assert "AHORA SI PRESIONA APPLY" not in transcript
    assert services.calls.count("phase1") <= 1
    assert all(result[key] is False for key in operator.ZERO_AUTHORITY)


def test_bad_applying_postcondition_never_prints_apply_instruction(tmp_path):
    services = FakeServices(tmp_path)

    def bad_begin(run, token, handoff_sha, callback):
        services._call("begin_apply")
        callback(zero({"state": phase3.AUTHORIZED, "apply_count": 0}))

    services.begin_apply = bad_begin
    result, messages = execute(tmp_path, services)
    assert result["state"] == phase1.BLOCKED
    assert "AHORA SI PRESIONA APPLY" not in "\n".join(messages)


def test_phase3_fixed_binding_path_must_be_exact(tmp_path):
    services = FakeServices(tmp_path)
    original = services.prepare_phase3

    def wrong_binding(run, runtime):
        result = original(run, runtime)
        result["handoff"]["settings"]["ArmsReadOnlyMarketV1"][
            "OneClickBindingFile"] = str(tmp_path / "foreign-binding.json")
        return result

    services.prepare_phase3 = wrong_binding
    result, messages = execute(tmp_path, services)
    assert result["state"] == phase1.BLOCKED
    assert result["primary_reason"] == "FIXED_BINDING_PATH_MISMATCH"
    assert "authorize" not in services.calls
    assert "AHORA SI PRESIONA APPLY" not in "\n".join(messages)


def test_handoff_failure_does_not_continue_or_request_second_apply(tmp_path):
    services = FakeServices(tmp_path)

    def incomplete(run, token, handoff_sha, callback):
        services._call("begin_apply")
        callback(zero({"state": phase3.APPLYING, "apply_count": 1}))
        return zero({"state": phase3.FAILED, "apply_count": 1})

    services.begin_apply = incomplete
    result, messages = execute(tmp_path, services)
    transcript = "\n".join(messages)
    assert result["state"] == phase1.BLOCKED
    assert "continue" not in services.calls
    assert transcript.count("AHORA SI PRESIONA APPLY") == 1
    assert operator.APPLY_DETECTED not in transcript


def test_native_hello_timeout_stops_without_retrying_apply(tmp_path):
    services = FakeServices(tmp_path)

    def timeout(run, token, handoff_sha, callback):
        services._call("begin_apply")
        callback(zero({"state": phase3.APPLYING, "apply_count": 1}))
        raise phase3.Phase3Blocked("NATIVE_HELLO_TIMEOUT")

    services.begin_apply = timeout
    result, messages = execute(tmp_path, services)
    transcript = "\n".join(messages)
    assert result["state"] == phase1.BLOCKED
    assert result["primary_reason"] == "NATIVE_HELLO_TIMEOUT"
    assert services.calls.count("phase1") == 1
    assert services.calls.count("begin_apply") == 1
    assert "continue" not in services.calls
    assert transcript.count("AHORA SI PRESIONA APPLY") == 1
    assert operator.APPLY_DETECTED not in transcript


def test_strict_waiting_and_gap_guards_are_not_changed():
    startup = Path("backend/market_data/analysis_startup_v1.py").read_text(
        encoding="utf-8")
    phase2_source = Path("tools/arms_one_click_runtime_phase2_v1.py").read_text(
        encoding="utf-8")
    assert "require(self.phase == 'VERIFYING_WAITING', 'WAITING_GATE_ORDER')" in startup
    assert '"UNEXPECTED_DATA_GAP"' in phase2_source
