"""ARMS One-Click Runtime V1 Phase 1: offline preparation only.

Start validates a reviewed profile and creates a sealed plan for a future
supervised Current-PAPER run. It never executes that plan. Status and audit
are read-only. Stop only closes a plan that never started.
"""

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sys
from uuid import uuid4

PROFILE_SCHEMA = "arms.one-click-runtime-profile.v1"
MANIFEST_SCHEMA = "arms.one-click-runtime-manifest.v1"
SEAL_SCHEMA = "arms.one-click-runtime-seal.v1"
STATE_SCHEMA = "arms.one-click-runtime-state.v1"
EVENT_SCHEMA = "arms.one-click-runtime-event.v1"
AUDIT_SCHEMA = "arms.one-click-runtime-audit.v1"
MAX_JSON_BYTES = 4 * 1024 * 1024
MAX_INPUT_BYTES = 64 * 1024 * 1024
PREPARED = "PREPARED_OFFLINE"
STOPPED = "STOPPED_OFFLINE"
BLOCKED = "BLOCKED"
BLOCKED_SOURCE_DRIFT = "BLOCKED_SOURCE_DRIFT"
REVIEWED_PROFILE_VERSION = "PHASE_1B_REAL_OFFLINE_V1"
SOURCE_BINDING_PASS = "PASS"
PATH_POLICY_PASS = "PASS"

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORKSPACE = REPO_ROOT / ".arms-one-click-runtime-v1" / "runs"
ARTIFACT_FIELDS = (
    "installed_exporter", "bootstrap_evidence",
    "startup_chart_catchup_source", "native_spec", "paper_config",
)
LEGACY_PROFILE_FIELDS = {
    "schema", "mode", "execution_authority", "live_authority",
    "external_order_authority", "python_path", *ARTIFACT_FIELDS,
    "runtime_parent", "paper_namespace_parent", "news_parent", "l1_parent",
    "ports", "admin_token_env", "startup_chart_catchup_timeout_seconds",
}
REVIEWED_PROFILE_FIELDS = LEGACY_PROFILE_FIELDS | {
    "reviewed_profile_version", "future_runtime_execution_enabled",
    "python_identity", "market_identity", "risk_and_execution_parameters",
    "runtime_environment",
    "path_templates", "stable_path_policy", "private_acl_required",
    "excluded_active_run_ids", "reviewed_source_pins",
}
PORT_FIELDS = {"backend", "frontend", "paper"}
PATH_TEMPLATE_FIELDS = {
    "analysis_namespace", "market_inbox", "catchup_directory",
    "external_private_l1_root", "paper_run_namespace", "command_channel",
    "current_paper_news_root", "local_dumps", "runtime_evidence_directory",
}
REVIEWED_SOURCE_NAMES = {
    "scripts/arms-runtime-v1.ps1",
    "tools/arms_one_click_runtime_v1.py",
    "tools/arms_one_click_runtime_phase2_v1.py",
    "tools/arms_one_click_runtime_phase3_v1.py",
    "tools/start_native_current_paper_v1.py",
    "tools/windows_runtime_supervisor_v1.py",
    "tools/analysis_native_startup_v1.py",
    "tools/startup_chart_catchup_v1.py",
}
REVIEWED_PYTHON_IDENTITY = {
    "implementation": "CPython", "version": "3.13.16",
    "architecture": "x64", "gil": "STANDARD",
}
REVIEWED_MARKET_IDENTITY = {
    "provider": "Provider31", "canonical_provider": "NINJATRADER:Provider31",
    "instrument": "NQ", "contract": "NQ DEC26", "expiry": "2026-12-01",
    "trading_hours": "CME US Index Futures ETH", "bars_period": "Minute",
    "bars_value": 1, "source_timezone": "UTC",
}
REVIEWED_RISK_AND_EXECUTION = {
    "risk_percent": 0.5, "minimum_reward_risk_ratio": 2.0,
    "minimum_stop_points": 1.0, "maximum_stop_points": 100.0,
    "maximum_spread_points": 5.0, "minimum_atr_points": 1.0,
    "maximum_quote_age_seconds": 30.0,
    "maximum_signal_age_seconds": 300,
    "minimum_probability": 0.80, "minimum_confluence": 0.80,
    "minimum_trade_quality": 85, "maximum_open_positions": 1,
    "paper_boundary": 80.5, "paper_stop_loss_points": 30.0,
    "paper_take_profit_points": 60.0, "fee_per_contract_side": 5.0,
    "slippage_ticks_side": 2,
}
REVIEWED_RUNTIME_ENVIRONMENT = {
    "ARMS_MAXIMUM_QUOTE_AGE_SECONDS": "30",
    "ARMS_MINIMUM_REWARD_RISK_RATIO": "2.0",
    "ARMS_MINIMUM_STOP_POINTS": "1",
    "ARMS_MAXIMUM_STOP_POINTS": "100",
    "ARMS_MAXIMUM_SPREAD_POINTS": "5",
    "ARMS_MINIMUM_ATR_POINTS": "1",
    "ARMS_MINIMUM_A_PLUS_PROBABILITY": "0.80",
    "ARMS_MINIMUM_A_PLUS_CONFLUENCE_SCORE": "0.80",
    "ARMS_MAXIMUM_SIGNAL_AGE_SECONDS": "300",
    "ARMS_MAXIMUM_OPEN_POSITIONS": "1",
}
REVIEWED_PAPER_CONFIG = {
    "version": "sprint07r-paper-80.5-v1", "mode": "PAPER_RESEARCH",
    "boundary": 80.5, "quality": 85, "ema": 10, "stop_loss": 30,
    "take_profit": 60, "fee_per_contract_side": 5.0,
    "slippage_ticks_side": 2, "live_execution_allowed": False,
    "research_evidence_sha256":
        "9e4542e57c9fc922cc0ad0fc3f104d072d24190f458260f842ff49fd15229855",
}
REVIEWED_STABLE_PATH_POLICY = {
    "mechanism": "ATOMIC_JSON_POINTER",
    "atomic_publication_required": True,
    "pointer_switch_during_active_run_allowed": False,
    "pointer_switch_performed_by_offline_start": False,
    "stale_run_cross_binding_allowed": False,
    "historical_run_mutation_allowed": False,
}
RUN_ID_PATTERN = re.compile(r"^[0-9]{8}T[0-9]{6}Z-oneclick-[0-9a-f]{12}$")
ENV_NAME_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{2,127}$")
ACTIVE_RUN_ID_PATTERN = re.compile(
    r"^[0-9]{8}T[0-9]{6}Z-[A-Za-z0-9-]+-[0-9a-f]{8}$")


