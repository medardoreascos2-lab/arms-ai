"""One-Click Phase 3: sealed, one-shot native setup handoff.

This module has no GUI implementation and no trading surface.  It validates
the exact runtime request, grants either an in-process test authorization or a
short-lived operator authorization for one setup Apply, records the attempt
before any Apply, and accepts completion only after a bound read-only HELLO
arrives in the exact run inbox.
"""

import argparse
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
from secrets import compare_digest, token_bytes
import sys
import time
from uuid import UUID

from tools import arms_one_click_runtime_v1 as phase1
from tools import arms_one_click_runtime_phase2_v1 as phase2


HANDOFF_SCHEMA = "arms.one-click-runtime-phase3-handoff.v1"
EVENTS_SCHEMA = "arms.one-click-runtime-phase3-events.v1"
EVENT_SCHEMA = "arms.one-click-runtime-phase3-event.v1"
STATE_SCHEMA = "arms.one-click-runtime-phase3-state.v1"
RECEIPT_SCHEMA = "arms.one-click-runtime-phase3-apply-receipt.v1"
BINDING_CONTROL_SCHEMA = "arms.one-click-native-binding-control.v1"
BINDING_CLAIM_SCHEMA = "arms.one-click-native-binding-claim.v1"
BINDING_RECEIPT_SCHEMA = "arms.nt.one-click-binding-receipt.v1"
PHASE3_SOURCE = "tools/arms_one_click_runtime_phase3_v1.py"
PREPARED = "HANDOFF_PREPARED"
AUTHORIZED = "SETUP_AUTHORIZED"
APPLYING = "SETUP_APPLYING"
AWAITING_HELLO = "AWAITING_NATIVE_HELLO"
COMPLETE = "HANDOFF_COMPLETE"
FAILED = "HANDOFF_FAILED"
REVOKED = "SETUP_AUTHORIZATION_REVOKED"
AUTHORIZATION_TTL_SECONDS = 900
_HANDOFF_NAME = "phase3-handoff.json"
_EVENTS_NAME = "phase3-events.json"
_STATE_NAME = "phase3-state.json"
_LOCK_NAME = ".phase3-transition.lock"
_BINDING_DIRECTORY_NAME = "one-click-native-control"
_BINDING_FILE_NAME = "active-binding.json"
_BINDING_LOCK_NAME = ".binding-transition.lock"
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
    phase2_native_setup_sha256: str
    issued_utc: datetime
    expires_utc: datetime
    issuer_pid: int
    _token: bytes = field(repr=False)
    consumed: bool = field(default=False, repr=False)

    def token_for_immediate_consumption(self):
        return self._token

    def operator_token(self):
        return self._token.hex()


class NativeSetupAdapter:
    """Production boundary. A separately approved adapter must implement it."""

    def apply_once(self, *, handoff):
        raise Phase3Blocked("NATIVE_SETUP_ADAPTER_REQUIRED")


class NativeHelloObserver:
    """Uses the certified reader's preactivation HELLO validation."""

    def __init__(self, handoff, binding_claim):
        from backend.market_data.fresh_native_adapter_v1 import (
            FreshNativeAdapterV1, WindowsQpc,
        )
        self._adapter = FreshNativeAdapterV1(
            directory=handoff["runtime"]["live_inbox"],
            qpc_clock=WindowsQpc(),
            installed_exporter=handoff["inputs"]["installed_exporter"]["path"],
            startup_seconds=handoff["hello_timeout_seconds"],
            health_gated=True,
            expected_one_click_binding={
                "native_runtime_id": binding_claim["native_runtime_id"],
                "binding_nonce": binding_claim["binding_nonce"],
                "binding_claim_sha256": _digest(binding_claim),
                "handoff_file_sha256": binding_claim["handoff_file_sha256"],
            },
        )
        self._native_runtime_id = handoff["runtime"]["native_runtime_id"]
        self._provider = handoff["runtime"]["expected_provider"]

    def observe(self):
        return self._adapter.validate_preactivation_buffer(
            "PHASE3_NATIVE_HELLO_INVALID")

    def observe_binding_receipt_evidence(self):
        suffix = ".one-click-binding.json"
        receipts = sorted(
            path for path in self._adapter.directory.iterdir()
            if path.is_file() and path.name.endswith(suffix))
        if not receipts:
            return None
        if len(receipts) != 1:
            raise Phase3Blocked("PHASE3_NATIVE_BINDING_RECEIPT_INVALID")
        session = self._adapter._preactivation_session_from_name(
            receipts[0].name, suffix,
            "PHASE3_NATIVE_BINDING_RECEIPT_INVALID")
        return self._adapter._validate_one_click_binding_receipt(
            receipts[0], session,
            "PHASE3_NATIVE_BINDING_RECEIPT_INVALID")

    def observe_evidence(self):
        session = self.observe()
        if session is None:
            return None
        return {
            "native_session_id": session,
            "native_runtime_id": self._native_runtime_id,
            "provider": self._provider,
            "binding_nonce": self._adapter.one_click_binding[
                "binding_nonce"],
            "binding_claim_sha256": self._adapter.one_click_binding[
                "binding_claim_sha256"],
            "handoff_file_sha256": self._adapter.one_click_binding[
                "handoff_file_sha256"],
        }


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


