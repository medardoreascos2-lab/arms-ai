"""Single-command, operator-assisted ARMS One Click orchestration.

This command composes the sealed Phase 1/2/3 APIs.  It has no GUI control,
NinjaTrader control, PAPER execution, LIVE execution, or order authority.
"""

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

from tools import arms_one_click_runtime_v1 as phase1
from tools import arms_one_click_runtime_phase2_v1 as phase2
from tools import arms_one_click_runtime_phase3_v1 as phase3


SCHEMA = "arms.one-click-operator.v1"
DIAGNOSTIC_SCHEMA = "arms.one-click-operator-diagnostic.v1"
EXPECTED_BRANCH = "refactor/backend-architecture"
SOURCE_NAME = "tools/arms_one_click_operator_v1.py"
ZERO_AUTHORITY = {
    "paper_execution_enabled": False,
    "live_execution_allowed": False,
    "external_order_authority": False,
    "broker_live_order_authority": False,
    "ninjatrader_control_authority": False,
}
APPLY_BANNER = (
    "============================================================\n"
    "ARMS AI — OPERATOR ACTION REQUIRED\n"
    "AHORA SI PRESIONA APPLY EN NINJATRADER — UNA SOLA VEZ\n"
    "NO CAMBIES NINGUNA RUTA\n"
    "NO PRESIONES APPLY DOS VECES\n"
    "VUELVE A ESTA TERMINAL DESPUES DEL APPLY\n"
    "============================================================"
)
DO_NOT_APPLY = "DO NOT PRESS APPLY YET"
APPLY_DETECTED = "APPLY DETECTED — DO NOT PRESS APPLY AGAIN"
LOG_TAIL_BYTES = 16 * 1024


class OperatorBlocked(RuntimeError):
    """Fail-closed orchestration refusal."""

    def __init__(self, stage, reason):
        super().__init__(reason)
        self.stage = stage
        self.reason = reason


def _raise(stage, reason):
    raise OperatorBlocked(stage, reason)


def _read_optional_json(path):
    path = Path(path)
    if not path.is_file():
        return None
    try:
        if not 0 < path.stat().st_size <= phase1.MAX_JSON_BYTES:
            return {"error": "SIZE_OR_TYPE_INVALID"}
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        return {"error": type(error).__name__}


def _tail(path):
    path = Path(path)
    if not path.is_file():
        return None
    try:
        size = path.stat().st_size
        with path.open("rb") as stream:
            stream.seek(max(0, size - LOG_TAIL_BYTES))
            return stream.read(LOG_TAIL_BYTES).decode("utf-8", "replace")
    except OSError as error:
        return "UNAVAILABLE:" + type(error).__name__


def _bounded_inventory(root, suffix, limit=100):
    root = Path(root)
    if not root.is_dir():
        return {"files": [], "truncated": False}
    files = []
    for path in root.rglob("*" + suffix):
        if path.is_file():
            if len(files) == limit:
                return {"files": files, "truncated": True}
            files.append(str(path.relative_to(root)))
    return {"files": sorted(files), "truncated": False}


class OperatorServices:
    """Production adapters; tests replace this object deterministically."""

    def validate_profile(self, profile):
        return phase1._validate_profile(profile)

    def branch(self):
        result = subprocess.run(
            ["git", "branch", "--show-current"], cwd=phase1.REPO_ROOT,
            check=True, capture_output=True, text=True)
        return result.stdout.strip()

    def port_states(self, ports):
        if os.name != "nt":
            return {port: set() for port in ports}
        result = subprocess.run(
            ["netstat", "-ano", "-p", "tcp"], check=True,
            capture_output=True, text=True)
        observed = {port: set() for port in ports}
        for line in result.stdout.splitlines():
            columns = line.split()
            if len(columns) < 4 or columns[0].upper() != "TCP":
                continue
            try:
                port = int(columns[1].rsplit(":", 1)[1])
            except (ValueError, IndexError):
                continue
            if port in observed:
                observed[port].add(columns[3].upper())
        return observed

    def phase2_state(self, run):
        return phase2._load_phase2(run)[0]

    def ownership_matches(self, ownership):
        return phase2.WindowsProcessAdapter().matches(ownership)

    def stop(self, run):
        return phase2.stop(run)

    def prepare_phase1(self, profile, workspace):
        return phase1.prepare(profile, workspace=workspace)

    def audit_phase1(self, run):
        return phase1.audit(run)

    def start_phase2(self, run):
        authorization = phase2.authorize_start(run)
        return phase2.start_authorized(
            run, authorization,
            authorization.token_for_immediate_consumption())

    def prepare_phase3(self, run, runtime):
        return phase3.prepare_handoff(run, runtime)

    def authorize_phase3(self, run):
        return phase3.operator_authorization(run, ttl_seconds=60)

    def begin_apply(self, run, token, handoff_sha, callback):
        return phase3.begin_operator_apply(
            run, token, handoff_sha, on_apply_recorded=callback)

    def continue_phase2(self, run):
        return phase2.continue_after_native_setup(run)


