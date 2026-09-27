"""Explicit SIM_NATIVE commissioning inputs; never changes global API policy."""
from dataclasses import dataclass
import json
import math
from pathlib import Path

from backend.accounts.sim_native_account_v3 import digest
from backend.config.api_settings import APISettings

POLICY_PATH = Path(__file__).resolve().parents[1] / "config/sim_native_commissioning_policy_v1.json"
SCHEMA = "ARMS_SIM_NATIVE_COMMISSIONING_POLICY_V1"
FLOAT_FIELDS = (
    "maximum_quote_age_seconds", "minimum_reward_risk_ratio", "minimum_stop_points",
    "maximum_stop_points", "maximum_spread_points", "minimum_atr_points",
    "minimum_a_plus_probability", "minimum_a_plus_confluence_score",
)
INT_FIELDS = ("maximum_signal_age_seconds", "maximum_open_positions")
TIMEOUT_FIELDS = ("protection_timeout_us", "recovery_timeout_us")


@dataclass(frozen=True)
class CommissioningPolicyV1:
    api_settings: APISettings
    protection_timeout_us: int
    recovery_timeout_us: int
    policy_id: str


def resolve(document):
    if (type(document) is not dict or set(document) != {"schema", "version", "api_settings", *TIMEOUT_FIELDS}
            or document["schema"] != SCHEMA or type(document["version"]) is not int or document["version"] != 1):
        raise ValueError("exact commissioning policy V1 schema and keys required")
    source = document["api_settings"]
    if type(source) is not dict or set(source) != set(FLOAT_FIELDS + INT_FIELDS):
        raise ValueError("exact commissioning API policy fields required")
    values = {}
    for name in FLOAT_FIELDS:
        value = source[name]
        probability = name in ("minimum_a_plus_probability", "minimum_a_plus_confluence_score")
        if type(value) not in (float, int):
            raise ValueError("invalid commissioning numeric field: " + name)
        try:
            numeric = float(value)
        except OverflowError as error:
            raise ValueError("commissioning numeric field overflow: " + name) from error
        if not math.isfinite(numeric) or (not 0 <= numeric <= 1 if probability else numeric <= 0):
            raise ValueError("invalid commissioning numeric field: " + name)
        values[name] = numeric
    for name in INT_FIELDS:
        if type(source[name]) is not int or source[name] <= 0:
            raise ValueError("positive commissioning integer required: " + name)
        values[name] = source[name]
    if values["maximum_open_positions"] != 1 or values["minimum_stop_points"] > values["maximum_stop_points"]:
        raise ValueError("invalid V1 position/stop bounds")
    for name in TIMEOUT_FIELDS:
        if type(document[name]) is not int or document[name] <= 0:
            raise ValueError("positive commissioning timeout required")
    if document["recovery_timeout_us"] <= document["protection_timeout_us"]:
        raise ValueError("recovery timeout must exceed protection timeout")
    normalized = {"schema": SCHEMA, "version": 1, "api_settings": values,
                  **{name: document[name] for name in TIMEOUT_FIELDS}}
    # All ten required fields are explicit; unrelated APISettings semantics stay intact.
    return CommissioningPolicyV1(APISettings(**values), document["protection_timeout_us"],
                                document["recovery_timeout_us"], digest(normalized))


def _unique_fields(pairs):
    values = {}
    for name, value in pairs:
        if name in values:
            raise ValueError("duplicate commissioning policy field")
        values[name] = value
    return values


def load(path=POLICY_PATH):
    return resolve(json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=_unique_fields))