def _load_context(run_directory, *, require_waiting=False):
    directory, manifest, phase1_state, _, validated = phase1._load_and_verify(
        run_directory, allow_runtime_targets=True)
    if not validated["reviewed"]:
        raise Phase3Blocked("REVIEWED_PHASE1B_PLAN_REQUIRED")
    source = _phase3_source(manifest)
    state, _ = phase2._load_phase2(directory)
    allowed_states = ({phase2.AWAITING_NATIVE_SETUP} if require_waiting else
                      {phase2.AWAITING_NATIVE_SETUP, phase2.RUNNING,
                       phase2.FAILED})
    if (state is None or state.get("state") not in allowed_states
            or type(state.get("ownership")) is not dict
            or type(state.get("native_setup")) is not dict):
        raise Phase3Blocked("PHASE2_OWNED_RUNTIME_REQUIRED")
    bindings = {
        "plan_sha256": phase1_state["manifest_sha256"],
        "profile_sha256": manifest["profile"]["sha256"],
        "capture_spec_sha256": manifest["inputs"]["native_spec"]["sha256"],
        "phase3_source_sha256": source["sha256"],
        "phase2_native_setup_sha256": _digest(state["native_setup"]),
    }
    if state.get("bindings") != {
            key: bindings[key] for key in (
                "plan_sha256", "profile_sha256", "capture_spec_sha256")}:
        raise Phase3Blocked("PHASE2_BINDING_DRIFT")
    return directory, manifest, validated, bindings, state


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


def _binding_file(manifest, *, create=False):
    runtime_parent = Path(
        manifest["targets"]["runtime_parent"]).resolve(strict=True)
    control = runtime_parent.parent / _BINDING_DIRECTORY_NAME
    if create:
        control.mkdir(exist_ok=True)
    control = control.resolve(strict=True)
    if (control.parent != runtime_parent.parent
            or control.name != _BINDING_DIRECTORY_NAME
            or any(path.is_symlink() for path in (control, *control.parents))):
        raise Phase3Blocked("NATIVE_BINDING_CONTROL_PATH_INVALID")
    return control / _BINDING_FILE_NAME


def _settings(runtime, binding_file):
    return {
        "ArmsReadOnlyMarketV1": {
            "OneClickBindingFile": str(binding_file),
            "OutputDirectory": "",
            "ExpectedProvider": runtime["expected_provider"],
        },
        "ArmsChartCatchupBridgeV1": {
            "CaptureEnabled": True,
            "OneClickBindingFile": str(binding_file),
            "OutputDirectory": "",
            "ExpectedProvider": runtime["expected_provider"],
            "FromCloseUtc": "",
            "ThroughCloseUtc": "",
            "LiveOutputDirectory": "",
        },
    }


def _revoked_binding(*, run_id, native_runtime_id, timestamp, generation=0):
    return {
        "schema": BINDING_CONTROL_SCHEMA,
        "state": "REVOKED",
        "one_click_run_id": run_id,
        "native_runtime_id": native_runtime_id,
        "revoked_utc": timestamp,
        "generation": generation,
        **_ZERO_AUTHORITY,
    }


def _binding_lock(manifest):
    path = _binding_file(manifest, create=True).parent / _BINDING_LOCK_NAME
    try:
        stream = path.open("xb")
        stream.write(b"one-click-native-binding-transition\n")
        stream.flush()
        os.fsync(stream.fileno())
        stream.close()
    except FileExistsError as error:
        raise Phase3Blocked("NATIVE_BINDING_TRANSITION_IN_PROGRESS") from error
    return path


def _initialize_revoked_binding(manifest, *, run_id, native_runtime_id, clock):
    now = _now(clock)
    lock = _binding_lock(manifest)
    try:
        path = _binding_file(manifest)
        generation = 0
        if path.exists():
            current, _ = phase1._read_json(path, BINDING_CONTROL_SCHEMA)
            if current.get("state") == "ACTIVE":
                try:
                    claim = json.loads(current["claim_json"])
                    expires = _parse_utc(
                        claim["expires_utc"], "NATIVE_BINDING_CONTROL_INVALID")
                except (KeyError, TypeError, ValueError,
                        json.JSONDecodeError) as error:
                    raise Phase3Blocked(
                        "NATIVE_BINDING_CONTROL_INVALID") from error
                if now <= expires:
                    raise Phase3Blocked("NATIVE_BINDING_ALREADY_ACTIVE")
                generation = claim.get("generation", 0)
            elif current.get("state") != "REVOKED":
                raise Phase3Blocked("NATIVE_BINDING_CONTROL_INVALID")
            else:
                generation = current.get("generation", 0)
            if type(generation) is not int or generation < 0:
                raise Phase3Blocked("NATIVE_BINDING_CONTROL_INVALID")
        phase1._atomic_json(path, _revoked_binding(
            run_id=run_id, native_runtime_id=native_runtime_id,
            timestamp=_utc(now), generation=generation))
    finally:
        lock.unlink(missing_ok=True)