def _binding_precheck(validated):
    parent = validated["parents"]["runtime_parent"].resolve(strict=False)
    path = parent.parent / phase3._BINDING_DIRECTORY_NAME / phase3._BINDING_FILE_NAME
    if not path.exists():
        return {"path": str(path), "state": "ABSENT"}
    value, _ = phase1._read_json(path, phase3.BINDING_CONTROL_SCHEMA)
    state = value.get("state")
    if state == "REVOKED":
        if any(value.get(key) is not False for key in phase3._ZERO_AUTHORITY):
            _raise("PRECHECK", "FIXED_BINDING_AUTHORITY_INVALID")
        return {"path": str(path), "state": state}
    if state != "ACTIVE":
        _raise("PRECHECK", "FIXED_BINDING_STATE_INVALID")
    try:
        if set(value) != {"schema", "state", "claim_json", "claim_sha256"}:
            _raise("PRECHECK", "FIXED_BINDING_STATE_INVALID")
        if (sha256(value["claim_json"].encode("utf-8")).hexdigest()
                != value["claim_sha256"]):
            _raise("PRECHECK", "FIXED_BINDING_STATE_INVALID")
        claim = json.loads(value["claim_json"])
        if (type(claim) is not dict
                or any(claim.get(key) is not False
                       for key in phase3._ZERO_AUTHORITY)):
            _raise("PRECHECK", "FIXED_BINDING_AUTHORITY_INVALID")
        expiry = phase3._parse_utc(
            claim["expires_utc"], "NATIVE_BINDING_TIME_INVALID")
    except OperatorBlocked:
        raise
    except (KeyError, TypeError, ValueError, AttributeError,
            json.JSONDecodeError) as error:
        raise OperatorBlocked("PRECHECK", "FIXED_BINDING_STATE_INVALID") from error
    if datetime.now(timezone.utc) <= expiry:
        _raise("PRECHECK", "FIXED_BINDING_ALREADY_ACTIVE")
    return {"path": str(path), "state": "EXPIRED_ACTIVE"}


def _reconcile_old_runs(workspace, services):
    results = []
    if not workspace.exists():
        return results
    if not workspace.is_dir():
        _raise("PRECHECK", "ONE_CLICK_WORKSPACE_INVALID")
    for run in sorted(workspace.iterdir()):
        if not run.is_dir() or not phase1.RUN_ID_PATTERN.fullmatch(run.name):
            continue
        try:
            state = services.phase2_state(run)
        except Exception as error:
            _raise("PRECHECK", "STALE_RUN_STATE_INVALID:" + run.name + ":" + str(error))
        if state is None:
            continue
        current = state.get("state")
        ownership = state.get("ownership")
        if current in {phase2.AWAITING_NATIVE_SETUP, phase2.RUNNING}:
            try:
                stopped = services.stop(run)
            except Exception as error:
                _raise("PRECHECK", "OWNED_STALE_RUN_STOP_FAILED:" + run.name + ":" + str(error))
            if stopped.get("state") != phase2.STOPPED:
                _raise("PRECHECK", "OWNED_STALE_RUN_STOP_UNPROVEN:" + run.name)
            results.append({"run_id": run.name, "action": "VERIFIED_PHASE2_STOP"})
        elif (type(ownership) is dict
              and services.ownership_matches(ownership)):
            _raise("PRECHECK", "CONFLICTING_RUNTIME_NOT_SAFELY_STOPPABLE:" + run.name)
        elif current in {phase2.AUTHORIZED, phase2.STARTING, phase2.STOPPING}:
            _raise("PRECHECK", "INCOMPLETE_ONE_CLICK_TRANSITION:" + run.name)
    return results


