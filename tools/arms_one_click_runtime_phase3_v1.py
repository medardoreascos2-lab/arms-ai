"""One-Click Phase 3: sealed, one-shot native setup handoff.

This module has no GUI implementation and no trading surface.  It validates
the exact runtime request, grants a process-local authorization for one setup
Apply, records the attempt before invoking an injected adapter, and accepts
completion only after the expected native session emits a valid read-only
HELLO in the exact run inbox.
"""

import argparse
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
from secrets import compare_digest, token_bytes
import time
from uuid import UUID

from tools import arms_one_click_runtime_v1 as phase1
from tools import arms_one_click_runtime_phase2_v1 as phase2


HANDOFF_SCHEMA = "arms.one-click-runtime-phase3-handoff.v1"
EVENTS_SCHEMA = "arms.one-click-runtime-phase3-events.v1"
EVENT_SCHEMA = "arms.one-click-runtime-phase3-event.v1"
STATE_SCHEMA = "arms.one-click-runtime-phase3-state.v1"
RECEIPT_SCHEMA = "arms.one-click-runtime-phase3-apply-receipt.v1"
PHASE3_SOURCE = "tools/arms_one_click_runtime_phase3_v1.py"
PREPARED = "HANDOFF_PREPARED"
AUTHORIZED = "SETUP_AUTHORIZED"
APPLYING = "SETUP_APPLYING"
AWAITING_HELLO = "AWAITING_NATIVE_HELLO"
COMPLETE = "HANDOFF_COMPLETE"
FAILED = "HANDOFF_FAILED"
REVOKED = "SETUP_AUTHORIZATION_REVOKED"
AUTHORIZATION_TTL_SECONDS = 60
_HANDOFF_NAME = "phase3-handoff.json"
_EVENTS_NAME = "phase3-events.json"
_STATE_NAME = "phase3-state.json"
_LOCK_NAME = ".phase3-transition.lock"
_ZERO_AUTHORITY = {
    "execution_authority": False,
    "order_authority": False,
    "paper_execution_authority": False,
    "live_execution_authority": False,
    "broker_authority": False,
    "strategy_enable_authority": False,
    "ninjatrader_control_authority": False,
    "paper_execution_enabled": False,
    "live_execution_allowed": False,
    "external_order_authority": False,
    "broker_live_order_authority": False,
}
_CHART = {
    "instrument": "NQ DEC26",
    "bars_period": "Minute",
    "bars_value": 1,
    "trading_hours": "CME US Index Futures ETH",
    "provider": "Provider31",
}


class Phase3Blocked(RuntimeError):
    """Fail-closed native setup refusal."""


@dataclass
class SetupAuthorization:
    handoff_sha256: str
    plan_sha256: str
    profile_sha256: str
    capture_spec_sha256: str
    phase3_source_sha256: str
    issued_utc: datetime
    expires_utc: datetime
    issuer_pid: int
    _token: bytes = field(repr=False)
    consumed: bool = field(default=False, repr=False)

    def token_for_immediate_consumption(self):
        return self._token


class NativeSetupAdapter:
    """Production boundary. A separately approved adapter must implement it."""

    def apply_once(self, *, handoff):
        raise Phase3Blocked("NATIVE_SETUP_ADAPTER_REQUIRED")


class NativeHelloObserver:
    """Uses the certified reader's preactivation HELLO validation."""

    def __init__(self, handoff):
        from backend.market_data.fresh_native_adapter_v1 import (
            FreshNativeAdapterV1, WindowsQpc,
        )
        self._adapter = FreshNativeAdapterV1(
            directory=handoff["runtime"]["live_inbox"],
            qpc_clock=WindowsQpc(),
            installed_exporter=handoff["inputs"]["installed_exporter"]["path"],
            startup_seconds=handoff["hello_timeout_seconds"],
            health_gated=True,
        )

    def observe(self):
        return self._adapter.validate_preactivation_buffer(
            "PHASE3_NATIVE_HELLO_INVALID")