def _revoke_binding(manifest, *, run_id, native_runtime_id, clock,
                    expected_claim_sha256=None):
    path = _binding_file(manifest, create=True)
    lock = _binding_lock(manifest)
    try:
        current, _ = phase1._read_json(path, BINDING_CONTROL_SCHEMA)
        generation = current.get("generation", 0)
        if current.get("state") == "ACTIVE":
            if (expected_claim_sha256 is None
                    or current.get("claim_sha256") != expected_claim_sha256):
                raise Phase3Blocked("NATIVE_BINDING_OWNERSHIP_MISMATCH")
            try:
                generation = json.loads(current["claim_json"])["generation"]
            except (KeyError, TypeError, ValueError,
                    json.JSONDecodeError) as error:
                raise Phase3Blocked("NATIVE_BINDING_CONTROL_INVALID") from error
        elif (current.get("state") != "REVOKED"
                or current.get("one_click_run_id") != run_id
                or current.get("native_runtime_id") != native_runtime_id):
            raise Phase3Blocked("NATIVE_BINDING_OWNERSHIP_MISMATCH")
        phase1._atomic_json(path, _revoked_binding(
            run_id=run_id, native_runtime_id=native_runtime_id,
            timestamp=_utc(_now(clock)), generation=generation))
    finally:
        lock.unlink(missing_ok=True)


def _binding_claim(handoff, handoff_file_sha, authorization_record, now,
                   nonce, generation=1):
    if type(nonce) is not bytes or len(nonce) < 32:
        raise Phase3Blocked("CRYPTOGRAPHIC_BINDING_NONCE_REQUIRED")
    claim = {
        "schema": BINDING_CLAIM_SCHEMA,
        "one_click_run_id": handoff["run_id"],
        "native_runtime_id": handoff["runtime"]["native_runtime_id"],
        "runtime_parent": str(Path(
            handoff["runtime"]["directory"]).resolve(strict=True).parent),
        "runtime_directory": handoff["runtime"]["directory"],
        "live_inbox": handoff["runtime"]["live_inbox"],
        "catchup_output_directory": handoff["runtime"][
            "catchup_output_directory"],
        "expected_provider": handoff["runtime"]["expected_provider"],
        "contract": handoff["chart_contract"]["instrument"],
        "bars_period": handoff["chart_contract"]["bars_period"],
        "bars_value": handoff["chart_contract"]["bars_value"],
        "trading_hours": handoff["chart_contract"]["trading_hours"],
        "from_close_utc": handoff["runtime"]["from_close_utc"],
        "through_close_utc": handoff["runtime"]["through_close_utc"],
        "handoff_file_sha256": handoff_file_sha,
        "phase3_source_sha256": handoff["bindings"][
            "phase3_source_sha256"],
        "binding_nonce": nonce.hex(),
        "generation": generation,
        "created_utc": _utc(now),
        "expires_utc": _utc(
            now + timedelta(seconds=handoff["hello_timeout_seconds"])),
        "apply_limit": 1,
        **_ZERO_AUTHORITY,
    }
    _validate_binding_claim(
        claim, handoff=handoff, handoff_file_sha=handoff_file_sha,
        now=now)
    return claim