class OfflineBlocked(ValueError):
    """A fail-closed validation result with no execution authority."""


def _utc_now(clock=None):
    value = (clock or (lambda: datetime.now(timezone.utc)))()
    if value.tzinfo is None or value.utcoffset() is None:
        raise OfflineBlocked("UTC_CLOCK_REQUIRED")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def _digest_bytes(raw):
    return sha256(raw).hexdigest()


def _event_digest(event):
    unsigned = dict(event)
    unsigned.pop("event_sha256", None)
    return _digest_bytes(_canonical(unsigned))


def _read_json(path, expected_schema=None):
    path = Path(path)
    try:
        size = path.stat().st_size
        if not 0 < size <= MAX_JSON_BYTES or not path.is_file():
            raise OfflineBlocked("JSON_SIZE_OR_TYPE_INVALID:" + path.name)
        raw = path.read_bytes()
        if len(raw) != size:
            raise OfflineBlocked("JSON_CHANGED_DURING_READ:" + path.name)
        value = json.loads(raw.decode("utf-8"))
    except OfflineBlocked:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError) as error:
        raise OfflineBlocked("JSON_UNAVAILABLE_OR_INVALID:" + path.name) from error
    if type(value) is not dict:
        raise OfflineBlocked("JSON_OBJECT_REQUIRED:" + path.name)
    if expected_schema is not None and value.get("schema") != expected_schema:
        raise OfflineBlocked("SCHEMA_INVALID:" + path.name)
    return value, raw


