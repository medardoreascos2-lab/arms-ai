"""Authorized One-Click Phase 2 process transition.

Phase 1 remains an inert plan builder. This module can consume only the exact
sealed supervisor command after an in-memory, one-shot authorization is bound
to the plan, profile, and native-capture digests. Process start never grants
PAPER, LIVE, external-order, broker-live, or NinjaTrader authority.
"""

import argparse
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
from secrets import compare_digest, token_bytes, token_urlsafe
import socket
import subprocess
import time
import urllib.request

from tools import arms_one_click_runtime_v1 as phase1
from tools import windows_runtime_supervisor_v1 as supervisor


EVENTS_SCHEMA = "arms.one-click-runtime-phase2-events.v1"
STATE_SCHEMA = "arms.one-click-runtime-phase2-state.v1"
EVENT_SCHEMA = "arms.one-click-runtime-phase2-event.v1"
PREPARED = phase1.PREPARED
AUTHORIZED = "AUTHORIZED_START"
STARTING = "STARTING"
RUNNING = "RUNNING_DISABLED"
STOPPING = "STOPPING"
STOPPED = "STOPPED"
FAILED = "FAILED_START"
REVOKED = "REVOKED"
AUTHORIZATION_TTL_SECONDS = 60
SUPERVISOR_SPAWN_CHALLENGE_ENV = (
    "ARMS_ONE_CLICK_SUPERVISOR_SPAWN_CHALLENGE")
PHASE2_SOURCE = "tools/arms_one_click_runtime_phase2_v1.py"
_EVENTS_NAME = "phase2-events.json"
_STATE_NAME = "phase2-state.json"
_LOCK_NAME = ".phase2-transition.lock"


class Phase2Blocked(RuntimeError):
    """Fail-closed Phase 2 refusal."""


@dataclass
class StartAuthorization:
    plan_sha256: str
    profile_sha256: str
    capture_spec_sha256: str
    issued_utc: datetime
    expires_utc: datetime
    issuer_pid: int
    _token: bytes = field(repr=False)
    consumed: bool = field(default=False, repr=False)

    def token_for_immediate_consumption(self):
        return self._token


def _now(clock=None):
    value = (clock or (lambda: datetime.now(timezone.utc)))()
    if type(value) is not datetime or value.tzinfo is None:
        raise Phase2Blocked("EXPLICIT_UTC_CLOCK_REQUIRED")
    value = value.astimezone(timezone.utc)
    if value.utcoffset() != timedelta(0):
        raise Phase2Blocked("EXPLICIT_UTC_CLOCK_REQUIRED")
    return value


def _utc(value):
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _digest(value):
    return sha256(phase1._canonical(value)).hexdigest()


def _phase2_event(*, run_id, sequence, timestamp, previous, transition,
                  state, bindings, details=None):
    event = {
        "schema": EVENT_SCHEMA,
        "run_id": run_id,
        "sequence": sequence,
        "timestamp_utc": timestamp,
        "previous_event_sha256": previous,
        "transition": transition,
        "state": state,
        "bindings": dict(bindings),
        "details": {} if details is None else details,
        "paper_execution_enabled": False,
        "live_execution_allowed": False,
        "external_order_authority": False,
        "broker_live_order_authority": False,
        "ninjatrader_control_authority": False,
    }
    event["event_sha256"] = _digest(event)
    return event


def _state_from_event(event):
    return {
        "schema": STATE_SCHEMA,
        "run_id": event["run_id"],
        "state": event["state"],
        "sequence": event["sequence"],
        "last_event_sha256": event["event_sha256"],
        "bindings": event["bindings"],
        "ownership": event["details"].get("ownership"),
        "paper_execution_enabled": False,
        "live_execution_allowed": False,
        "external_order_authority": False,
        "broker_live_order_authority": False,
        "ninjatrader_control_authority": False,
    }