def _validate_binding_claim(claim, *, handoff, handoff_file_sha, now):
    if type(claim) is not dict:
        raise Phase3Blocked("NATIVE_BINDING_CLAIM_INVALID")
    expected = _binding_claim_fields(handoff, handoff_file_sha)
    if (set(claim) != expected
            or any(claim.get(key) is not False for key in _ZERO_AUTHORITY)):
        raise Phase3Blocked("NATIVE_BINDING_CLAIM_INVALID")
    try:
        runtime_id = str(UUID(claim["native_runtime_id"]))
        nonce = bytes.fromhex(claim["binding_nonce"])
        created = _parse_utc(claim["created_utc"], "NATIVE_BINDING_TIME_INVALID")
        expires = _parse_utc(claim["expires_utc"], "NATIVE_BINDING_TIME_INVALID")
    except (ValueError, TypeError, AttributeError, KeyError) as error:
        raise Phase3Blocked("NATIVE_BINDING_CLAIM_INVALID") from error
    expected_values = {
        "schema": BINDING_CLAIM_SCHEMA,
        "one_click_run_id": handoff["run_id"],
        "native_runtime_id": handoff["runtime"]["native_runtime_id"],
        "runtime_parent": str(Path(handoff["runtime"]["directory"]).parent),
        "runtime_directory": handoff["runtime"]["directory"],
        "live_inbox": handoff["runtime"]["live_inbox"],
        "catchup_output_directory": handoff["runtime"][
            "catchup_output_directory"],
        "expected_provider": handoff["runtime"]["expected_provider"],
        "contract": handoff["chart_contract"]["instrument"],
        "bars_period": handoff["chart_contract"]["bars_period"],
        "bars_value": handoff["chart_contract"]["bars_value"],
        "trading_hours": handoff["chart_contract"]["trading_hours"],
        "from_close_utc": handoff["runtime"]["from_close_utc"],
        "through_close_utc": handoff["runtime"]["through_close_utc"],
        "handoff_file_sha256": handoff_file_sha,
        "phase3_source_sha256": handoff["bindings"]["phase3_source_sha256"],
        "apply_limit": 1,
    }
    if (runtime_id != claim["native_runtime_id"]
            or len(nonce) < 32
            or type(claim.get("generation")) is not int
            or claim["generation"] <= 0
            or any(claim.get(key) != value
                   for key, value in expected_values.items())
            or not created <= now <= expires
            or not timedelta(0) < expires - created
            <= timedelta(seconds=AUTHORIZATION_TTL_SECONDS)):
        raise Phase3Blocked("NATIVE_BINDING_CLAIM_INVALID")
    runtime = Path(claim["runtime_directory"]).resolve(strict=True)
    parent = Path(claim["runtime_parent"]).resolve(strict=True)
    inbox = Path(claim["live_inbox"]).resolve(strict=True)
    catchup = Path(claim["catchup_output_directory"]).resolve(strict=True)
    if (not all(Path(claim[key]).is_absolute() for key in (
            "runtime_parent", "runtime_directory", "live_inbox",
            "catchup_output_directory"))
            or runtime.parent != parent
            or runtime.name != runtime_id
            or inbox != (runtime / "inbox").resolve(strict=True)
            or catchup != (runtime / "chart-catchup").resolve(strict=True)
            or any(path.is_symlink() for path in (
                runtime, inbox, catchup, *runtime.parents))):
        raise Phase3Blocked("NATIVE_BINDING_PATH_INVALID")
    return claim


def _binding_claim_fields(handoff, handoff_file_sha):
    return {
        "schema", "one_click_run_id", "native_runtime_id",
        "runtime_parent", "runtime_directory", "live_inbox",
        "catchup_output_directory", "expected_provider", "contract",
        "bars_period", "bars_value", "trading_hours", "from_close_utc",
        "through_close_utc", "handoff_file_sha256",
        "phase3_source_sha256", "binding_nonce", "generation",
        "created_utc", "expires_utc", "apply_limit", *_ZERO_AUTHORITY,
    }


def _next_binding_generation(manifest):
    value, _ = phase1._read_json(
        _binding_file(manifest), BINDING_CONTROL_SCHEMA)
    generation = value.get("generation", 0)
    if (value.get("state") != "REVOKED"
            or type(generation) is not int or generation < 0):
        raise Phase3Blocked("NATIVE_BINDING_CONTROL_INVALID")
    return generation + 1


def _publish_active_binding(manifest, claim):
    claim_json = phase1._canonical(claim).decode("utf-8")
    value = {
        "schema": BINDING_CONTROL_SCHEMA,
        "state": "ACTIVE",
        "claim_json": claim_json,
        "claim_sha256": sha256(claim_json.encode("utf-8")).hexdigest(),
    }
    path = _binding_file(manifest, create=True)
    lock = _binding_lock(manifest)
    try:
        current, _ = phase1._read_json(path, BINDING_CONTROL_SCHEMA)
        if (current.get("state") != "REVOKED"
                or current.get("one_click_run_id")
                != claim["one_click_run_id"]
                or current.get("native_runtime_id")
                != claim["native_runtime_id"]):
            raise Phase3Blocked("NATIVE_BINDING_OWNERSHIP_MISMATCH")
        current_generation = current.get("generation", 0)
        if (type(current_generation) is not int
                or claim.get("generation") != current_generation + 1):
            raise Phase3Blocked("NATIVE_BINDING_GENERATION_INVALID")
        phase1._atomic_json(path, value)
    finally:
        lock.unlink(missing_ok=True)
    return value["claim_sha256"]