def _now(clock=None):
    value = (clock or (lambda: datetime.now(timezone.utc)))()
    if type(value) is not datetime or value.tzinfo is None:
        raise Phase3Blocked("EXPLICIT_UTC_CLOCK_REQUIRED")
    value = value.astimezone(timezone.utc)
    if value.utcoffset() != timedelta(0):
        raise Phase3Blocked("EXPLICIT_UTC_CLOCK_REQUIRED")
    return value


def _utc(value):
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _digest(value):
    return sha256(phase1._canonical(value)).hexdigest()


def _parse_utc(value, reason):
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError) as error:
        raise Phase3Blocked(reason) from error
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise Phase3Blocked(reason)
    return parsed


def _read_bound_json(path, schema):
    value, raw = phase1._read_json(path, schema)
    return value, sha256(raw).hexdigest()


def _phase3_source(manifest):
    descriptor = manifest["source_pins"].get(PHASE3_SOURCE)
    if type(descriptor) is not dict:
        raise Phase3Blocked("PHASE3_SOURCE_PIN_REQUIRED")
    _, digest, size = phase1._hash_stable_file(
        descriptor.get("path"), descriptor.get("sha256"))
    if digest != descriptor.get("sha256") or size != descriptor.get("bytes"):
        raise Phase3Blocked("PHASE3_SOURCE_BINDING_INVALID")
    return descriptor


def _load_context(run_directory, *, runtime_required=True):
    directory, manifest, phase1_state, _, validated = phase1._load_and_verify(
        run_directory, allow_runtime_targets=True)
    if not validated["reviewed"]:
        raise Phase3Blocked("REVIEWED_PHASE1B_PLAN_REQUIRED")
    source = _phase3_source(manifest)
    state, _ = phase2._load_phase2(directory)
    if (state is None or state.get("state") not in {phase2.STARTING, phase2.RUNNING}
            or type(state.get("ownership")) is not dict):
        raise Phase3Blocked("PHASE2_OWNED_RUNTIME_REQUIRED")
    bindings = {
        "plan_sha256": phase1_state["manifest_sha256"],
        "profile_sha256": manifest["profile"]["sha256"],
        "capture_spec_sha256": manifest["inputs"]["native_spec"]["sha256"],
        "phase3_source_sha256": source["sha256"],
    }
    if state.get("bindings") != {
            key: bindings[key] for key in (
                "plan_sha256", "profile_sha256", "capture_spec_sha256")}:
        raise Phase3Blocked("PHASE2_BINDING_DRIFT")
    return directory, manifest, validated, bindings