def _load_phase2(directory):
    events_path = directory / _EVENTS_NAME
    state_path = directory / _STATE_NAME
    if not events_path.exists() and not state_path.exists():
        return None, []
    if not events_path.is_file() or not state_path.is_file():
        raise Phase2Blocked("PHASE2_EVIDENCE_INCOMPLETE")
    value, _ = phase1._read_json(events_path, EVENTS_SCHEMA)
    state, _ = phase1._read_json(state_path, STATE_SCHEMA)
    events = value.get("events")
    if type(events) is not list or not events:
        raise Phase2Blocked("PHASE2_EVENTS_REQUIRED")
    previous = None
    for sequence, event in enumerate(events, 1):
        unsigned = dict(event)
        digest = unsigned.pop("event_sha256", None)
        if (type(event) is not dict or event.get("schema") != EVENT_SCHEMA
                or event.get("sequence") != sequence
                or event.get("previous_event_sha256") != previous
                or digest != _digest(unsigned)
                or event.get("paper_execution_enabled") is not False
                or event.get("live_execution_allowed") is not False
                or event.get("external_order_authority") is not False
                or event.get("broker_live_order_authority") is not False
                or event.get("ninjatrader_control_authority") is not False):
            raise Phase2Blocked("PHASE2_EVENT_CHAIN_INVALID")
        previous = digest
    if state != _state_from_event(events[-1]):
        raise Phase2Blocked("PHASE2_STATE_PROJECTION_INVALID")
    return state, events


def _bindings(manifest, state):
    return {
        "plan_sha256": state["manifest_sha256"],
        "profile_sha256": manifest["profile"]["sha256"],
        "capture_spec_sha256": manifest["inputs"]["native_spec"]["sha256"],
    }