def _load_active_binding(manifest, handoff, handoff_file_sha, *, now):
    value, _ = phase1._read_json(
        _binding_file(manifest), BINDING_CONTROL_SCHEMA)
    if (set(value) != {"schema", "state", "claim_json", "claim_sha256"}
            or value.get("state") != "ACTIVE"
            or type(value.get("claim_json")) is not str
            or sha256(value["claim_json"].encode("utf-8")).hexdigest()
            != value.get("claim_sha256")):
        raise Phase3Blocked("NATIVE_BINDING_CONTROL_INVALID")
    try:
        claim = json.loads(value["claim_json"])
    except (UnicodeError, json.JSONDecodeError, TypeError, ValueError) as error:
        raise Phase3Blocked("NATIVE_BINDING_CONTROL_INVALID") from error
    _validate_binding_claim(
        claim, handoff=handoff, handoff_file_sha=handoff_file_sha,
        now=now)
    if value["claim_sha256"] != _digest(claim):
        raise Phase3Blocked("NATIVE_BINDING_CONTROL_INVALID")
    return claim


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
    directory, manifest, _, bindings, _ = _load_context(run_directory)
    handoff, raw = phase1._read_json(directory / _HANDOFF_NAME, HANDOFF_SCHEMA)
    if (handoff.get("run_id") != manifest["run_id"]
            or handoff.get("bindings") != bindings
            or any(handoff.get(key) is not False for key in _ZERO_AUTHORITY)
            or handoff.get("ninjatrader_setup_authority") is not False
            or handoff.get("chart_contract") != _CHART):
        raise Phase3Blocked("HANDOFF_BINDING_INVALID")
    runtime = _validate_runtime(manifest, handoff["runtime"]["directory"])
    binding_file = _binding_file(manifest)
    expected_binding = {
        "control_file": str(binding_file),
        "control_schema": BINDING_CONTROL_SCHEMA,
        "claim_schema": BINDING_CLAIM_SCHEMA,
        "receipt_schema": BINDING_RECEIPT_SCHEMA,
    }
    if (runtime != handoff["runtime"]
            or _settings(runtime, binding_file) != handoff["settings"]
            or handoff.get("native_binding") != expected_binding):
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
    directory, manifest, _, bindings, phase2_state = _load_context(
        run_directory, require_waiting=True)
    if any((directory / name).exists()
           for name in (_HANDOFF_NAME, _EVENTS_NAME, _STATE_NAME)):
        raise Phase3Blocked("PHASE3_FRESH_HANDOFF_REQUIRED")
    runtime = _validate_runtime(manifest, runtime_directory)
    expected_phase2_runtime = {
        "runtime_directory": runtime["directory"],
        "native_runtime_id": runtime["native_runtime_id"],
        "live_inbox": runtime["live_inbox"],
        "catchup_output_directory": runtime["catchup_output_directory"],
        "claim_sha256": runtime["claim_sha256"],
        "request_sha256": runtime["request_sha256"],
    }
    if phase2_state["native_setup"] != expected_phase2_runtime:
        raise Phase3Blocked("PHASE2_NATIVE_SETUP_BINDING_MISMATCH")
    binding_file = _binding_file(manifest, create=True)
    _initialize_revoked_binding(
        manifest, run_id=manifest["run_id"],
        native_runtime_id=runtime["native_runtime_id"], clock=clock)
    handoff = {
        "schema": HANDOFF_SCHEMA, "run_id": manifest["run_id"],
        "created_utc": _utc(_now(clock)), "bindings": bindings,
        "runtime": runtime, "chart_contract": dict(_CHART),
        "settings": _settings(runtime, binding_file),
        "native_binding": {
            "control_file": str(binding_file),
            "control_schema": BINDING_CONTROL_SCHEMA,
            "claim_schema": BINDING_CLAIM_SCHEMA,
            "receipt_schema": BINDING_RECEIPT_SCHEMA,
        },
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
    authorization_record = {
        "mode": "OPERATOR_ASSISTED_ONE_SHOT",
        "token_sha256": sha256(raw_token).hexdigest(),
        "handoff_file_sha256": handoff_file_sha,
        "bindings": dict(handoff["bindings"]),
        "issued_utc": _utc(authorization.issued_utc),
        "expires_utc": _utc(authorization.expires_utc),
    }
    _transition(directory, handoff, state=AUTHORIZED,
                transition="SETUP_AUTHORIZED", clock=lambda: now,
                apply_count=0, details={"authorization": authorization_record},
                expected_states=(PREPARED,))
    return authorization


def operator_authorization(run_directory, *, clock=None, ttl_seconds=30,
                           token_factory=token_bytes):
    authorization = authorize_setup(
        run_directory, clock=clock, ttl_seconds=ttl_seconds,
        token_factory=token_factory)
    _, _, handoff, handoff_file_sha = _load_handoff(run_directory)
    return {
        "schema": STATE_SCHEMA,
        "state": AUTHORIZED,
        "run_id": handoff["run_id"],
        "authorization_token": authorization.operator_token(),
        "expires_utc": _utc(authorization.expires_utc),
        "handoff_file_sha256": handoff_file_sha,
        "apply_limit": 1,
        "operator_workflow": [
            "VERIFY_THE_SEALED_VALUES_BELOW",
            "RUN_BEGIN_APPLY_WITH_TOKEN_AND_HANDOFF_SHA256",
            "WAIT_FOR_SETUP_APPLYING_APPLY_COUNT_1_CONFIRMATION",
            "PERFORM_EXACTLY_ONE_NINJATRADER_APPLY",
            "WAIT_FOR_HANDOFF_COMPLETE",
        ],
        "chart_contract": handoff["chart_contract"],
        "settings": handoff["settings"],
        "ninjatrader_setup_authority": True,
        **_ZERO_AUTHORITY,
    }


def _operator_authorization_record(state, handoff, handoff_file_sha,
                                   supplied_token, confirmed_handoff_sha,
                                   now):
    record = state.get("details", {}).get("authorization")
    reason = None
    try:
        token = bytes.fromhex(supplied_token)
    except (TypeError, ValueError):
        token = None
    if type(record) is not dict:
        reason = "DURABLE_SETUP_AUTHORIZATION_REQUIRED"
    elif type(token) is not bytes or len(token) < 32:
        reason = "SETUP_AUTHORIZATION_TOKEN_INVALID"
    elif not compare_digest(
            sha256(token).hexdigest(), record.get("token_sha256", "")):
        reason = "SETUP_AUTHORIZATION_TOKEN_INVALID"
    elif confirmed_handoff_sha != handoff_file_sha:
        reason = "HANDOFF_SHA256_CONFIRMATION_MISMATCH"
    elif record.get("handoff_file_sha256") != handoff_file_sha:
        reason = "SETUP_AUTHORIZATION_BINDING_MISMATCH"
    elif record.get("bindings") != handoff["bindings"]:
        reason = "SETUP_AUTHORIZATION_BINDING_MISMATCH"
    else:
        try:
            expires = _parse_utc(
                record.get("expires_utc"),
                "SETUP_AUTHORIZATION_EXPIRY_INVALID")
            if now > expires:
                reason = "SETUP_AUTHORIZATION_EXPIRED"
        except Phase3Blocked:
            reason = "SETUP_AUTHORIZATION_EXPIRY_INVALID"
    return record, reason


def _validate_operator_hello(evidence, handoff, binding_claim):
    if type(evidence) is not dict:
        raise Phase3Blocked("NATIVE_HELLO_EVIDENCE_INVALID")
    try:
        session = str(UUID(evidence.get("native_session_id")))
    except (ValueError, TypeError, AttributeError) as error:
        raise Phase3Blocked("NATIVE_SESSION_ID_INVALID") from error
    expected = {
        "native_session_id": session,
        "native_runtime_id": handoff["runtime"]["native_runtime_id"],
        "provider": handoff["runtime"]["expected_provider"],
        "binding_nonce": binding_claim["binding_nonce"],
        "binding_claim_sha256": _digest(binding_claim),
        "handoff_file_sha256": binding_claim["handoff_file_sha256"],
    }
    if evidence != expected:
        raise Phase3Blocked("FOREIGN_NATIVE_HELLO_SESSION")
    return session


def begin_operator_apply(run_directory, supplied_token,
                         confirmed_handoff_sha256, *, hello_observer=None,
                         clock=None, monotonic=time.monotonic,
                         sleeper=time.sleep, on_apply_recorded=None,
                         on_native_apply_observed=None,
                         nonce_factory=token_bytes):
    now = _now(clock)
    directory, manifest, handoff, handoff_file_sha = _load_handoff(run_directory)
    state, _ = _load_evidence(directory, handoff)
    if state["state"] != AUTHORIZED or state["apply_count"] != 0:
        raise Phase3Blocked("SETUP_AUTHORIZATION_REQUIRED")
    record, reason = _operator_authorization_record(
        state, handoff, handoff_file_sha, supplied_token,
        confirmed_handoff_sha256, now)
    if reason is not None:
        _transition(
            directory, handoff, state=REVOKED,
            transition="SETUP_AUTHORIZATION_REVOKED", clock=lambda: now,
            apply_count=0, details={"reason": reason},
            expected_states=(AUTHORIZED,))
        raise Phase3Blocked(reason)

    binding_claim = _binding_claim(
        handoff, handoff_file_sha, record, now, nonce_factory(32),
        generation=_next_binding_generation(manifest))
    observer = hello_observer or NativeHelloObserver(handoff, binding_claim)
    attempt = {
        "mode": "PASSIVE_FIXED_BINDING_ONE_SHOT",
        "authorization_token_sha256": record["token_sha256"],
        "confirmed_handoff_file_sha256": confirmed_handoff_sha256,
        "binding_nonce": binding_claim["binding_nonce"],
        "binding_claim_sha256": _digest(binding_claim),
        "binding_control_file": handoff["native_binding"]["control_file"],
    }
    applying = _transition(
        directory, handoff, state=APPLYING,
        transition="SETUP_APPLY_ATTEMPT_RECORDED", clock=lambda: now,
        apply_count=1, details={"operator_attempt": attempt},
        expected_states=(AUTHORIZED,))
    try:
        published_sha = _publish_active_binding(manifest, binding_claim)
        if (published_sha != attempt["binding_claim_sha256"]
                or _load_active_binding(
                    manifest, handoff, handoff_file_sha, now=now)
                != binding_claim):
            raise Phase3Blocked("NATIVE_BINDING_PUBLICATION_INVALID")
        if on_apply_recorded is not None:
            on_apply_recorded(applying)
        _transition(
            directory, handoff, state=AWAITING_HELLO,
            transition="OPERATOR_APPLY_AWAITING_NATIVE_HELLO", clock=clock,
            apply_count=1, details={"operator_attempt": attempt},
            expected_states=(APPLYING,))
        deadline = monotonic() + handoff["hello_timeout_seconds"]
        native_apply_observed = False
        while monotonic() <= deadline:
            receipt_observer = getattr(
                observer, "observe_binding_receipt_evidence", None)
            if not native_apply_observed and callable(receipt_observer):
                receipt = receipt_observer()
                if receipt is not None:
                    native_apply_observed = True
                    if on_native_apply_observed is not None:
                        on_native_apply_observed({
                            "kind": "BINDING_RECEIPT",
                            "native_session_id": receipt["session"],
                        })
            evidence = observer.observe_evidence()
            if evidence is not None:
                session = _validate_operator_hello(
                    evidence, handoff, binding_claim)
                if not native_apply_observed:
                    native_apply_observed = True
                    if on_native_apply_observed is not None:
                        on_native_apply_observed({
                            "kind": "NATIVE_HELLO",
                            "native_session_id": session,
                        })
                _revoke_binding(
                    manifest, run_id=handoff["run_id"],
                    native_runtime_id=handoff["runtime"]["native_runtime_id"],
                    clock=clock,
                    expected_claim_sha256=attempt["binding_claim_sha256"])
                return _transition(
                    directory, handoff, state=COMPLETE,
                    transition="NATIVE_HELLO_ACCEPTED_SETUP_RELINQUISHED",
                    clock=clock, apply_count=1,
                    details={"operator_attempt": attempt,
                             "hello_evidence": evidence,
                             "native_session_id": session},
                    expected_states=(AWAITING_HELLO,))
            sleeper(0.05)
        raise Phase3Blocked("NATIVE_HELLO_TIMEOUT")
    except BaseException as error:
        try:
            _revoke_binding(
                manifest, run_id=handoff["run_id"],
                native_runtime_id=handoff["runtime"]["native_runtime_id"],
                clock=clock,
                expected_claim_sha256=attempt["binding_claim_sha256"])
        except BaseException:
            pass
        current, _ = _load_evidence(directory, handoff)
        if current["state"] in {APPLYING, AWAITING_HELLO}:
            _transition(
                directory, handoff, state=FAILED,
                transition="NATIVE_SETUP_FAILED_CLOSED", clock=clock,
                apply_count=1,
                details={"operator_attempt": attempt,
                         "reason": str(error)},
                expected_states=(APPLYING, AWAITING_HELLO))
        raise


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
                       monotonic=time.monotonic, sleeper=time.sleep,
                       nonce_factory=token_bytes):
    now = _now(clock)
    directory, manifest, handoff, handoff_file_sha = _load_handoff(run_directory)
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

    authorization_record = state["details"]["authorization"]
    binding_claim = _binding_claim(
        handoff, handoff_file_sha, authorization_record, now,
        nonce_factory(32), generation=_next_binding_generation(manifest))
    observer = hello_observer or NativeHelloObserver(handoff, binding_claim)
    adapter = setup_adapter or NativeSetupAdapter()
    _transition(directory, handoff, state=APPLYING,
                transition="SETUP_APPLY_ATTEMPT_RECORDED", clock=lambda: now,
                apply_count=1, expected_states=(AUTHORIZED,))
    try:
        _publish_active_binding(manifest, binding_claim)
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
                _revoke_binding(
                    manifest, run_id=handoff["run_id"],
                    native_runtime_id=handoff["runtime"]["native_runtime_id"],
                    clock=clock,
                    expected_claim_sha256=_digest(binding_claim))
                return _transition(
                    directory, handoff, state=COMPLETE,
                    transition="NATIVE_HELLO_ACCEPTED_SETUP_RELINQUISHED",
                    clock=clock, apply_count=1,
                    details={"receipt": receipt, "native_session_id": observed},
                    expected_states=(AWAITING_HELLO,))
            sleeper(0.05)
        raise Phase3Blocked("NATIVE_HELLO_TIMEOUT")
    except BaseException as error:
        try:
            _revoke_binding(
                manifest, run_id=handoff["run_id"],
                native_runtime_id=handoff["runtime"]["native_runtime_id"],
                clock=clock,
                expected_claim_sha256=_digest(binding_claim))
        except BaseException:
            pass
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


