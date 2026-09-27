"""Public heartbeat observations only: no authority key or execution dependencies."""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import stat

from backend.accounts.sim_native_account_v3 import SimNativeAccountV3
from backend.market_data.sim_operator_binding_v2 import _MAX_EVIDENCE_AGE
from backend.services.sim_native_runtime_snapshot_reader_v2 import SimNativeRuntimeSnapshotReaderV2 as RuntimeSchema

COMMISSIONING_FILE = "controlled-v3-commissioning-status.json"
BOOLEAN_FIELDS = ("controlled_v3_configured", "authority_loaded", "config_signature_valid",
    "command_path_ready", "activation_path_ready", "state_path_ready", "reconciliation_path_ready",
    "native_submit_enabled", "auto_retry_allowed")
IDENTITY_FIELDS = ("configuration_generation", "authority_id", "backend_account_id", "native_account",
                   "provider", "instrument", "runtime_generation")
COMMISSIONING_KEYS = {"schema", "observed_at", "restore_status", "last_configuration_error",
                      "reconciliation_fence", *BOOLEAN_FIELDS, *IDENTITY_FIELDS}


def _safe_path(path):
    repo = Path(__file__).resolve().parents[2]
    if (not path.is_absolute() or str(path).startswith(("\\\\", "//")) or ".." in path.parts
            or any("onedrive" in part.lower() or part.lower() == "custom" for part in path.parts)
            or path == repo or repo in path.parents):
        raise ValueError("UNSAFE_SNAPSHOT_PATH")
    for part in (path, *path.parents):
        if part.is_symlink() or (part.exists() and getattr(part.lstat(), "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT):
            raise ValueError("UNSAFE_SNAPSHOT_PATH")
    return path


def _read(path, keys):
    _safe_path(path)
    with path.open("rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError("INVALID_SNAPSHOT_FILE")
        raw = stream.read(RuntimeSchema.MAX_FILE_BYTES + 1)
    _safe_path(path)
    if not raw or len(raw) > RuntimeSchema.MAX_FILE_BYTES:
        raise ValueError("INVALID_SNAPSHOT_SIZE")
    value = json.loads(raw.decode("utf-8"), object_pairs_hook=RuntimeSchema._object_no_duplicates,
                       parse_constant=RuntimeSchema._reject_constant)
    if type(value) is not dict or set(value) != keys:
        raise ValueError("INVALID_SNAPSHOT_SCHEMA")
    return value


def _age(value, now):
    if type(value) is not str:
        raise ValueError("INVALID_HEARTBEAT_TIME")
    observed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if observed.tzinfo is None or observed.utcoffset() != timedelta(0):
        raise ValueError("INVALID_HEARTBEAT_TIME")
    age = (now - observed).total_seconds()
    if age < 0:
        raise ValueError("FUTURE_HEARTBEAT")
    return age


class SimNativeDashboardReaderV3:
    def __init__(self, *, clock=None):
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def get_snapshot(self):
        result = {"execution_domain": "SIM_NATIVE", "status": "UNAVAILABLE", "reason": "SNAPSHOTS_UNAVAILABLE",
            "heartbeat_fresh": False, "heartbeat_age_seconds": None,
            "heartbeat_maximum_age_seconds": _MAX_EVIDENCE_AGE.total_seconds(),
            "observed_at": None, "commissioning": None, "runtime": None}
        for name in (*BOOLEAN_FIELDS, "backend_account_id", "native_account", "provider", "instrument",
                     "restore_status", "reconciliation_fence", "connection_status", "physical_test_readiness",
                     "position_state", "active_order_count"):
            result[name] = None
        try:
            binding = SimNativeAccountV3.load(execution_domain="SIM_NATIVE", provider="Simulator", native_account_name="Sim101")
            result.update(backend_account_id=binding.backend_account_id, native_account=binding.native_account_name,
                          provider=binding.provider, instrument=binding.instrument)
            local = os.environ.get("LOCALAPPDATA")
            if not local:
                return result
            root = _safe_path(Path(local) / "ARMS-AI/sim-native-v3/runtime/snapshots")
            commissioning = _read(root / COMMISSIONING_FILE, COMMISSIONING_KEYS)
            runtime = _read(root / RuntimeSchema.FILE_NAME, RuntimeSchema.REQUIRED_KEYS)
            if commissioning["schema"] != "ARMS_CONTROLLED_COMMISSIONING_V3" or runtime["schema"] != RuntimeSchema.SCHEMA:
                raise ValueError("INVALID_SNAPSHOT_SCHEMA")
            expected = {"backend_account_id": binding.backend_account_id, "native_account": binding.native_account_name,
                        "provider": binding.provider, "instrument": binding.instrument, "runtime_generation": str(binding.runtime_generation)}
            if any(type(commissioning[k]) is not str or commissioning[k] != v for k,v in expected.items()):
                raise ValueError("COMMISSIONING_IDENTITY_MISMATCH")
            if any(type(runtime[k]) is not str or runtime[k] != v for k,v in
                   {"account_name": binding.native_account_name, "provider": binding.provider, "instrument": binding.instrument}.items()):
                raise ValueError("RUNTIME_IDENTITY_MISMATCH")
            if (type(commissioning["authority_id"]) is not str or not re.fullmatch(r"[0-9a-f]{64}", commissioning["authority_id"])
                    or type(commissioning["configuration_generation"]) is not str
                    or not re.fullmatch(r"[1-9][0-9]*", commissioning["configuration_generation"])):
                raise ValueError("INVALID_COMMISSIONING_IDENTITY")
            if any(type(commissioning[k]) is not bool for k in BOOLEAN_FIELDS):
                raise ValueError("INVALID_COMMISSIONING_FLAGS")
            if type(commissioning["reconciliation_fence"]) is not bool and commissioning["reconciliation_fence"] != "UNKNOWN":
                raise ValueError("INVALID_RECONCILIATION_FENCE")
            if (type(commissioning["restore_status"]) is not str or not re.fullmatch(r"[A-Z_]{1,80}", commissioning["restore_status"])
                    or type(commissioning["last_configuration_error"]) is not str or len(commissioning["last_configuration_error"]) > 256):
                raise ValueError("INVALID_COMMISSIONING_STATUS")
            if (type(runtime["active_order_count"]) is not int or runtime["active_order_count"] < 0
                    or type(runtime["position_state"]) is not str or runtime["position_state"] not in RuntimeSchema.VALID_POSITION_STATES
                    or type(runtime["physical_test_readiness"]) is not str or runtime["physical_test_readiness"] not in RuntimeSchema.VALID_READINESS_STATES
                    or type(runtime["connection_status"]) is not str or not re.fullmatch(r"[A-Za-z]{1,40}", runtime["connection_status"])
                    or type(runtime["native_submit_enabled"]) is not bool or type(runtime["auto_retry_allowed"]) is not bool):
                raise ValueError("INVALID_RUNTIME_STATUS")
            now = self.clock()
            if type(now) is not datetime or now.tzinfo is None or now.utcoffset() != timedelta(0):
                raise ValueError("INVALID_OBSERVATION_CLOCK")
            age = max(_age(commissioning["observed_at"], now), _age(runtime["observed_at"], now))
            fresh = age <= _MAX_EVIDENCE_AGE.total_seconds()
            result.update({k: commissioning[k] for k in (*BOOLEAN_FIELDS, "restore_status", "reconciliation_fence")})
            result.update({k: runtime[k] for k in ("connection_status", "physical_test_readiness", "position_state", "active_order_count")})
            # Never report disabled if either observation says enabled.
            for flag in ("native_submit_enabled", "auto_retry_allowed"):
                result[flag] = commissioning[flag] or runtime[flag]
            result.update(commissioning={k:v for k,v in commissioning.items() if k != "last_configuration_error"},
                runtime=runtime, observed_at=runtime["observed_at"], heartbeat_age_seconds=age, heartbeat_fresh=fresh)
            if (any(not commissioning[k] for k in ("controlled_v3_configured", "authority_loaded", "config_signature_valid"))
                    or result["native_submit_enabled"] or result["auto_retry_allowed"]):
                result.update(status="INVALID", reason="COMMISSIONING_SAFETY_INVALID")
            elif not fresh:
                result.update(status="STALE", reason="HEARTBEAT_STALE")
            elif result["reconciliation_fence"] is not False:
                result.update(status="DEGRADED", reason="RECONCILIATION_REQUIRED")
            elif runtime["connection_status"] != "Connected":
                result.update(status="DISCONNECTED", reason="CONNECTION_NOT_READY")
            elif (not all(commissioning[k] for k in ("command_path_ready", "activation_path_ready", "state_path_ready", "reconciliation_path_ready"))
                    or runtime["position_state"] != "FLAT" or runtime["active_order_count"] != 0
                    or commissioning["last_configuration_error"] or commissioning["restore_status"] != "NO_PERSISTED_OPERATION"):
                result.update(status="DEGRADED", reason="RUNTIME_REVIEW_REQUIRED")
            elif runtime["physical_test_readiness"] == "MARKET_SESSION_CLOSED":
                result.update(status="SESSION_CLOSED", reason="MARKET_SESSION_CLOSED")
            elif runtime["physical_test_readiness"] != "PHYSICAL_TEST_READY":
                result.update(status="NOT_READY", reason=runtime["physical_test_readiness"])
            else:
                result.update(status="HEALTHY", reason=None)
        except OSError:
            result.update(status="UNAVAILABLE", reason="SNAPSHOTS_UNAVAILABLE")
        except (ValueError, TypeError, OverflowError):
            # Do not echo raw file content, arbitrary exception text, or local paths.
            result.update(status="INVALID", reason="SNAPSHOT_VALIDATION_FAILED")
        return result