def _validate_runtime(manifest, runtime_directory):
    runtime = Path(runtime_directory).resolve(strict=True)
    parent = Path(manifest["targets"]["runtime_parent"]).resolve(strict=True)
    if runtime.parent != parent:
        raise Phase3Blocked("RUNTIME_DIRECTORY_NOT_RUN_SCOPED")
    try:
        native_runtime_id = str(UUID(runtime.name))
    except (ValueError, TypeError, AttributeError) as error:
        raise Phase3Blocked("NATIVE_RUNTIME_ID_INVALID") from error
    if native_runtime_id != runtime.name:
        raise Phase3Blocked("NATIVE_RUNTIME_ID_INVALID")
    claim, claim_sha = _read_bound_json(runtime / "claim.json", None)
    request, request_sha = _read_bound_json(
        runtime / "chart-catchup-request.json",
        "arms.startup-chart-catchup-request.v1")
    inbox = (runtime / "inbox").resolve(strict=True)
    catchup = (runtime / "chart-catchup").resolve(strict=True)
    expected_claim = {
        "run_id": native_runtime_id,
        "mode": "ANALYSIS_ONLY",
        "bootstrap_sha256": manifest["inputs"]["bootstrap_evidence"]["sha256"],
        "startup_chart_catchup_required": True,
        "backend_url": f"http://127.0.0.1:{manifest['ports']['backend']}",
        "dashboard_url": (
            f"http://127.0.0.1:{manifest['ports']['frontend']}/market-analysis"),
        "input_directory": str(inbox),
    }
    if any(claim.get(key) != value for key, value in expected_claim.items()):
        raise Phase3Blocked("RUNTIME_CLAIM_BINDING_INVALID")
    expected_request = {
        "indicator": "ArmsChartCatchupBridgeV1",
        "capture_enabled": True,
        "output_directory": str(catchup),
        "live_output_directory": str(inbox),
        "expected_provider_enum": "Provider31",
        "through_close_utc": "LATEST_CLOSED",
        "through_selection": "CHART_LATEST_CLOSED",
        "absolute_time_authority": "NONE",
        "range_contract": "EXACT_CONTIGUOUS_NO_TRUNCATION",
        "observation_only": True,
        "runtime_admission": False,
        "execution_authority": False,
    }
    if any(request.get(key) != value for key, value in expected_request.items()):
        raise Phase3Blocked("CHART_REQUEST_CONTRACT_INVALID")
    _parse_utc(request.get("from_close_utc"), "FROM_CLOSE_UTC_INVALID")
    return {
        "directory": str(runtime), "native_runtime_id": native_runtime_id,
        "live_inbox": str(inbox), "catchup_output_directory": str(catchup),
        "claim_sha256": claim_sha, "request_sha256": request_sha,
        "from_close_utc": request["from_close_utc"],
        "through_close_utc": request["through_close_utc"],
        "expected_provider": request["expected_provider_enum"],
    }


def _settings(runtime):
    return {
        "ArmsReadOnlyMarketV1": {
            "OutputDirectory": runtime["live_inbox"],
            "ExpectedProvider": runtime["expected_provider"],
        },
        "ArmsChartCatchupBridgeV1": {
            "CaptureEnabled": True,
            "OutputDirectory": runtime["catchup_output_directory"],
            "ExpectedProvider": runtime["expected_provider"],
            "FromCloseUtc": runtime["from_close_utc"],
            "ThroughCloseUtc": runtime["through_close_utc"],
            "LiveOutputDirectory": runtime["live_inbox"],
        },
    }


def _event(*, handoff, sequence, previous, transition, state, timestamp,
           apply_count, details=None):
    setup_authority = state in {AUTHORIZED, APPLYING, AWAITING_HELLO}
    value = {
        "schema": EVENT_SCHEMA, "run_id": handoff["run_id"],
        "native_runtime_id": handoff["runtime"]["native_runtime_id"],
        "sequence": sequence, "timestamp_utc": timestamp,
        "previous_event_sha256": previous, "transition": transition,
        "state": state, "handoff_sha256": _digest(handoff),
        "apply_count": apply_count, "ninjatrader_setup_authority": setup_authority,
        **_ZERO_AUTHORITY, "details": {} if details is None else details,
    }
    value["event_sha256"] = _digest(value)
    return value


def _state(event):
    return {
        "schema": STATE_SCHEMA, "run_id": event["run_id"],
        "native_runtime_id": event["native_runtime_id"],
        "state": event["state"], "sequence": event["sequence"],
        "last_event_sha256": event["event_sha256"],
        "handoff_sha256": event["handoff_sha256"],
        "apply_count": event["apply_count"],
        "ninjatrader_setup_authority": event["ninjatrader_setup_authority"],
        **_ZERO_AUTHORITY, "details": event["details"],
    }