def _atomic_json(path, value, *, exclusive=False):
    path = Path(path)
    raw = json.dumps(value, sort_keys=True, indent=2,
                     allow_nan=False).encode("utf-8") + b"\n"
    if len(raw) > MAX_JSON_BYTES:
        raise OfflineBlocked("JSON_TOO_LARGE:" + path.name)
    temporary = path.with_name(path.name + "." + uuid4().hex + ".tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        if exclusive and path.exists():
            raise FileExistsError(str(path))
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return _digest_bytes(raw)


def _absolute(path_value, *, base):
    if type(path_value) is not str or not path_value.strip():
        raise OfflineBlocked("PATH_REQUIRED")
    candidate = Path(path_value)
    if not candidate.is_absolute():
        candidate = base / candidate
    return candidate.resolve(strict=False)


def _hash_stable_file(path, expected=None):
    path = Path(path)
    try:
        before = path.stat()
        if not path.is_file() or not 0 < before.st_size <= MAX_INPUT_BYTES:
            raise OfflineBlocked("INPUT_SIZE_OR_TYPE_INVALID:" + path.name)
        raw = path.read_bytes()
        after = path.stat()
    except OfflineBlocked:
        raise
    except OSError as error:
        raise OfflineBlocked("INPUT_UNAVAILABLE:" + path.name) from error
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise OfflineBlocked("INPUT_CHANGED_DURING_READ:" + path.name)
    actual = _digest_bytes(raw)
    if expected is not None and actual != expected:
        raise OfflineBlocked(
            "PROFILE_STATUS=" + BLOCKED_SOURCE_DRIFT
            + ":INPUT_SHA256_MISMATCH:" + path.name)
    return raw, actual, before.st_size


def _validate_hash(value):
    return (type(value) is str and len(value) == 64
            and all(character in "0123456789abcdef" for character in value))


def _is_within(path, parent):
    try:
        Path(path).relative_to(Path(parent))
        return True
    except ValueError:
        return False


def _validate_reviewed_descriptor(name, descriptor):
    if (type(descriptor) is not dict
            or set(descriptor) != {"path", "sha256"}
            or not _validate_hash(descriptor.get("sha256"))):
        raise OfflineBlocked("REVIEWED_SOURCE_DESCRIPTOR_INVALID:" + name)
    path = _absolute(descriptor["path"], base=REPO_ROOT)
    _, digest, size = _hash_stable_file(path, descriptor["sha256"])
    return {"path": str(path), "sha256": digest, "bytes": size}


def _resolve_path_templates(validated, run_id):
    return {
        name: _absolute(template.replace("{RUN_ID}", run_id), base=REPO_ROOT)
        for name, template in validated["path_templates"].items()
    }


def _validate_reviewed_profile(profile, python_path):
    if profile["reviewed_profile_version"] != REVIEWED_PROFILE_VERSION:
        raise OfflineBlocked("REVIEWED_PROFILE_VERSION_INVALID")
    if profile["future_runtime_execution_enabled"] is not False:
        raise OfflineBlocked("FUTURE_RUNTIME_EXECUTION_MUST_REMAIN_DISABLED")
    python_identity = profile["python_identity"]
    if (type(python_identity) is not dict
            or set(python_identity) != {*REVIEWED_PYTHON_IDENTITY, "sha256"}
            or {key: python_identity.get(key) for key in REVIEWED_PYTHON_IDENTITY}
            != REVIEWED_PYTHON_IDENTITY
            or not _validate_hash(python_identity.get("sha256"))):
        raise OfflineBlocked("PYTHON_IDENTITY_INVALID")
    _hash_stable_file(python_path, python_identity["sha256"])
    if profile["market_identity"] != REVIEWED_MARKET_IDENTITY:
        raise OfflineBlocked("MARKET_IDENTITY_INVALID")
    if profile["risk_and_execution_parameters"] != REVIEWED_RISK_AND_EXECUTION:
        raise OfflineBlocked("RISK_AND_EXECUTION_PARAMETERS_INVALID")
    if profile["runtime_environment"] != REVIEWED_RUNTIME_ENVIRONMENT:
        raise OfflineBlocked("RUNTIME_ENVIRONMENT_INVALID")
    if profile["private_acl_required"] is not True:
        raise OfflineBlocked("PRIVATE_ACL_REQUIRED")

    excluded = profile["excluded_active_run_ids"]
    if (type(excluded) is not list or not excluded
            or len(excluded) != len(set(excluded))
            or any(type(value) is not str
                   or not ACTIVE_RUN_ID_PATTERN.fullmatch(value)
                   for value in excluded)):
        raise OfflineBlocked("EXCLUDED_ACTIVE_RUN_IDS_INVALID")

    templates = profile["path_templates"]
    if type(templates) is not dict or set(templates) != PATH_TEMPLATE_FIELDS:
        raise OfflineBlocked("PATH_TEMPLATE_FIELDS_INVALID")
    for name, template in templates.items():
        remainder = template.replace("{RUN_ID}", "") if type(template) is str else ""
        if (type(template) is not str or template.count("{RUN_ID}") != 1
                or "{" in remainder or "}" in remainder
                or any(run_id.casefold() in template.casefold()
                       for run_id in excluded)):
            raise OfflineBlocked("PATH_TEMPLATE_INVALID:" + name)
    sample_run_id = "20990101T000000Z-oneclick-000000000000"
    resolved = {
        name: _absolute(template.replace("{RUN_ID}", sample_run_id),
                        base=REPO_ROOT)
        for name, template in templates.items()
    }
    if (resolved["market_inbox"].parent != resolved["analysis_namespace"]
            or resolved["catchup_directory"].parent
            != resolved["analysis_namespace"]
            or resolved["command_channel"].parent
            != resolved["paper_run_namespace"]
            or resolved["local_dumps"].parent
            != resolved["runtime_evidence_directory"]):
        raise OfflineBlocked("PATH_TEMPLATE_RELATIONSHIP_INVALID")
    if _is_within(resolved["external_private_l1_root"], REPO_ROOT):
        raise OfflineBlocked("EXTERNAL_L1_MUST_BE_OUTSIDE_REPOSITORY")
    if len({str(path).casefold() for path in resolved.values()}) != len(resolved):
        raise OfflineBlocked("PATH_TEMPLATES_MUST_BE_DISTINCT")

    stable = profile["stable_path_policy"]
    if (type(stable) is not dict
            or set(stable) != {*REVIEWED_STABLE_PATH_POLICY, "pointer_path"}
            or {key: stable.get(key) for key in REVIEWED_STABLE_PATH_POLICY}
            != REVIEWED_STABLE_PATH_POLICY):
        raise OfflineBlocked("STABLE_PATH_POLICY_INVALID")
    pointer_path = _absolute(stable.get("pointer_path"), base=REPO_ROOT)
    if "{RUN_ID}" in stable["pointer_path"]:
        raise OfflineBlocked("STABLE_POINTER_PATH_INVALID")

    source_pins = profile["reviewed_source_pins"]
    if type(source_pins) is not dict or set(source_pins) != REVIEWED_SOURCE_NAMES:
        raise OfflineBlocked("REVIEWED_SOURCE_INVENTORY_INVALID")
    validated_sources = {
        name: _validate_reviewed_descriptor(name, descriptor)
        for name, descriptor in source_pins.items()
    }
    return {
        "path_templates": dict(templates), "stable_pointer": pointer_path,
        "source_pins": validated_sources, "excluded_active_run_ids": excluded,
        "runtime_environment": dict(profile["runtime_environment"]),
    }


def _validate_profile(profile_path):
    profile_path = Path(profile_path).resolve(strict=True)
    profile, profile_raw = _read_json(profile_path, PROFILE_SCHEMA)
    fields = set(profile)
    reviewed = fields == REVIEWED_PROFILE_FIELDS
    if not reviewed and fields != LEGACY_PROFILE_FIELDS:
        raise OfflineBlocked("PROFILE_FIELDS_INVALID")
    if (profile["mode"] != "OFFLINE_ONLY"
            or profile["execution_authority"] is not False
            or profile["live_authority"] is not False
            or profile["external_order_authority"] is not False):
        raise OfflineBlocked("OFFLINE_ZERO_AUTHORITY_REQUIRED")

    python_path = _absolute(profile["python_path"], base=REPO_ROOT)
    reviewed_values = (_validate_reviewed_profile(profile, python_path)
                       if reviewed else None)
    python_expected = (profile["python_identity"]["sha256"]
                       if reviewed else None)
    _, python_hash, python_size = _hash_stable_file(python_path, python_expected)
    inputs = {"python": {"path": str(python_path), "sha256": python_hash,
                         "bytes": python_size}}
    raw_inputs = {}
    for field in ARTIFACT_FIELDS:
        descriptor = profile[field]
        if type(descriptor) is not dict or set(descriptor) != {"path", "sha256"}:
            raise OfflineBlocked("ARTIFACT_DESCRIPTOR_INVALID:" + field)
        if not _validate_hash(descriptor["sha256"]):
            raise OfflineBlocked("ARTIFACT_SHA256_INVALID:" + field)
        path = _absolute(descriptor["path"], base=REPO_ROOT)
        raw, actual, size = _hash_stable_file(path, descriptor["sha256"])
        inputs[field] = {"path": str(path), "sha256": actual, "bytes": size}
        raw_inputs[field] = raw

    try:
        native_spec = json.loads(raw_inputs["native_spec"].decode("utf-8"))
        paper_config = json.loads(raw_inputs["paper_config"].decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise OfflineBlocked("RUNTIME_JSON_INPUT_INVALID") from error
    if type(native_spec) is not dict or (
            native_spec.get("schema") != "arms.native-capture-spec.sprint13.v1"
            or native_spec.get("unknown_policy") != "FAIL_CLOSED"
            or native_spec.get("order_authority") is not False):
        raise OfflineBlocked("NATIVE_SPEC_FAIL_CLOSED_CONTRACT_REQUIRED")
    if type(paper_config) is not dict:
        raise OfflineBlocked("PAPER_CONFIG_OBJECT_REQUIRED")
    if reviewed:
        contract = native_spec.get("contract")
        if (native_spec.get("provider_enum") != "Provider31"
                or type(contract) is not dict
                or contract.get("provider") != "Provider31"
                or contract.get("instrument") != "NQ"
                or contract.get("contract") != "NQ DEC26"
                or native_spec.get("expiry") != "2026-12-01"
                or contract.get("trading_hours_template")
                != "CME US Index Futures ETH"):
            raise OfflineBlocked("NATIVE_SPEC_MARKET_IDENTITY_INVALID")
        if paper_config != REVIEWED_PAPER_CONFIG:
            raise OfflineBlocked("CERTIFIED_PAPER_CONFIG_INVALID")

    ports = profile["ports"]
    if type(ports) is not dict or set(ports) != PORT_FIELDS:
        raise OfflineBlocked("PORT_FIELDS_INVALID")
    if (any(type(value) is not int or isinstance(value, bool)
            or not 1024 <= value <= 65535 for value in ports.values())
            or len(set(ports.values())) != 3):
        raise OfflineBlocked("DISTINCT_BOUNDED_PORTS_REQUIRED")
    timeout = profile["startup_chart_catchup_timeout_seconds"]
    if (type(timeout) not in (int, float) or isinstance(timeout, bool)
            or not 0 < timeout <= 900):
        raise OfflineBlocked("CATCHUP_TIMEOUT_INVALID")
    if not ENV_NAME_PATTERN.fullmatch(profile["admin_token_env"]):
        raise OfflineBlocked("ADMIN_TOKEN_ENV_NAME_INVALID")

    parents = {}
    for field in ("runtime_parent", "paper_namespace_parent",
                  "news_parent", "l1_parent"):
        parents[field] = _absolute(profile[field], base=REPO_ROOT)
    if len({str(path).casefold() for path in parents.values()}) != len(parents):
        raise OfflineBlocked("DESTINATION_PARENTS_MUST_BE_DISTINCT")
    if reviewed:
        templates = reviewed_values["path_templates"]
        sample = "20990101T000000Z-oneclick-000000000000"
        template_paths = {
            name: _absolute(value.replace("{RUN_ID}", sample), base=REPO_ROOT)
            for name, value in templates.items()
        }
        relationships = {
            "runtime_parent": template_paths["analysis_namespace"].parent,
            "paper_namespace_parent": template_paths["paper_run_namespace"].parent,
            "news_parent": template_paths["current_paper_news_root"].parent,
            "l1_parent": template_paths["external_private_l1_root"].parent,
        }
        if any(parents[name] != expected
               for name, expected in relationships.items()):
            raise OfflineBlocked("PATH_TEMPLATE_PARENT_MISMATCH")
    return {
        "profile_path": profile_path,
        "profile_sha256": _digest_bytes(profile_raw),
        "profile": profile, "inputs": inputs, "parents": parents,
        "ports": dict(ports), "timeout": timeout, "reviewed": reviewed,
        "path_templates": (reviewed_values["path_templates"]
                           if reviewed else None),
        "source_pins": (reviewed_values["source_pins"]
                        if reviewed else None),
        "runtime_environment": (reviewed_values["runtime_environment"]
                                if reviewed else {}),
        "excluded_active_run_ids": (reviewed_values["excluded_active_run_ids"]
                                    if reviewed else []),
    }


def _new_run_id(now, identity=None):
    prefix = now.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    value = prefix + "-oneclick-" + (identity or uuid4()).hex[:12]
    if not RUN_ID_PATTERN.fullmatch(value):
        raise OfflineBlocked("RUN_ID_INVALID")
    return value


def _build_manifest(validated, run_id, run_directory, created_utc):
    reviewed_targets = (_resolve_path_templates(validated, run_id)
                        if validated["reviewed"] else {})
    targets = {
        "plan_directory": str(run_directory),
        "supervisor_stop_request": str(
            run_directory / "phase2-stop-request.json"),
        "supervisor_report_directory": str(
            reviewed_targets.get(
                "runtime_evidence_directory", run_directory) / "supervisor"),
        "runtime_parent": str(validated["parents"]["runtime_parent"]),
        "paper_run_namespace": str(
            reviewed_targets.get(
                "paper_run_namespace",
                validated["parents"]["paper_namespace_parent"] / run_id)),
        "current_paper_news_root": str(
            reviewed_targets.get(
                "current_paper_news_root",
                validated["parents"]["news_parent"] / run_id)),
        "current_paper_l1_directory": str(
            reviewed_targets.get(
                "external_private_l1_root",
                validated["parents"]["l1_parent"] / run_id)),
    }
    collision_targets = {
        key: value for key, value in targets.items()
        if key not in {"plan_directory", "runtime_parent"}
    }
    collision_targets.update({
        "analysis_namespace": str(reviewed_targets["analysis_namespace"]),
        "runtime_evidence_directory": str(
            reviewed_targets["runtime_evidence_directory"]),
    } if validated["reviewed"] else {})
    collisions = [key for key, value in collision_targets.items()
                  if Path(value).exists()]
    if collisions:
        raise OfflineBlocked("FRESH_DESTINATIONS_REQUIRED:" + ",".join(collisions))
    if any(excluded.casefold() in str(path).casefold()
           for excluded in validated["excluded_active_run_ids"]
           for path in reviewed_targets.values()):
        raise OfflineBlocked("ACTIVE_RUN_COLLISION")

    inputs = validated["inputs"]
    profile = validated["profile"]
    python_path = inputs["python"]["path"]
    launcher = [
        python_path, "-B", "-m", "tools.start_native_current_paper_v1",
        "--start-current-paper",
        "--installed-exporter", inputs["installed_exporter"]["path"],
        "--bootstrap-evidence", inputs["bootstrap_evidence"]["path"],
        "--bootstrap-sha256", inputs["bootstrap_evidence"]["sha256"],
        "--startup-chart-catchup-source",
        inputs["startup_chart_catchup_source"]["path"],
        "--startup-chart-catchup-timeout", str(validated["timeout"]),
        "--native-spec", inputs["native_spec"]["path"],
        "--native-spec-sha256", inputs["native_spec"]["sha256"],
        "--paper-config", inputs["paper_config"]["path"],
        "--runtime-parent", targets["runtime_parent"],
        "--paper-run-namespace", targets["paper_run_namespace"],
        "--current-paper-news-root", targets["current_paper_news_root"],
        "--current-paper-l1-directory", targets["current_paper_l1_directory"],
        "--port", str(validated["ports"]["backend"]),
        "--frontend-port", str(validated["ports"]["frontend"]),
        "--paper-port", str(validated["ports"]["paper"]),
        "--admin-token-env", profile["admin_token_env"],
    ]
    command = [
        python_path, "-B", "-m", "tools.windows_runtime_supervisor_v1",
        "--run-id", run_id,
        "--report-directory", targets["supervisor_report_directory"],
        "--stop-request", targets["supervisor_stop_request"],
        "--cwd", str(REPO_ROOT),
        "--owned-port", str(validated["ports"]["backend"]),
        "--owned-port", str(validated["ports"]["frontend"]),
        "--owned-port", str(validated["ports"]["paper"]),
        "--", *launcher,
    ]
    source_pins = validated["source_pins"]
    if source_pins is None:
        source_pins = {}
        source_names = (
            "tools/start_native_current_paper_v1.py",
            "tools/windows_runtime_supervisor_v1.py",
        )
        for name in source_names:
            _, digest, size = _hash_stable_file(REPO_ROOT / name)
            source_pins[name] = {"sha256": digest, "bytes": size}
    else:
        source_pins = {
            name: {"path": descriptor["path"],
                   "sha256": descriptor["sha256"],
                   "bytes": descriptor["bytes"]}
            for name, descriptor in source_pins.items()
        }
    return {
        "schema": MANIFEST_SCHEMA, "phase": 1, "run_id": run_id,
        "created_utc": created_utc, "mode": "OFFLINE_ONLY",
        "execution_authority": False, "live_authority": False,
        "external_order_authority": False, "native_apply_authority": False,
        "process_start_authority": False,
        "profile": {"path": str(validated["profile_path"]),
                    "sha256": validated["profile_sha256"]},
        "inputs": inputs, "source_pins": source_pins,
        "runtime_environment": validated["runtime_environment"],
        "ports": validated["ports"], "targets": targets,
        "startup_chart_catchup_timeout_seconds": validated["timeout"],
        "admin_token": {
            "environment_name": profile["admin_token_env"],
            "value_captured": False, "validated_offline": False,
        },
        "disabled_future_start_command": command,
        "command_execution_performed": False,
    }


def _expected_future_command(manifest):
    inputs = manifest["inputs"]
    targets = manifest["targets"]
    ports = manifest["ports"]
    python_path = inputs["python"]["path"]
    launcher = [
        python_path, "-B", "-m", "tools.start_native_current_paper_v1",
        "--start-current-paper",
        "--installed-exporter", inputs["installed_exporter"]["path"],
        "--bootstrap-evidence", inputs["bootstrap_evidence"]["path"],
        "--bootstrap-sha256", inputs["bootstrap_evidence"]["sha256"],
        "--startup-chart-catchup-source",
        inputs["startup_chart_catchup_source"]["path"],
        "--startup-chart-catchup-timeout",
        str(manifest["startup_chart_catchup_timeout_seconds"]),
        "--native-spec", inputs["native_spec"]["path"],
        "--native-spec-sha256", inputs["native_spec"]["sha256"],
        "--paper-config", inputs["paper_config"]["path"],
        "--runtime-parent", targets["runtime_parent"],
        "--paper-run-namespace", targets["paper_run_namespace"],
        "--current-paper-news-root", targets["current_paper_news_root"],
        "--current-paper-l1-directory", targets["current_paper_l1_directory"],
        "--port", str(ports["backend"]),
        "--frontend-port", str(ports["frontend"]),
        "--paper-port", str(ports["paper"]),
        "--admin-token-env", manifest["admin_token"]["environment_name"],
    ]
    return [
        python_path, "-B", "-m", "tools.windows_runtime_supervisor_v1",
        "--run-id", manifest["run_id"],
        "--report-directory", targets["supervisor_report_directory"],
        "--stop-request", targets["supervisor_stop_request"],
        "--cwd", str(REPO_ROOT),
        "--owned-port", str(ports["backend"]),
        "--owned-port", str(ports["frontend"]),
        "--owned-port", str(ports["paper"]),
        "--", *launcher,
    ]


def _make_event(*, run_id, sequence, timestamp, previous, transition, state):
    event = {
        "schema": EVENT_SCHEMA, "run_id": run_id, "sequence": sequence,
        "timestamp_utc": timestamp, "previous_event_sha256": previous,
        "transition": transition, "state": state,
        "execution_started": False, "process_control_performed": False,
    }
    event["event_sha256"] = _event_digest(event)
    return event


def _state_from_event(event, manifest_sha256):
    return {
        "schema": STATE_SCHEMA, "run_id": event["run_id"],
        "state": event["state"], "sequence": event["sequence"],
        "last_event_sha256": event["event_sha256"],
        "manifest_sha256": manifest_sha256, "execution_started": False,
        "process_control_performed": False,
    }


def prepare(profile_path, *, workspace=DEFAULT_WORKSPACE, clock=None, identity=None):
    """Validate and seal a fresh offline plan. No process is started."""
    validated = _validate_profile(profile_path)
    now_value = (clock or (lambda: datetime.now(timezone.utc)))()
    created_utc = _utc_now(lambda: now_value)
    run_id = _new_run_id(now_value, identity)
    workspace = Path(workspace).resolve(strict=False)
    run_directory = workspace / run_id
    if run_directory.exists():
        raise OfflineBlocked("FRESH_PLAN_DIRECTORY_REQUIRED")
    manifest = _build_manifest(validated, run_id, run_directory, created_utc)
    workspace.mkdir(parents=True, exist_ok=True)
    staging = workspace / ("." + run_id + "." + uuid4().hex + ".tmp")
    staging.mkdir(exist_ok=False)
    evidence_names = ("manifest.json", "seal.json", "events.json", "state.json")
    try:
        manifest_sha256 = _atomic_json(
            staging / "manifest.json", manifest, exclusive=True)
        seal = {
            "schema": SEAL_SCHEMA, "run_id": run_id,
            "manifest_sha256": manifest_sha256, "sealed_utc": created_utc,
        }
        _atomic_json(staging / "seal.json", seal, exclusive=True)
        event = _make_event(
            run_id=run_id, sequence=1, timestamp=created_utc, previous=None,
            transition="OFFLINE_PLAN_PREPARED", state=PREPARED)
        _atomic_json(
            staging / "events.json", {"schema": EVENT_SCHEMA,
                                      "events": [event]}, exclusive=True)
        _atomic_json(
            staging / "state.json",
            _state_from_event(event, manifest_sha256), exclusive=True)
        os.replace(staging, run_directory)
    finally:
        if staging.exists():
            for name in evidence_names:
                (staging / name).unlink(missing_ok=True)
            staging.rmdir()
    return status(run_directory)


def _load_and_verify(run_directory, *, rehash_inputs=True,
                     allow_runtime_targets=False):
    run_directory = Path(run_directory).resolve(strict=True)
    manifest, manifest_raw = _read_json(
        run_directory / "manifest.json", MANIFEST_SCHEMA)
    seal, _ = _read_json(run_directory / "seal.json", SEAL_SCHEMA)
    state_value, _ = _read_json(run_directory / "state.json", STATE_SCHEMA)
    events_value, _ = _read_json(run_directory / "events.json", EVENT_SCHEMA)
    run_id = manifest.get("run_id")
    if (type(run_id) is not str or not RUN_ID_PATTERN.fullmatch(run_id)
            or run_directory.name != run_id
            or seal.get("run_id") != run_id
            or state_value.get("run_id") != run_id):
        raise OfflineBlocked("RUN_IDENTITY_MISMATCH")
    manifest_hash = _digest_bytes(manifest_raw)
    if seal.get("manifest_sha256") != manifest_hash:
        raise OfflineBlocked("MANIFEST_SEAL_MISMATCH")
    authority_fields = (
        "execution_authority", "live_authority", "external_order_authority",
        "native_apply_authority", "process_start_authority",
    )
    if (manifest.get("mode") != "OFFLINE_ONLY"
            or any(manifest.get(field) is not False for field in authority_fields)
            or manifest.get("command_execution_performed") is not False):
        raise OfflineBlocked("ZERO_AUTHORITY_MANIFEST_REQUIRED")
    manifest_fields = {
        "schema", "phase", "run_id", "created_utc", "mode",
        "execution_authority", "live_authority", "external_order_authority",
        "native_apply_authority", "process_start_authority", "profile",
        "inputs", "source_pins", "ports", "targets",
        "runtime_environment",
        "startup_chart_catchup_timeout_seconds", "admin_token",
        "disabled_future_start_command", "command_execution_performed",
    }
    if set(manifest) != manifest_fields or manifest.get("phase") != 1:
        raise OfflineBlocked("MANIFEST_FIELDS_INVALID")
    profile = manifest.get("profile")
    if (type(profile) is not dict or set(profile) != {"path", "sha256"}
            or not _validate_hash(profile.get("sha256"))):
        raise OfflineBlocked("PROFILE_IDENTITY_INVALID")
    _hash_stable_file(profile["path"], profile["sha256"])
    validated_profile = _validate_profile(profile["path"])
    if validated_profile["profile_sha256"] != profile["sha256"]:
        raise OfflineBlocked("PROFILE_IDENTITY_MISMATCH")
    runtime_environment = manifest.get("runtime_environment")
    if (runtime_environment != validated_profile["runtime_environment"]
            or (validated_profile["reviewed"] and runtime_environment
                != REVIEWED_RUNTIME_ENVIRONMENT)):
        raise OfflineBlocked("RUNTIME_ENVIRONMENT_BINDING_INVALID")
    ports = manifest.get("ports")
    if (type(ports) is not dict or set(ports) != PORT_FIELDS
            or any(type(value) is not int or isinstance(value, bool)
                   or not 1024 <= value <= 65535 for value in ports.values())
            or len(set(ports.values())) != 3):
        raise OfflineBlocked("MANIFEST_PORTS_INVALID")
    timeout = manifest.get("startup_chart_catchup_timeout_seconds")
    if (type(timeout) not in (int, float) or isinstance(timeout, bool)
            or not 0 < timeout <= 900):
        raise OfflineBlocked("MANIFEST_CATCHUP_TIMEOUT_INVALID")
    admin_token = manifest.get("admin_token")
    if (type(admin_token) is not dict or set(admin_token) != {
            "environment_name", "value_captured", "validated_offline"}
            or type(admin_token.get("environment_name")) is not str
            or not ENV_NAME_PATTERN.fullmatch(
                admin_token.get("environment_name", ""))
            or admin_token.get("value_captured") is not False
            or admin_token.get("validated_offline") is not False):
        raise OfflineBlocked("ADMIN_TOKEN_EVIDENCE_INVALID")

    events = events_value.get("events")
    if type(events) is not list or not events:
        raise OfflineBlocked("EVENTS_REQUIRED")
    previous = None
    for index, event in enumerate(events, 1):
        if (type(event) is not dict or event.get("schema") != EVENT_SCHEMA
                or event.get("run_id") != run_id
                or event.get("sequence") != index
                or event.get("previous_event_sha256") != previous
                or event.get("event_sha256") != _event_digest(event)
                or event.get("execution_started") is not False
                or event.get("process_control_performed") is not False):
            raise OfflineBlocked("EVENT_CHAIN_INVALID")
        previous = event["event_sha256"]
    last = events[-1]
    if state_value != _state_from_event(last, manifest_hash):
        raise OfflineBlocked("STATE_PROJECTION_INVALID")
    if last.get("state") not in (PREPARED, STOPPED):
        raise OfflineBlocked("STATE_INVALID")
    expected = ["OFFLINE_PLAN_PREPARED"]
    if last["state"] == STOPPED:
        expected.append("OFFLINE_PLAN_STOPPED")
    if [event.get("transition") for event in events] != expected:
        raise OfflineBlocked("STATE_TRANSITIONS_INVALID")

    targets = manifest.get("targets")
    if (type(targets) is not dict
            or targets.get("plan_directory") != str(run_directory)):
        raise OfflineBlocked("PLAN_PATH_IDENTITY_MISMATCH")
    runtime_targets = (
        "supervisor_report_directory", "paper_run_namespace",
        "current_paper_news_root", "current_paper_l1_directory",
        "supervisor_stop_request",
    )
    for key in runtime_targets:
        value = targets.get(key)
        if type(value) is not str:
            raise OfflineBlocked("TARGET_INVALID:" + key)
        target = Path(value).resolve(strict=False)
        if (key not in {"supervisor_report_directory", "supervisor_stop_request"}
                and target.name != run_id):
            raise OfflineBlocked("TARGET_RUN_ID_MISMATCH:" + key)
        if target.exists() and not allow_runtime_targets:
            raise OfflineBlocked("RUNTIME_SIDE_EFFECT_DETECTED:" + key)
    target_fields = {
        "plan_directory", "supervisor_report_directory", "runtime_parent",
        "paper_run_namespace", "current_paper_news_root",
        "current_paper_l1_directory", "supervisor_stop_request",
    }
    if set(targets) != target_fields:
        raise OfflineBlocked("TARGET_INVENTORY_INVALID")
    if validated_profile["reviewed"]:
        reviewed_targets = _resolve_path_templates(validated_profile, run_id)
        expected_reviewed_targets = {
            "supervisor_report_directory": str(
                reviewed_targets["runtime_evidence_directory"] / "supervisor"),
            "paper_run_namespace": str(
                reviewed_targets["paper_run_namespace"]),
            "current_paper_news_root": str(
                reviewed_targets["current_paper_news_root"]),
            "current_paper_l1_directory": str(
                reviewed_targets["external_private_l1_root"]),
        }
        if any(targets[key] != value
               for key, value in expected_reviewed_targets.items()):
            raise OfflineBlocked("REVIEWED_TARGET_IDENTITY_MISMATCH")
        for key in ("analysis_namespace", "runtime_evidence_directory"):
            if reviewed_targets[key].exists() and not allow_runtime_targets:
                raise OfflineBlocked("RUNTIME_SIDE_EFFECT_DETECTED:" + key)
        if any(excluded.casefold() in str(path).casefold()
               for excluded in validated_profile["excluded_active_run_ids"]
               for path in reviewed_targets.values()):
            raise OfflineBlocked("ACTIVE_RUN_COLLISION")
    if manifest.get("disabled_future_start_command") != _expected_future_command(
            manifest):
        raise OfflineBlocked("DISABLED_COMMAND_CONTRACT_INVALID")

    if rehash_inputs:
        inputs = manifest.get("inputs")
        if type(inputs) is not dict or set(inputs) != {"python", *ARTIFACT_FIELDS}:
            raise OfflineBlocked("INPUT_INVENTORY_INVALID")
        for name, descriptor in inputs.items():
            if (type(descriptor) is not dict
                    or set(descriptor) != {"path", "sha256", "bytes"}):
                raise OfflineBlocked("INPUT_DESCRIPTOR_INVALID:" + name)
            _, digest, size = _hash_stable_file(
                descriptor["path"], descriptor["sha256"])
            if digest != descriptor["sha256"] or size != descriptor["bytes"]:
                raise OfflineBlocked("INPUT_IDENTITY_MISMATCH:" + name)
        allowed_sources = (REVIEWED_SOURCE_NAMES
                           if validated_profile["reviewed"] else {
                               "tools/start_native_current_paper_v1.py",
                               "tools/windows_runtime_supervisor_v1.py",
                           })
        source_pins = manifest.get("source_pins")
        if type(source_pins) is not dict or set(source_pins) != allowed_sources:
            raise OfflineBlocked("SOURCE_PIN_INVENTORY_INVALID")
        for name, descriptor in source_pins.items():
            expected_fields = ({"path", "sha256", "bytes"}
                               if validated_profile["reviewed"]
                               else {"sha256", "bytes"})
            if (type(descriptor) is not dict
                    or set(descriptor) != expected_fields
                    or not _validate_hash(descriptor.get("sha256"))
                    or type(descriptor.get("bytes")) is not int
                    or descriptor["bytes"] <= 0):
                raise OfflineBlocked("SOURCE_PIN_DESCRIPTOR_INVALID:" + name)
            source_path = (descriptor["path"]
                           if validated_profile["reviewed"]
                           else REPO_ROOT / name)
            _, digest, size = _hash_stable_file(
                source_path, descriptor.get("sha256"))
            if size != descriptor.get("bytes") or digest != descriptor.get("sha256"):
                raise OfflineBlocked("SOURCE_PIN_MISMATCH:" + name)
    return run_directory, manifest, state_value, events, validated_profile


def audit(run_directory):
    """Read-only integrity and zero-authority audit."""
    try:
        directory, manifest, state_value, events, validated = _load_and_verify(
            run_directory)
        return {
            "schema": AUDIT_SCHEMA, "run_id": manifest["run_id"],
            "status": "PASS", "state": state_value["state"],
            "event_count": len(events), "execution_started": False,
            "process_control_performed": False, "live_authority": False,
            "external_order_authority": False,
            "run_directory": str(directory), "blocking_reasons": [],
            "profile_valid": True, "profile_status": "VALID",
            "profile_path": str(validated["profile_path"]),
            "profile_sha256": validated["profile_sha256"],
            "plan_sealed": True, "source_binding": SOURCE_BINDING_PASS,
            "path_policy": PATH_POLICY_PASS, "active_run_collision": False,
            "ARMS_MAXIMUM_QUOTE_AGE_SECONDS": manifest[
                "runtime_environment"].get(
                    "ARMS_MAXIMUM_QUOTE_AGE_SECONDS"),
            "ARMS_MINIMUM_REWARD_RISK_RATIO": manifest[
                "runtime_environment"].get(
                    "ARMS_MINIMUM_REWARD_RISK_RATIO"),
            "api_settings_binding": "PASS",
            "required_api_settings": dict(manifest["runtime_environment"]),
            "frozen_policy_drift": "NONE",
            "current_paper_run_touched": False, "ninjatrader_touched": False,
            "paper_enabled_by_this_task": False,
        }
    except (OfflineBlocked, OSError, ValueError, TypeError, KeyError,
            AttributeError) as error:
        reason = str(error)
        source_drift = "PROFILE_STATUS=" + BLOCKED_SOURCE_DRIFT in reason
        return {
            "schema": AUDIT_SCHEMA, "run_id": None, "status": BLOCKED,
            "state": BLOCKED, "execution_started": False,
            "process_control_performed": False, "live_authority": False,
            "external_order_authority": False,
            "run_directory": str(Path(run_directory).resolve(strict=False)),
            "blocking_reasons": [reason], "profile_valid": False,
            "profile_status": (BLOCKED_SOURCE_DRIFT if source_drift else BLOCKED),
            "plan_sealed": False,
            "source_binding": (BLOCKED_SOURCE_DRIFT if source_drift else BLOCKED),
            "path_policy": BLOCKED, "active_run_collision": None,
            "ARMS_MAXIMUM_QUOTE_AGE_SECONDS": None,
            "ARMS_MINIMUM_REWARD_RISK_RATIO": None,
            "api_settings_binding": BLOCKED,
            "required_api_settings": None,
            "frozen_policy_drift": BLOCKED,
            "current_paper_run_touched": False, "ninjatrader_touched": False,
            "paper_enabled_by_this_task": False,
        }


def status(run_directory):
    """Read-only status. Invalid or incomplete evidence is always BLOCKED."""
    result = audit(run_directory)
    return {
        "schema": STATE_SCHEMA, "run_id": result["run_id"],
        "state": result["state"], "audit_status": result["status"],
        "execution_started": False, "process_control_performed": False,
        "run_directory": result["run_directory"],
        "blocking_reasons": result["blocking_reasons"],
        "profile_valid": result["profile_valid"],
        "profile_status": result["profile_status"],
        "profile_path": result.get("profile_path"),
        "profile_sha256": result.get("profile_sha256"),
        "plan_sealed": result["plan_sealed"],
        "source_binding": result["source_binding"],
        "path_policy": result["path_policy"],
        "ARMS_MAXIMUM_QUOTE_AGE_SECONDS": result.get(
            "ARMS_MAXIMUM_QUOTE_AGE_SECONDS"),
        "ARMS_MINIMUM_REWARD_RISK_RATIO": result.get(
            "ARMS_MINIMUM_REWARD_RISK_RATIO"),
        "api_settings_binding": result.get("api_settings_binding"),
        "required_api_settings": result.get("required_api_settings"),
        "frozen_policy_drift": result.get("frozen_policy_drift"),
        "active_run_collision": result["active_run_collision"],
        "live_execution_allowed": result["live_authority"],
        "external_order_authority": result["external_order_authority"],
        "current_paper_run_touched": result["current_paper_run_touched"],
        "ninjatrader_touched": result["ninjatrader_touched"],
        "paper_enabled_by_this_task": result["paper_enabled_by_this_task"],
    }


def stop(run_directory, *, clock=None):
    """Close an offline plan only. This has no process-control path."""
    directory = Path(run_directory).resolve(strict=True)
    lock = directory / ".offline-stop.lock"
    lock_acquired = False
    try:
        with lock.open("xb") as stream:
            lock_acquired = True
            stream.write(b"offline-plan-transition-only\n")
            stream.flush()
            os.fsync(stream.fileno())
        directory, manifest, state_value, events, _ = _load_and_verify(directory)
        if state_value["state"] == STOPPED:
            return status(directory)
        if state_value["state"] != PREPARED:
            raise OfflineBlocked("ONLY_PREPARED_OFFLINE_CAN_STOP")
        event = _make_event(
            run_id=manifest["run_id"], sequence=2, timestamp=_utc_now(clock),
            previous=events[-1]["event_sha256"],
            transition="OFFLINE_PLAN_STOPPED", state=STOPPED)
        _atomic_json(directory / "events.json",
                     {"schema": EVENT_SCHEMA, "events": [*events, event]})
        _atomic_json(
            directory / "state.json",
            _state_from_event(event, state_value["manifest_sha256"]))
    finally:
        if lock_acquired:
            lock.unlink(missing_ok=True)
    return status(directory)


def _print(value):
    print(json.dumps(value, sort_keys=True, indent=2, allow_nan=False))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    start_parser = commands.add_parser(
        "start", help="prepare a sealed offline plan")
    start_parser.add_argument("--profile", type=Path, required=True)
    start_parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    for name in ("status", "audit", "stop"):
        child = commands.add_parser(name)
        child.add_argument("--run", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "start":
            result = prepare(args.profile, workspace=args.workspace)
        elif args.command == "status":
            result = status(args.run)
        elif args.command == "audit":
            result = audit(args.run)
        else:
            result = stop(args.run)
    except (OfflineBlocked, OSError, ValueError, TypeError, KeyError,
            AttributeError) as error:
        reason = str(error)
        source_drift = "PROFILE_STATUS=" + BLOCKED_SOURCE_DRIFT in reason
        result = {
            "schema": STATE_SCHEMA, "run_id": None, "state": BLOCKED,
            "audit_status": BLOCKED, "execution_started": False,
            "process_control_performed": False,
            "blocking_reasons": [reason], "profile_valid": False,
            "profile_status": (BLOCKED_SOURCE_DRIFT if source_drift else BLOCKED),
            "plan_sealed": False,
            "source_binding": (BLOCKED_SOURCE_DRIFT if source_drift else BLOCKED),
            "path_policy": BLOCKED, "active_run_collision": None,
            "live_execution_allowed": False,
            "external_order_authority": False,
            "current_paper_run_touched": False, "ninjatrader_touched": False,
            "paper_enabled_by_this_task": False,
        }
    _print(result)
    healthy = (result.get("state") in (PREPARED, STOPPED)
               or result.get("status") == "PASS")
    return 0 if healthy else 2


if __name__ == "__main__":
    sys.exit(main())
