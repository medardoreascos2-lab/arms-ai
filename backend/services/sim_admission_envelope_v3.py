"""Authenticated, immutable admission for the controlled Sim101 profile.

This module has no native transport and grants no authority by itself. Signing
keys are injected by the trusted backend composition, never read from commands.
Deployment/key provisioning is deliberately outside this offline contract.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import hmac
import os
from pathlib import Path
import re
from backend.accounts.sim_native_account_v3 import CLAIM_NAMES, SimNativeAccountV3


DOMAIN = b"arms.native.admission.v3\0"
GATES = ("risk", "probability", "confluence", "news", "market", "rr", "stop")
IDENTITIES = (
    "admission_id", "signal_id", "plan_id", "operation_id", "command_id",
    "client_order_id", "approval_id", "activation_id", "risk_approval_id",
    "risk_version", "quote_id", "runtime_id", "policy_version",
)
FIELDS = frozenset(IDENTITIES + CLAIM_NAMES + (
    "account", "provider", "instrument", "runtime_generation", "side", "quantity",
    "stop_price", "target_price", "entry_price", "point_value", "risk_ceiling",
    "signal_us", "quote_us", "runtime_us", "issued_us", "expires_us",
    "risk_expires_us", "max_signal_age_us", "max_quote_age_us", "max_runtime_age_us",
    "protection_timeout_us", "recovery_timeout_us",
) + tuple(g + "_approval" for g in GATES))
_ID = re.compile(r"[A-Za-z0-9_.-]{1,100}\Z")


def utc_us(value: datetime) -> int:
    if type(value) is not datetime or value.tzinfo is not timezone.utc:
        raise ValueError("an explicit UTC clock is required")
    delta = value - datetime(1970, 1, 1, tzinfo=timezone.utc)
    return (delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds


def canonical(fields: dict[str, str]) -> bytes:
    if type(fields) is not dict or set(fields) != FIELDS:
        raise ValueError("exact admission schema required")
    if any(type(v) is not str or not v or any(ord(c) < 32 or ord(c) > 126 for c in v)
           for v in fields.values()):
        raise ValueError("admission values must be nonempty printable ASCII")
    return "".join(k + "\t" + fields[k] + "\n" for k in sorted(fields)).encode("ascii")


def positive_decimal(value: str) -> Decimal:
    try:
        result = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("invalid admission price or risk") from None
    if not result.is_finite() or result <= 0:
        raise ValueError("invalid admission price or risk")
    return result


def validate(fields: dict[str, str], *, now_us: int, instrument: str,
             runtime_generation: int, risk_version: str, account_binding: SimNativeAccountV3) -> None:
    canonical(fields)
    if type(account_binding) is not SimNativeAccountV3:
        raise ValueError("explicit native-simulation account authority required")
    account_binding.assert_claims(fields)
    account_binding.manager()  # Reject profile drift before producing authority.
    if any(not _ID.fullmatch(fields[k]) for k in IDENTITIES):
        raise ValueError("invalid admission identity")
    if (fields["account"] != "Sim101" or fields["provider"] != "Simulator"
            or fields["instrument"] != instrument or not instrument
            or fields["runtime_generation"] != str(runtime_generation)
            or type(runtime_generation) is not int or runtime_generation < 1
            or fields["risk_version"] != risk_version
            or fields["operation_id"] != fields["client_order_id"]
            or fields["quantity"] != "1" or fields["side"] not in {"BUY", "SELL"}):
        raise ValueError("admission binding mismatch")
    if any(fields[g + "_approval"] != "APPROVED" for g in GATES):
        raise ValueError("admission gate rejected")
    integer_fields = [k for k in fields if k.endswith("_us")]
    if any(not re.fullmatch(r"[1-9][0-9]{0,17}", fields[k]) for k in integer_fields):
        raise ValueError("invalid admission time")
    times = {k: int(fields[k]) for k in integer_fields}
    if (type(now_us) is not int or times["issued_us"] > now_us
            or now_us >= min(times["expires_us"], times["risk_expires_us"])
            or times["max_runtime_age_us"] > 15_000_000):
        raise ValueError("expired or future admission")
    for kind in ("signal", "quote", "runtime"):
        observed, maximum = times[kind + "_us"], times["max_" + kind + "_age_us"]
        if not 0 <= now_us - observed <= maximum:
            raise ValueError("stale or future " + kind)
        if times["expires_us"] > observed + maximum:
            raise ValueError("deadline exceeds evidence validity")
    entry, stop, target, point, ceiling = (
        positive_decimal(fields[k]) for k in
        ("entry_price", "stop_price", "target_price", "point_value", "risk_ceiling"))
    if not (stop < entry < target if fields["side"] == "BUY" else target < entry < stop):
        raise ValueError("invalid approved levels")
    if abs(entry - stop) * point > ceiling:
        raise ValueError("planned risk exceeds approved ceiling")


@dataclass(frozen=True)
class AuthenticatedAdmissionV3:
    payload: bytes
    digest: str
    authenticator: str

    @classmethod
    def read(cls, wire: bytes):
        marker, digest, authenticator, payload = wire.split(b"\n", 3)
        if marker != b"ARMS_SIM_ADMISSION_V3":
            raise ValueError("invalid admission wire schema")
        result = cls(payload, digest.decode("ascii"), authenticator.decode("ascii"))
        result.fields()
        return result

    def fields(self) -> dict[str, str]:
        try:
            pairs = [line.split("\t") for line in self.payload.decode("ascii").splitlines()]
            if any(len(pair) != 2 for pair in pairs):
                raise ValueError("invalid admission encoding")
            result = dict(pairs)
        except (UnicodeError, TypeError):
            raise ValueError("invalid admission encoding") from None
        if len(result) != len(pairs) or canonical(result) != self.payload:
            raise ValueError("noncanonical admission")
        return result

    def wire_bytes(self) -> bytes:
        return b"ARMS_SIM_ADMISSION_V3\n" + self.digest.encode("ascii") + b"\n" + \
            self.authenticator.encode("ascii") + b"\n" + self.payload


class NativeAdmissionAuthorityV3:
    """One configured key/issuer; a self-supplied key is never an admission field."""
    def __init__(self, *, key: bytes, execution_scope_guard, account_binding: SimNativeAccountV3):
        if type(key) is not bytes or len(key) < 32 or not callable(execution_scope_guard):
            raise ValueError("configured admission key and execution scope required")
        self.__key = key
        self.__guard = execution_scope_guard
        if type(account_binding) is not SimNativeAccountV3:
            raise ValueError("explicit native-simulation account authority required")
        self.__binding = account_binding

    def issue(self, fields: dict[str, str], *, now_us: int, instrument: str,
              runtime_generation: int, risk_version: str) -> AuthenticatedAdmissionV3:
        # The production composition must supply RuntimeAdmissionV2's guard.
        # Callers cannot substitute an 'approved' boolean for that capability.
        self.__guard()
        validate(fields, now_us=now_us, instrument=instrument,
                 runtime_generation=runtime_generation, risk_version=risk_version, account_binding=self.__binding)
        payload = canonical(fields)
        return AuthenticatedAdmissionV3(payload, hashlib.sha256(payload).hexdigest(),
            hmac.new(self.__key, DOMAIN + payload, hashlib.sha256).hexdigest())

    def verify(self, envelope: AuthenticatedAdmissionV3, **context) -> dict[str, str]:
        if (type(envelope) is not AuthenticatedAdmissionV3
                or not hmac.compare_digest(hashlib.sha256(envelope.payload).hexdigest(), envelope.digest)
                or not hmac.compare_digest(hmac.new(self.__key, DOMAIN + envelope.payload,
                    hashlib.sha256).hexdigest(), envelope.authenticator)):
            raise ValueError("unverifiable admission writer/content")
        fields = envelope.fields()
        validate(fields, account_binding=self.__binding, **context)
        return fields

    def persist(self, directory: Path, envelope: AuthenticatedAdmissionV3) -> Path:
        self.__guard()
        # Verify authenticity independently of admission freshness: persistence is
        # not an execution permission, and expired evidence must remain readable.
        if not hmac.compare_digest(hmac.new(self.__key, DOMAIN + envelope.payload,
                hashlib.sha256).hexdigest(), envelope.authenticator):
            raise ValueError("unverifiable admission writer")
        fields = envelope.fields()
        self.__binding.assert_claims(fields)
        if hashlib.sha256(envelope.payload).hexdigest() != envelope.digest:
            raise ValueError("admission digest mismatch")
        if not _ID.fullmatch(fields["admission_id"]):
            raise ValueError("invalid admission identity")
        destination = Path(directory) / (fields["admission_id"] + ".admission")
        data = envelope.wire_bytes()
        try:
            with destination.open("xb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
        except FileExistsError:
            if destination.read_bytes() != data:
                raise ValueError("immutable admission collision") from None
        return destination