def _capture_spec_current(manifest, now):
    descriptor = manifest["inputs"]["native_spec"]
    raw, actual, size = phase1._hash_stable_file(
        descriptor["path"], descriptor["sha256"])
    if actual != descriptor["sha256"] or size != descriptor["bytes"]:
        raise Phase2Blocked("CAPTURE_SPEC_BINDING_INVALID")
    try:
        spec = json.loads(raw.decode("utf-8"))
        contract = spec["contract"]
        begin = datetime.fromisoformat(contract["valid_from"])
        end = datetime.fromisoformat(contract["valid_until"])
    except (UnicodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        raise Phase2Blocked("CAPTURE_SPEC_INVALID") from error
    if (begin.tzinfo is None or end.tzinfo is None
            or not begin <= now < end
            or not timedelta(0) < end - begin <= timedelta(days=14)):
        raise Phase2Blocked("CAPTURE_SPEC_EXPIRED_OR_NOT_CURRENT")
    for field_name in ("calendar_evidence_file", "loaded_calendar_evidence_file"):
        value = spec.get(field_name)
        if (type(value) is not str or not value.strip()
                or any(marker in value for marker in "<>{}")):
            raise Phase2Blocked("CAPTURE_SPEC_PATH_INVALID:" + field_name)
        evidence = Path(value)
        expected = spec.get(field_name.replace("_file", "_sha256"))
        _, digest, _ = phase1._hash_stable_file(evidence, expected)
        if digest != expected:
            raise Phase2Blocked("CAPTURE_SPEC_EVIDENCE_DRIFT:" + field_name)
    return descriptor["sha256"]


def _load_plan(run_directory, *, now, allow_runtime_targets=False,
               require_current_spec=True):
    directory, manifest, state, events, validated = phase1._load_and_verify(
        run_directory, allow_runtime_targets=allow_runtime_targets)
    if not validated["reviewed"]:
        raise Phase2Blocked("REVIEWED_PHASE1B_PLAN_REQUIRED")
    if PHASE2_SOURCE not in manifest["source_pins"]:
        raise Phase2Blocked("PHASE2_SOURCE_PIN_REQUIRED")
    if manifest["disabled_future_start_command"] != phase1._expected_future_command(
            manifest):
        raise Phase2Blocked("ARBITRARY_COMMAND_BLOCKED")
    if require_current_spec:
        _capture_spec_current(manifest, now)
    return directory, manifest, state, events, validated


def _transition(directory, manifest, bindings, *, state, transition, clock,
                details=None, expected_states=()):
    lock = directory / _LOCK_NAME
    acquired = False
    try:
        with lock.open("xb") as stream:
            acquired = True
            stream.write(b"phase2-transition\n")
            stream.flush()
            os.fsync(stream.fileno())
        current, events = _load_phase2(directory)
        current_state = PREPARED if current is None else current["state"]
        if expected_states and current_state not in expected_states:
            raise Phase2Blocked("PHASE2_TRANSITION_NOT_ALLOWED:" + current_state)
        if current is not None and current["bindings"] != bindings:
            raise Phase2Blocked("PHASE2_BINDING_DRIFT")
        event = _phase2_event(
            run_id=manifest["run_id"], sequence=len(events) + 1,
            timestamp=_utc(_now(clock)),
            previous=None if not events else events[-1]["event_sha256"],
            transition=transition, state=state, bindings=bindings,
            details=details)
        phase1._atomic_json(
            directory / _EVENTS_NAME,
            {"schema": EVENTS_SCHEMA, "events": [*events, event]})
        phase1._atomic_json(directory / _STATE_NAME, _state_from_event(event))
        return _state_from_event(event)
    finally:
        if acquired:
            lock.unlink(missing_ok=True)


def authorize_start(run_directory, *, clock=None, ttl_seconds=30,
                    token_factory=token_bytes):
    now = _now(clock)
    if (type(ttl_seconds) not in (int, float)
            or isinstance(ttl_seconds, bool)
            or not 0 < ttl_seconds <= AUTHORIZATION_TTL_SECONDS):
        raise Phase2Blocked("AUTHORIZATION_TTL_INVALID")
    directory, manifest, phase1_state, _, _ = _load_plan(
        run_directory, now=now)
    current, _ = _load_phase2(directory)
    if current is not None:
        raise Phase2Blocked("ONE_SHOT_AUTHORIZATION_ALREADY_ISSUED")
    bindings = _bindings(manifest, phase1_state)
    raw_token = token_factory(32)
    if type(raw_token) is not bytes or len(raw_token) < 32:
        raise Phase2Blocked("CRYPTOGRAPHIC_AUTHORIZATION_REQUIRED")
    authorization = StartAuthorization(
        **bindings, issued_utc=now,
        expires_utc=now + timedelta(seconds=ttl_seconds),
        issuer_pid=os.getpid(), _token=raw_token)
    _transition(
        directory, manifest, bindings, state=AUTHORIZED,
        transition="START_AUTHORIZED", clock=lambda: now,
        expected_states=(PREPARED,))
    return authorization


def _revoke(directory, manifest, bindings, reason, clock):
    _transition(
        directory, manifest, bindings, state=REVOKED,
        transition="START_AUTHORIZATION_REVOKED", clock=clock,
        details={"reason": reason}, expected_states=(AUTHORIZED,))


class WindowsProcessAdapter:
    @staticmethod
    def _verified_supervisor_ownership(*, report, manifest, challenge_sha256,
                                       command_sha256):
        pid = report.get("supervisor_pid")
        identity = report.get("supervisor_identity")
        if (report.get("run_id") != manifest["run_id"]
                or report.get("spawn_challenge_sha256") != challenge_sha256
                or type(pid) is not int or isinstance(pid, bool) or pid <= 0
                or type(identity) is not list or len(identity) != 2
                or any(type(value) is not int or isinstance(value, bool)
                       for value in identity)
                or not supervisor._pid_alive(pid, tuple(identity))):
            raise Phase2Blocked("SUPERVISOR_SPAWN_IDENTITY_MISMATCH")
        return {
            "pid": pid,
            "identity": identity,
            "command_sha256": command_sha256,
            "spawn_challenge_sha256": challenge_sha256,
        }

    def start(self, *, command, cwd, environment, run_directory, manifest):
        stdout_path = run_directory / "phase2-supervisor.stdout.log"
        stderr_path = run_directory / "phase2-supervisor.stderr.log"
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        challenge = token_urlsafe(48)
        challenge_sha256 = sha256(challenge.encode("utf-8")).hexdigest()
        child_environment = dict(environment)
        child_environment[SUPERVISOR_SPAWN_CHALLENGE_ENV] = challenge
        with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
            process = subprocess.Popen(
                list(command), cwd=cwd, env=child_environment,
                stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                creationflags=creationflags)
        child_environment.pop(SUPERVISOR_SPAWN_CHALLENGE_ENV, None)
        challenge = None
        command_sha256 = sha256(
            phase1._canonical(list(command))).hexdigest()
        report_path = (Path(manifest["targets"]["supervisor_report_directory"])
                       / "supervisor-start.json")
        deadline = time.monotonic() + 10
        last_error = None
        while time.monotonic() < deadline:
            try:
                report, _ = phase1._read_json(report_path, supervisor.SCHEMA)
                return self._verified_supervisor_ownership(
                    report=report, manifest=manifest,
                    challenge_sha256=challenge_sha256,
                    command_sha256=command_sha256)
            except (OSError, ValueError, TypeError, KeyError,
                    phase1.OfflineBlocked, Phase2Blocked) as error:
                last_error = error
                time.sleep(0.01)
        raise Phase2Blocked(
            "SUPERVISOR_PROCESS_IDENTITY_UNAVAILABLE") from last_error

    @staticmethod
    def _get_json(url):
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(url, timeout=2) as response:
            raw = response.read(4 * 1024 * 1024 + 1)
            if response.status != 200 or len(raw) > 4 * 1024 * 1024:
                raise Phase2Blocked("CONTROL_PLANE_RESPONSE_INVALID")
        value = json.loads(raw.decode("utf-8"))
        if type(value) is not dict:
            raise Phase2Blocked("CONTROL_PLANE_RESPONSE_INVALID")
        return value

    def wait_running(self, *, ownership, manifest, timeout_seconds):
        deadline = time.monotonic() + timeout_seconds
        ports = manifest["ports"]
        report_path = (Path(manifest["targets"]["supervisor_report_directory"])
                       / "supervisor-start.json")
        last_error = None
        while time.monotonic() < deadline:
            if not self.matches(ownership):
                raise Phase2Blocked("SUPERVISOR_EXITED_DURING_START")
            try:
                report, _ = phase1._read_json(
                    report_path, supervisor.SCHEMA)
                if (report.get("run_id") != manifest["run_id"]
                        or report.get("supervisor_pid") != ownership["pid"]
                        or report.get("supervisor_identity")
                        != ownership["identity"]
                        or report.get("spawn_challenge_sha256")
                        != ownership["spawn_challenge_sha256"]):
                    raise Phase2Blocked("SUPERVISOR_OWNERSHIP_MISMATCH")
                analysis = self._get_json(
                    f"http://127.0.0.1:{ports['backend']}/api/v2/market-analysis/health")
                with socket.create_connection(
                        ("127.0.0.1", ports["frontend"]), timeout=2):
                    pass
                paper = self._get_json(
                    f"http://127.0.0.1:{ports['paper']}/api/v2/backtesting/dashboard")
                snapshot = paper.get("paper_research")
                if type(snapshot) is not dict:
                    raise Phase2Blocked("PAPER_SNAPSHOT_INVALID")
                result = {
                    "paper_runtime_process_alive": True,
                    "analysis_runtime_process_alive": True,
                    "supervisor_health": "PASS",
                    "control_plane_observable": bool(analysis),
                    "paper_execution_enabled": snapshot.get(
                        "paper_execution_enabled"),
                    "live_execution_allowed": snapshot.get(
                        "live_execution_allowed"),
                    "external_order_authority": False,
                    "broker_live_order_authority": False,
                    "ninjatrader_touched": False,
                }
                return result
            except (OSError, ValueError, TypeError, KeyError,
                    json.JSONDecodeError, Phase2Blocked) as error:
                last_error = error
                time.sleep(0.1)
        raise Phase2Blocked("RUNTIME_START_READINESS_TIMEOUT") from last_error

    def matches(self, ownership):
        return supervisor._pid_alive(
            ownership["pid"], tuple(ownership["identity"]))

    @staticmethod
    def _cleanup_report_passes(result, *, run_id, controlled_stop):
        return (
            type(result) is dict
            and result.get("run_id") == run_id
            and result.get("controlled_stop_requested") is controlled_stop
            and result.get("run_scoped_process_count") == 0
            and result.get("run_scoped_ports_open") == 0
            and result.get("job_membership_remains") == 0
            and result.get("cleanup_evidence_status") == "PASS"
            and result.get("child_cleanup_confirmed") is True
        )

    def stop(self, *, ownership, manifest, timeout_seconds=30):
        if not self.matches(ownership):
            raise Phase2Blocked("OWNED_SUPERVISOR_IDENTITY_MISMATCH")
        report_directory = Path(
            manifest["targets"]["supervisor_report_directory"])
        start, _ = phase1._read_json(
            report_directory / "supervisor-start.json", supervisor.SCHEMA)
        expected_launcher = phase1._expected_future_command(manifest)
        separator = expected_launcher.index("--")
        if (start.get("run_id") != manifest["run_id"]
                or start.get("supervisor_pid") != ownership["pid"]
                or start.get("supervisor_identity") != ownership["identity"]
                or start.get("spawn_challenge_sha256")
                != ownership["spawn_challenge_sha256"]
                or start.get("command") != expected_launcher[separator + 1:]):
            raise Phase2Blocked("OWNED_SUPERVISOR_EVIDENCE_MISMATCH")
        request = {
            "schema": "arms.windows-runtime-stop-request.v1",
            "run_id": manifest["run_id"],
            "supervisor_pid": ownership["pid"],
            "supervisor_identity": ownership["identity"],
        }
        phase1._atomic_json(manifest["targets"]["supervisor_stop_request"], request,
                            exclusive=True)
        deadline = time.monotonic() + timeout_seconds
        shutdown_path = report_directory / "external-shutdown-result.json"
        while time.monotonic() < deadline:
            if not self.matches(ownership) and shutdown_path.is_file():
                result, _ = phase1._read_json(
                    shutdown_path, supervisor.REPORT_SCHEMA)
                if self._cleanup_report_passes(
                        result, run_id=manifest["run_id"],
                        controlled_stop=True):
                    return result
            time.sleep(0.05)
        raise Phase2Blocked("CONTROLLED_STOP_TIMEOUT")


def _validate_running_result(result):
    expected = {
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
    if type(result) is not dict or any(result.get(key) != value
                                       for key, value in expected.items()):
        raise Phase2Blocked("RUNNING_DISABLED_SAFETY_POSTCONDITION_FAILED")


def start_authorized(run_directory, authorization, supplied_token, *,
                     clock=None, process_adapter=None, readiness_timeout=960):
    now = _now(clock)
    directory, manifest, phase1_state, _, _ = _load_plan(
        run_directory, now=now)
    bindings = _bindings(manifest, phase1_state)
    current, _ = _load_phase2(directory)
    if current is None or current["state"] != AUTHORIZED:
        raise Phase2Blocked("AUTHORIZED_START_REQUIRED")
    if type(authorization) is not StartAuthorization:
        raise Phase2Blocked("PROCESS_SCOPED_AUTHORIZATION_REQUIRED")
    if authorization.consumed:
        raise Phase2Blocked("START_AUTHORIZATION_ALREADY_CONSUMED")
    authorization.consumed = True
    reason = None
    if authorization.issuer_pid != os.getpid():
        reason = "START_AUTHORIZATION_PROCESS_MISMATCH"
    elif now > authorization.expires_utc:
        reason = "START_AUTHORIZATION_EXPIRED"
    elif type(supplied_token) is not bytes or not compare_digest(
            supplied_token, authorization._token):
        reason = "START_AUTHORIZATION_TOKEN_INVALID"
    elif any(getattr(authorization, key) != value
             for key, value in bindings.items()):
        reason = "START_AUTHORIZATION_BINDING_MISMATCH"
    if reason is not None:
        _revoke(directory, manifest, bindings, reason, lambda: now)
        raise Phase2Blocked(reason)

    command = manifest["disabled_future_start_command"]
    if command != phase1._expected_future_command(manifest):
        _revoke(directory, manifest, bindings, "ARBITRARY_COMMAND_BLOCKED",
                lambda: now)
        raise Phase2Blocked("ARBITRARY_COMMAND_BLOCKED")
    _transition(
        directory, manifest, bindings, state=STARTING,
        transition="PROCESS_STARTING", clock=lambda: now,
        expected_states=(AUTHORIZED,))
    adapter = process_adapter or WindowsProcessAdapter()
    environment = dict(os.environ)
    for name, value in manifest["runtime_environment"].items():
        environment[name] = value
    environment[manifest["admin_token"]["environment_name"]] = token_urlsafe(48)
    ownership = None
    try:
        ownership = adapter.start(
            command=command, cwd=phase1.REPO_ROOT, environment=environment,
            run_directory=directory, manifest=manifest)
        environment.pop(manifest["admin_token"]["environment_name"], None)
        _transition(
            directory, manifest, bindings, state=STARTING,
            transition="PROCESS_OWNERSHIP_RECORDED", clock=clock,
            details={"ownership": ownership}, expected_states=(STARTING,))
        result = adapter.wait_running(
            ownership=ownership, manifest=manifest,
            timeout_seconds=readiness_timeout)
        _validate_running_result(result)
        return _transition(
            directory, manifest, bindings, state=RUNNING,
            transition="RUNTIME_RUNNING_DISABLED", clock=clock,
            details={"ownership": ownership, "readiness": result},
            expected_states=(STARTING,))
    except BaseException as error:
        environment.pop(manifest["admin_token"]["environment_name"], None)
        if ownership is not None:
            try:
                adapter.stop(ownership=ownership, manifest=manifest)
            except BaseException:
                pass
        current, _ = _load_phase2(directory)
        if current is not None and current["state"] == STARTING:
            _transition(
                directory, manifest, bindings, state=FAILED,
                transition="RUNTIME_START_FAILED", clock=clock,
                details={"reason": type(error).__name__},
                expected_states=(STARTING,))
        raise


def start(run_directory, *, clock=None, process_adapter=None,
          readiness_timeout=960):
    authorization = authorize_start(run_directory, clock=clock)
    return start_authorized(
        run_directory, authorization,
        authorization.token_for_immediate_consumption(), clock=clock,
        process_adapter=process_adapter, readiness_timeout=readiness_timeout)


def status(run_directory):
    directory = Path(run_directory).resolve(strict=True)
    state, events = _load_phase2(directory)
    if state is None:
        phase1_status = phase1.status(directory)
        return {
            "schema": STATE_SCHEMA, "run_id": phase1_status["run_id"],
            "state": phase1_status["state"], "sequence": 0,
            "event_count": 0, "paper_execution_enabled": False,
            "live_execution_allowed": False,
            "external_order_authority": False,
            "broker_live_order_authority": False,
            "ninjatrader_control_authority": False,
        }
    _, manifest, phase1_state, _, _ = _load_plan(
        directory, now=_now(), allow_runtime_targets=True,
        require_current_spec=False)
    if state["bindings"] != _bindings(manifest, phase1_state):
        raise Phase2Blocked("PHASE2_BINDING_DRIFT")
    return {**state, "event_count": len(events)}


def stop(run_directory, *, clock=None, process_adapter=None):
    now = _now(clock)
    directory, manifest, phase1_state, _, _ = _load_plan(
        run_directory, now=now, allow_runtime_targets=True,
        require_current_spec=False)
    bindings = _bindings(manifest, phase1_state)
    state, _ = _load_phase2(directory)
    if state is None:
        phase1.stop(directory, clock=clock)
        return status(directory)
    if state["state"] == STOPPED:
        return status(directory)
    if state["state"] != RUNNING or type(state.get("ownership")) is not dict:
        raise Phase2Blocked("ONLY_RUNNING_DISABLED_CAN_CONTROLLED_STOP")
    adapter = process_adapter or WindowsProcessAdapter()
    if not adapter.matches(state["ownership"]):
        raise Phase2Blocked("OWNED_SUPERVISOR_IDENTITY_MISMATCH")
    ownership = state["ownership"]
    _transition(
        directory, manifest, bindings, state=STOPPING,
        transition="CONTROLLED_STOPPING", clock=lambda: now,
        details={"ownership": ownership}, expected_states=(RUNNING,))
    adapter.stop(ownership=ownership, manifest=manifest)
    _transition(
        directory, manifest, bindings, state=STOPPED,
        transition="CONTROLLED_STOPPED", clock=clock,
        expected_states=(STOPPING,))
    return status(directory)


def _print(value):
    print(json.dumps(value, sort_keys=True, indent=2, allow_nan=False))


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Authorized One-Click Phase 2 runtime transition")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("start", "status", "stop"):
        child = commands.add_parser(name)
        child.add_argument("--run", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "start":
            result = start(args.run)
        elif args.command == "stop":
            result = stop(args.run)
        else:
            result = status(args.run)
        _print(result)
        return 0
    except (Phase2Blocked, phase1.OfflineBlocked, OSError, ValueError,
            TypeError, KeyError, AttributeError) as error:
        _print({
            "schema": STATE_SCHEMA, "state": phase1.BLOCKED,
            "blocking_reasons": [str(error)],
            "paper_execution_enabled": False,
            "live_execution_allowed": False,
            "external_order_authority": False,
            "broker_live_order_authority": False,
            "ninjatrader_control_authority": False,
        })
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