def terminalize_failed_historical_cleanup(
        run_directory, *, clock=None, process_adapter=None):
    """Finish only a revoked, failed handoff's interrupted Phase 2 stop."""
    directory, manifest, phase2_state, bindings = (
        phase2._load_historical_owned_cleanup_plan(
            run_directory, allow_interrupted_stopping=True))
    if phase2_state["state"] != phase2.STOPPING:
        raise Phase3Blocked("INTERRUPTED_HISTORICAL_STOPPING_REQUIRED")
    handoff, _ = phase1._read_json(
        directory / _HANDOFF_NAME, HANDOFF_SCHEMA)
    expected_bindings = {
        **bindings,
        "phase3_source_sha256": manifest["source_pins"][
            PHASE3_SOURCE]["sha256"],
        "phase2_native_setup_sha256": _digest(
            phase2_state["native_setup"]),
    }
    if (handoff.get("run_id") != manifest["run_id"]
            or handoff.get("bindings") != expected_bindings
            or handoff.get("runtime", {}).get("native_runtime_id")
            != phase2_state["native_setup"].get("native_runtime_id")
            or handoff.get("ninjatrader_setup_authority") is not False
            or any(handoff.get(key) is not False for key in _ZERO_AUTHORITY)):
        raise Phase3Blocked("HISTORICAL_FAILED_HANDOFF_BINDING_INVALID")
    phase3_state, _ = _load_evidence(directory, handoff)
    if (phase3_state["state"] != FAILED
            or type(phase3_state.get("details", {}).get("reason")) is not str
            or not phase3_state["details"]["reason"]
            or phase3_state.get("ninjatrader_setup_authority") is not False
            or any(phase3_state.get(key) is not False
                   for key in _ZERO_AUTHORITY)):
        raise Phase3Blocked("TERMINAL_FAILED_HANDOFF_REQUIRED")

    runtime_parent = Path(
        manifest["targets"]["runtime_parent"]).resolve(strict=False)
    binding_file = (runtime_parent.parent / _BINDING_DIRECTORY_NAME
                    / _BINDING_FILE_NAME).resolve(strict=False)
    if handoff.get("native_binding", {}).get("control_file") != str(binding_file):
        raise Phase3Blocked("HISTORICAL_BINDING_PATH_INVALID")
    binding, _ = phase1._read_json(binding_file, BINDING_CONTROL_SCHEMA)
    expected_binding_fields = {
        "schema", "state", "one_click_run_id", "native_runtime_id",
        "revoked_utc", *_ZERO_AUTHORITY,
    }
    if (set(binding) not in {
            frozenset(expected_binding_fields),
            frozenset((*expected_binding_fields, "generation"))}
            or binding.get("state") != "REVOKED"
            or binding.get("one_click_run_id") != manifest["run_id"]
            or binding.get("native_runtime_id")
            != handoff["runtime"]["native_runtime_id"]
            or any(binding.get(key) is not False for key in _ZERO_AUTHORITY)):
        raise Phase3Blocked("HISTORICAL_BINDING_NOT_REVOKED")
    _parse_utc(binding.get("revoked_utc"), "HISTORICAL_BINDING_NOT_REVOKED")

    phase3_before = {
        name: (directory / name).read_bytes()
        for name in (_HANDOFF_NAME, _EVENTS_NAME, _STATE_NAME)
    }
    final = phase2._terminalize_interrupted_historical_cleanup(
        directory, clock=clock, process_adapter=process_adapter)
    if any((directory / name).read_bytes() != raw
           for name, raw in phase3_before.items()):
        raise Phase3Blocked("PHASE3_HISTORY_MUTATED_DURING_CLEANUP")
    return final