def _precheck(profile, workspace, services):
    if Path.cwd().resolve() != phase1.REPO_ROOT.resolve():
        _raise("PRECHECK", "REPOSITORY_ROOT_REQUIRED")
    if services.branch() != EXPECTED_BRANCH:
        _raise("PRECHECK", "EXPECTED_BRANCH_REQUIRED:" + EXPECTED_BRANCH)
    try:
        validated = services.validate_profile(profile)
    except Exception as error:
        _raise("PRECHECK", str(error))
    profile_value = validated["profile"]
    if (profile_value.get("execution_authority") is not False
            or profile_value.get("live_authority") is not False
            or profile_value.get("external_order_authority") is not False
            or profile_value.get("future_runtime_execution_enabled") is not False):
        _raise("PRECHECK", "PROFILE_ZERO_AUTHORITY_REQUIRED")
    stale = _reconcile_old_runs(workspace, services)
    binding = _binding_precheck(validated)
    try:
        port_states = services.port_states(validated["ports"].values())
    except Exception as error:
        _raise("PRECHECK", "PORT_INSPECTION_FAILED:" + str(error))
    listening = sorted(
        port for port, states in port_states.items() if "LISTENING" in states)
    if listening:
        _raise("PRECHECK", "REQUIRED_PORT_LISTENING:" + ",".join(map(str, listening)))
    return {
        "profile_sha256": validated["profile_sha256"],
        "stale_runs": stale, "fixed_binding": binding,
        "port_states": {str(k): sorted(v) for k, v in port_states.items()},
    }


def _assert_zero_authority(value, stage):
    if any(value.get(key) is not False for key in ZERO_AUTHORITY):
        _raise(stage, "ZERO_AUTHORITY_POSTCONDITION_FAILED")


def _assert_exact_handoff_binding(handoff, runtime_directory, stage):
    expected = (runtime_directory.parent.parent
                / phase3._BINDING_DIRECTORY_NAME / phase3._BINDING_FILE_NAME)
    payload = handoff.get("handoff", {})
    settings = payload.get("settings", {})
    observed = {
        payload.get("native_binding", {}).get("control_file"),
        settings.get("ArmsReadOnlyMarketV1", {}).get("OneClickBindingFile"),
        settings.get("ArmsChartCatchupBridgeV1", {}).get("OneClickBindingFile"),
    }
    if observed != {str(expected.resolve(strict=False))}:
        _raise(stage, "FIXED_BINDING_PATH_MISMATCH")


def _diagnostic_path(workspace, run_id):
    if run_id is not None:
        directory = workspace / run_id
    else:
        directory = workspace / "diagnostics"
        directory.mkdir(parents=True, exist_ok=True)
    return directory / ("operator-diagnostic-" + uuid4().hex + ".json")