def _load_evidence(directory, handoff):
    events_value, _ = phase1._read_json(directory / _EVENTS_NAME, EVENTS_SCHEMA)
    state, _ = phase1._read_json(directory / _STATE_NAME, STATE_SCHEMA)
    events = events_value.get("events")
    if type(events) is not list or not events:
        raise Phase3Blocked("PHASE3_EVENTS_REQUIRED")
    previous = None
    expected_handoff = _digest(handoff)
    for sequence, event in enumerate(events, 1):
        unsigned = dict(event); digest = unsigned.pop("event_sha256", None)
        expected_setup = event.get("state") in {AUTHORIZED, APPLYING, AWAITING_HELLO}
        if (event.get("schema") != EVENT_SCHEMA
                or event.get("run_id") != handoff["run_id"]
                or event.get("native_runtime_id") != handoff["runtime"]["native_runtime_id"]
                or event.get("sequence") != sequence
                or event.get("previous_event_sha256") != previous
                or digest != _digest(unsigned)
                or event.get("handoff_sha256") != expected_handoff
                or event.get("ninjatrader_setup_authority") is not expected_setup
                or any(event.get(key) is not False for key in _ZERO_AUTHORITY)):
            raise Phase3Blocked("PHASE3_EVENT_CHAIN_INVALID")
        previous = digest
    if state != _state(events[-1]):
        raise Phase3Blocked("PHASE3_STATE_PROJECTION_INVALID")
    if state["apply_count"] not in (0, 1):
        raise Phase3Blocked("APPLY_COUNT_INVALID")
    return state, events


def _load_handoff(run_directory):
    directory, manifest, _, bindings = _load_context(run_directory)
    handoff, raw = phase1._read_json(directory / _HANDOFF_NAME, HANDOFF_SCHEMA)
    if (handoff.get("run_id") != manifest["run_id"]
            or handoff.get("bindings") != bindings
            or any(handoff.get(key) is not False for key in _ZERO_AUTHORITY)
            or handoff.get("ninjatrader_setup_authority") is not False
            or handoff.get("chart_contract") != _CHART):
        raise Phase3Blocked("HANDOFF_BINDING_INVALID")
    runtime = _validate_runtime(manifest, handoff["runtime"]["directory"])
    if runtime != handoff["runtime"] or _settings(runtime) != handoff["settings"]:
        raise Phase3Blocked("HANDOFF_RUNTIME_DRIFT")
    return directory, manifest, handoff, sha256(raw).hexdigest()


def _transition(directory, handoff, *, state, transition, clock,
                apply_count, details=None, expected_states=()):
    lock = directory / _LOCK_NAME
    acquired = False
    try:
        with lock.open("xb") as stream:
            acquired = True; stream.write(b"phase3-transition\n")
            stream.flush(); os.fsync(stream.fileno())
        current, events = _load_evidence(directory, handoff)
        if expected_states and current["state"] not in expected_states:
            raise Phase3Blocked("PHASE3_TRANSITION_NOT_ALLOWED:" + current["state"])
        event = _event(
            handoff=handoff, sequence=len(events) + 1,
            previous=events[-1]["event_sha256"], transition=transition,
            state=state, timestamp=_utc(_now(clock)), apply_count=apply_count,
            details=details)
        phase1._atomic_json(directory / _EVENTS_NAME,
                            {"schema": EVENTS_SCHEMA, "events": [*events, event]})
        phase1._atomic_json(directory / _STATE_NAME, _state(event))
        return _state(event)
    finally:
        if acquired:
            lock.unlink(missing_ok=True)


def prepare_handoff(run_directory, runtime_directory, *, clock=None,
                    hello_timeout_seconds=60):
    if (type(hello_timeout_seconds) not in (int, float)
            or isinstance(hello_timeout_seconds, bool)
            or not 0 < hello_timeout_seconds <= 900):
        raise Phase3Blocked("HELLO_TIMEOUT_INVALID")
    directory, manifest, _, bindings = _load_context(run_directory)
    if any((directory / name).exists()
           for name in (_HANDOFF_NAME, _EVENTS_NAME, _STATE_NAME)):
        raise Phase3Blocked("PHASE3_FRESH_HANDOFF_REQUIRED")
    runtime = _validate_runtime(manifest, runtime_directory)
    handoff = {
        "schema": HANDOFF_SCHEMA, "run_id": manifest["run_id"],
        "created_utc": _utc(_now(clock)), "bindings": bindings,
        "runtime": runtime, "chart_contract": dict(_CHART),
        "settings": _settings(runtime),
        "inputs": {
            name: dict(manifest["inputs"][name]) for name in (
                "installed_exporter", "startup_chart_catchup_source",
                "native_spec", "bootstrap_evidence")},
        "hello_timeout_seconds": hello_timeout_seconds,
        "apply_limit": 1, "ninjatrader_setup_authority": False,
        **_ZERO_AUTHORITY,
    }
    phase1._atomic_json(directory / _HANDOFF_NAME, handoff, exclusive=True)
    event = _event(
        handoff=handoff, sequence=1, previous=None,
        transition="HANDOFF_PREPARED", state=PREPARED,
        timestamp=handoff["created_utc"], apply_count=0)
    phase1._atomic_json(directory / _EVENTS_NAME,
                        {"schema": EVENTS_SCHEMA, "events": [event]}, exclusive=True)
    phase1._atomic_json(directory / _STATE_NAME, _state(event), exclusive=True)
    return status(directory)