def _print(value):
    print(json.dumps(value, sort_keys=True, indent=2, allow_nan=False))


def _announce_operator_apply(state):
    _print({
        "schema": STATE_SCHEMA,
        "state": state["state"],
        "apply_count": state["apply_count"],
        "operator_action": "PERFORM_EXACTLY_ONE_NINJATRADER_APPLY_NOW",
        "ninjatrader_setup_authority": True,
        **_ZERO_AUTHORITY,
    })
    sys.stdout.flush()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--run", type=Path, required=True)
    prepare.add_argument("--runtime", type=Path, required=True)
    authorize = commands.add_parser("authorize")
    authorize.add_argument("--run", type=Path, required=True)
    authorize.add_argument("--ttl-seconds", type=float, default=30)
    begin_apply = commands.add_parser("begin-apply")
    begin_apply.add_argument("--run", type=Path, required=True)
    begin_apply.add_argument("--token", required=True)
    begin_apply.add_argument("--confirm-handoff-sha256", required=True)
    status_parser = commands.add_parser("status")
    status_parser.add_argument("--run", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            result = prepare_handoff(args.run, args.runtime)
        elif args.command == "authorize":
            result = operator_authorization(
                args.run, ttl_seconds=args.ttl_seconds)
        elif args.command == "begin-apply":
            result = begin_operator_apply(
                args.run, args.token, args.confirm_handoff_sha256,
                on_apply_recorded=_announce_operator_apply)
        else:
            result = status(args.run)
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