def _write_diagnostic(workspace, *, stage, reason, run_id, runtime_id,
                      profile, precheck, cleanup):
    path = _diagnostic_path(workspace, run_id)
    run = workspace / run_id if run_id else None
    evidence = {}
    if run is not None and run.is_dir():
        for name in (
                "manifest.json", "state.json", "phase2-state.json",
                "phase3-state.json", "phase3-handoff.json"):
            evidence[name] = _read_optional_json(run / name)
        for name in ("phase2-supervisor.stdout.log",
                     "phase2-supervisor.stderr.log"):
            evidence[name + ":tail"] = _tail(run / name)
        manifest = evidence.get("manifest.json")
        if type(manifest) is dict:
            report = Path(manifest.get("targets", {}).get(
                "supervisor_report_directory", ""))
            for name in ("supervisor-start.json", "external-shutdown-result.json"):
                evidence[name] = _read_optional_json(report / name)
        handoff = evidence.get("phase3-handoff.json")
        if type(handoff) is dict:
            control = handoff.get("native_binding", {}).get("control_file")
            if type(control) is str and control:
                evidence["active-binding.json"] = _read_optional_json(control)
        if runtime_id:
            phase2_evidence = evidence.get("phase2-state.json")
            native_setup = (phase2_evidence.get("native_setup", {})
                            if type(phase2_evidence) is dict else {})
            runtime_value = native_setup.get("runtime_directory")
            if type(runtime_value) is str and runtime_value:
                runtime = Path(runtime_value)
                for name in ("shutdown-result.json", "claim.json",
                             "chart-catchup-request.json"):
                    evidence[name] = _read_optional_json(runtime / name)
                evidence["catchup-lifecycle.jsonl:tail"] = _tail(
                    runtime / "chart-catchup" / "catchup-lifecycle.jsonl")
                evidence["jsonl_inventory"] = _bounded_inventory(
                    runtime, ".jsonl")
                evidence["done_inventory"] = _bounded_inventory(
                    runtime, ".done.json")
    value = {
        "schema": DIAGNOSTIC_SCHEMA,
        "created_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "failed_stage": stage, "primary_reason": reason,
        "run_id": run_id, "native_runtime_id": runtime_id,
        "profile": str(Path(profile).resolve(strict=False)),
        "precheck": precheck, "cleanup": cleanup, "evidence": evidence,
        **ZERO_AUTHORITY,
    }
    phase1._atomic_json(path, value, exclusive=True)
    return path


def _success(output):
    output("============================================================")
    output("ARMS AI ONE CLICK — PASS")
    output("============================================================")
    for line in (
            "PHASE1=PASS", "PHASE2_NATIVE_SETUP=PASS",
            "PHASE3_PREPARE=PASS", "AUTHORIZATION=PASS", "APPLY_COUNT=1",
            "FIXED_BINDING=PASS", "BINDING_RECEIPT=PASS",
            "NATIVE_HELLO=PASS", "HANDOFF_COMPLETE=PASS",
            "PHASE2_CONTINUE=PASS", "FINAL_STATE=RUNNING_DISABLED"):
        output(line)
    for key, value in ZERO_AUTHORITY.items():
        output(key.upper() + "=" + str(value).upper())
    output("============================================================")


def _blocked(output, *, stage, reason, run_id, runtime_id, diagnostic):
    output("============================================================")
    output("ARMS AI ONE CLICK — BLOCKED")
    output("============================================================")
    output("FAILED_STAGE=" + stage)
    output("PRIMARY_REASON=" + reason)
    output("RUN_ID=" + (run_id or "NONE"))
    output("NATIVE_RUNTIME_ID=" + (runtime_id or "NONE"))
    output("DIAGNOSTIC_REPORT=" + str(diagnostic))
    for key, value in ZERO_AUTHORITY.items():
        output(key.upper() + "=" + str(value).upper())
    output("============================================================")