def authorize_setup(run_directory, *, clock=None, ttl_seconds=30,
                    token_factory=token_bytes):
    now = _now(clock)
    if (type(ttl_seconds) not in (int, float) or isinstance(ttl_seconds, bool)
            or not 0 < ttl_seconds <= AUTHORIZATION_TTL_SECONDS):
        raise Phase3Blocked("AUTHORIZATION_TTL_INVALID")
    directory, _, handoff, handoff_file_sha = _load_handoff(run_directory)
    state, _ = _load_evidence(directory, handoff)
    if state["state"] != PREPARED or state["apply_count"] != 0:
        raise Phase3Blocked("FRESH_PREPARED_HANDOFF_REQUIRED")
    raw_token = token_factory(32)
    if type(raw_token) is not bytes or len(raw_token) < 32:
        raise Phase3Blocked("CRYPTOGRAPHIC_AUTHORIZATION_REQUIRED")
    authorization = SetupAuthorization(
        handoff_sha256=handoff_file_sha, **handoff["bindings"],
        issued_utc=now, expires_utc=now + timedelta(seconds=ttl_seconds),
        issuer_pid=os.getpid(), _token=raw_token)
    _transition(directory, handoff, state=AUTHORIZED,
                transition="SETUP_AUTHORIZED", clock=lambda: now,
                apply_count=0, expected_states=(PREPARED,))
    return authorization


def _validate_receipt(receipt, handoff):
    expected = {
        "schema": RECEIPT_SCHEMA, "run_id": handoff["run_id"],
        "native_runtime_id": handoff["runtime"]["native_runtime_id"],
        "chart_contract": handoff["chart_contract"],
        "settings": handoff["settings"], "apply_count": 1,
        **_ZERO_AUTHORITY,
    }
    if type(receipt) is not dict or any(receipt.get(k) != v for k, v in expected.items()):
        raise Phase3Blocked("NATIVE_APPLY_RECEIPT_INVALID")
    try:
        session = str(UUID(receipt.get("native_session_id")))
    except (ValueError, TypeError, AttributeError) as error:
        raise Phase3Blocked("NATIVE_SESSION_ID_INVALID") from error
    if session != receipt.get("native_session_id"):
        raise Phase3Blocked("NATIVE_SESSION_ID_INVALID")
    _parse_utc(receipt.get("applied_utc"), "APPLIED_UTC_INVALID")
    return session


def execute_authorized(run_directory, authorization, supplied_token, *,
                       setup_adapter=None, hello_observer=None, clock=None,
                       monotonic=time.monotonic, sleeper=time.sleep):
    now = _now(clock)
    directory, _, handoff, handoff_file_sha = _load_handoff(run_directory)
    state, _ = _load_evidence(directory, handoff)
    if state["state"] != AUTHORIZED or state["apply_count"] != 0:
        raise Phase3Blocked("SETUP_AUTHORIZATION_REQUIRED")
    if type(authorization) is not SetupAuthorization:
        raise Phase3Blocked("PROCESS_SCOPED_AUTHORIZATION_REQUIRED")
    if authorization.consumed:
        raise Phase3Blocked("SETUP_AUTHORIZATION_ALREADY_CONSUMED")
    authorization.consumed = True
    expected = {"handoff_sha256": handoff_file_sha, **handoff["bindings"]}
    reason = None
    if authorization.issuer_pid != os.getpid():
        reason = "SETUP_AUTHORIZATION_PROCESS_MISMATCH"
    elif now > authorization.expires_utc:
        reason = "SETUP_AUTHORIZATION_EXPIRED"
    elif type(supplied_token) is not bytes or not compare_digest(
            supplied_token, authorization._token):
        reason = "SETUP_AUTHORIZATION_TOKEN_INVALID"
    elif any(getattr(authorization, key) != value for key, value in expected.items()):
        reason = "SETUP_AUTHORIZATION_BINDING_MISMATCH"
    if reason is not None:
        _transition(directory, handoff, state=REVOKED,
                    transition="SETUP_AUTHORIZATION_REVOKED", clock=lambda: now,
                    apply_count=0, details={"reason": reason},
                    expected_states=(AUTHORIZED,))
        raise Phase3Blocked(reason)

    observer = hello_observer or NativeHelloObserver(handoff)
    adapter = setup_adapter or NativeSetupAdapter()
    _transition(directory, handoff, state=APPLYING,
                transition="SETUP_APPLY_ATTEMPT_RECORDED", clock=lambda: now,
                apply_count=1, expected_states=(AUTHORIZED,))
    try:
        receipt = adapter.apply_once(handoff=handoff)
        expected_session = _validate_receipt(receipt, handoff)
        _transition(directory, handoff, state=AWAITING_HELLO,
                    transition="SETUP_APPLIED_AWAITING_HELLO", clock=clock,
                    apply_count=1, details={"receipt": receipt},
                    expected_states=(APPLYING,))
        deadline = monotonic() + handoff["hello_timeout_seconds"]
        while monotonic() <= deadline:
            observed = observer.observe()
            if observed is not None:
                if observed != expected_session:
                    raise Phase3Blocked("FOREIGN_NATIVE_HELLO_SESSION")
                return _transition(
                    directory, handoff, state=COMPLETE,
                    transition="NATIVE_HELLO_ACCEPTED_SETUP_RELINQUISHED",
                    clock=clock, apply_count=1,
                    details={"receipt": receipt, "native_session_id": observed},
                    expected_states=(AWAITING_HELLO,))
            sleeper(0.05)
        raise Phase3Blocked("NATIVE_HELLO_TIMEOUT")
    except BaseException as error:
        current, _ = _load_evidence(directory, handoff)
        if current["state"] in {APPLYING, AWAITING_HELLO}:
            _transition(directory, handoff, state=FAILED,
                        transition="NATIVE_SETUP_FAILED_CLOSED", clock=clock,
                        apply_count=1, details={"reason": str(error)},
                        expected_states=(APPLYING, AWAITING_HELLO))
        raise


def status(run_directory):
    directory, _, handoff, _ = _load_handoff(run_directory)
    state, events = _load_evidence(directory, handoff)
    return {**state, "event_count": len(events), "handoff": handoff}


def _print(value):
    print(json.dumps(value, sort_keys=True, indent=2, allow_nan=False))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--run", type=Path, required=True)
    prepare.add_argument("--runtime", type=Path, required=True)
    status_parser = commands.add_parser("status")
    status_parser.add_argument("--run", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = (prepare_handoff(args.run, args.runtime)
                  if args.command == "prepare" else status(args.run))
        _print(result)
        return 0
    except (Phase3Blocked, phase2.Phase2Blocked, phase1.OfflineBlocked,
            OSError, ValueError, TypeError, KeyError, AttributeError) as error:
        _print({"schema": STATE_SCHEMA, "state": phase1.BLOCKED,
                "blocking_reasons": [str(error)],
                "ninjatrader_setup_authority": False, **_ZERO_AUTHORITY})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