def run(profile, *, workspace=phase1.DEFAULT_WORKSPACE, services=None,
        output=print):
    services = services or OperatorServices()
    profile = Path(profile)
    workspace = Path(workspace).resolve(strict=False)
    stage = "PRECHECK"
    run_id = None
    runtime_id = None
    precheck = None
    cleanup = None
    try:
        output(DO_NOT_APPLY)
        precheck = _precheck(profile, workspace, services)
        stage = "PHASE1"
        phase1_state = services.prepare_phase1(profile, workspace)
        run_id = phase1_state.get("run_id")
        run_directory = Path(phase1_state["run_directory"])
        audit = services.audit_phase1(run_directory)
        if (phase1_state.get("state") != phase1.PREPARED
                or phase1_state.get("profile_status") != "VALID"
                or phase1_state.get("source_binding") != phase1.SOURCE_BINDING_PASS
                or audit.get("status") != "PASS"):
            _raise(stage, "PHASE1_POSTCONDITION_FAILED")

        stage = "PHASE2_START"
        phase2_state = services.start_phase2(run_directory)
        _assert_zero_authority(phase2_state, stage)
        if phase2_state.get("state") != phase2.AWAITING_NATIVE_SETUP:
            _raise(stage, "PHASE2_NATIVE_SETUP_STATE_REQUIRED")
        native = phase2_state.get("native_setup")
        if type(native) is not dict:
            _raise(stage, "PHASE2_NATIVE_SETUP_BINDING_REQUIRED")
        runtime_id = native.get("native_runtime_id")
        runtime_directory = Path(native["runtime_directory"])

        stage = "PHASE3_PREPARE"
        handoff = services.prepare_phase3(run_directory, runtime_directory)
        _assert_zero_authority(handoff, stage)
        _assert_exact_handoff_binding(handoff, runtime_directory, stage)
        if (handoff.get("state") != phase3.PREPARED
                or handoff.get("apply_count") != 0
                or handoff.get("native_runtime_id") != runtime_id
                or handoff.get("handoff", {}).get("chart_contract") != phase3._CHART):
            _raise(stage, "PHASE3_PREPARE_POSTCONDITION_FAILED")

        output(DO_NOT_APPLY)
        stage = "AUTHORIZATION"
        authorization = services.authorize_phase3(run_directory)
        _assert_zero_authority(authorization, stage)
        if (authorization.get("state") != phase3.AUTHORIZED
                or authorization.get("apply_limit") != 1):
            _raise(stage, "PHASE3_AUTHORIZATION_POSTCONDITION_FAILED")

        stage = "APPLY_AND_HANDOFF"
        prompts = 0

        def announce(applying):
            nonlocal prompts
            if (applying.get("state") != phase3.APPLYING
                    or applying.get("apply_count") != 1):
                _raise(stage, "SETUP_APPLYING_POSTCONDITION_FAILED")
            prompts += 1
            if prompts != 1:
                _raise(stage, "APPLY_INSTRUCTION_LIMIT_EXCEEDED")
            output(APPLY_BANNER)

        completed = services.begin_apply(
            run_directory, authorization["authorization_token"],
            authorization["handoff_file_sha256"], announce)
        _assert_zero_authority(completed, stage)
        if (prompts != 1 or completed.get("state") != phase3.COMPLETE
                or completed.get("apply_count") != 1):
            _raise(stage, "HANDOFF_COMPLETE_REQUIRED")
        output(APPLY_DETECTED)

        stage = "PHASE2_CONTINUE"
        final = services.continue_phase2(run_directory)
        _assert_zero_authority(final, stage)
        if final.get("state") != phase2.RUNNING:
            _raise(stage, "RUNNING_DISABLED_REQUIRED")
        _success(output)
        return {"schema": SCHEMA, "state": phase2.RUNNING,
                "run_id": run_id, "native_runtime_id": runtime_id,
                "apply_count": 1, **ZERO_AUTHORITY}
    except Exception as error:
        if isinstance(error, OperatorBlocked):
            stage, reason = error.stage, error.reason
        else:
            reason = str(error) or type(error).__name__
        if run_id is not None:
            try:
                state = services.phase2_state(workspace / run_id)
                if state is not None and state.get("state") in {
                        phase2.AWAITING_NATIVE_SETUP, phase2.RUNNING}:
                    cleanup = services.stop(workspace / run_id)
            except Exception as cleanup_error:
                cleanup = {"status": "FAILED", "reason": str(cleanup_error)}
        try:
            diagnostic = _write_diagnostic(
                workspace, stage=stage, reason=reason, run_id=run_id,
                runtime_id=runtime_id, profile=profile, precheck=precheck,
                cleanup=cleanup)
        except Exception as diagnostic_error:
            diagnostic = ("UNAVAILABLE:"
                          + (str(diagnostic_error)
                             or type(diagnostic_error).__name__))
        _blocked(output, stage=stage, reason=reason, run_id=run_id,
                 runtime_id=runtime_id, diagnostic=diagnostic)
        return {"schema": SCHEMA, "state": phase1.BLOCKED,
                "failed_stage": stage, "primary_reason": reason,
                "run_id": run_id, "native_runtime_id": runtime_id,
                "diagnostic_report": str(diagnostic), **ZERO_AUTHORITY}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, default=phase1.DEFAULT_WORKSPACE)
    args = parser.parse_args(argv)
    result = run(args.profile, workspace=args.workspace)
    return 0 if result["state"] == phase2.RUNNING else 2


if __name__ == "__main__":
    sys.exit(main())
