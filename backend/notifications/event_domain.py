"""Immutable notification event domain with deterministic redaction and dedupe."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
import hashlib
import json
import re
from types import MappingProxyType
from typing import Mapping


class NotificationEventType(str, Enum):
    SIGNAL_CANDIDATE = "SIGNAL_CANDIDATE"
    SIGNAL_REJECTED = "SIGNAL_REJECTED"
    PAPER_TRADE_OPENED = "PAPER_TRADE_OPENED"
    PAPER_TRADE_CLOSED = "PAPER_TRADE_CLOSED"
    RISK_BLOCK = "RISK_BLOCK"
    DRAWDOWN_WARNING = "DRAWDOWN_WARNING"
    DAILY_LIMIT_BLOCK = "DAILY_LIMIT_BLOCK"
    ACCOUNT_FAILED = "ACCOUNT_FAILED"
    PAYOUT_ELIGIBLE = "PAYOUT_ELIGIBLE"
    SYSTEM_FAULT = "SYSTEM_FAULT"
    DATA_FAULT = "DATA_FAULT"


class NotificationSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class RedactionPolicy(str, Enum):
    REDACT_SENSITIVE = "REDACT_SENSITIVE"
    REJECT_SENSITIVE = "REJECT_SENSITIVE"


DEFAULT_SEVERITY: Mapping[NotificationEventType, NotificationSeverity] = MappingProxyType({
    NotificationEventType.SIGNAL_CANDIDATE: NotificationSeverity.INFO,
    NotificationEventType.SIGNAL_REJECTED: NotificationSeverity.INFO,
    NotificationEventType.PAPER_TRADE_OPENED: NotificationSeverity.INFO,
    NotificationEventType.PAPER_TRADE_CLOSED: NotificationSeverity.INFO,
    NotificationEventType.RISK_BLOCK: NotificationSeverity.WARNING,
    NotificationEventType.DRAWDOWN_WARNING: NotificationSeverity.WARNING,
    NotificationEventType.DAILY_LIMIT_BLOCK: NotificationSeverity.WARNING,
    NotificationEventType.ACCOUNT_FAILED: NotificationSeverity.CRITICAL,
    NotificationEventType.PAYOUT_ELIGIBLE: NotificationSeverity.INFO,
    NotificationEventType.SYSTEM_FAULT: NotificationSeverity.CRITICAL,
    NotificationEventType.DATA_FAULT: NotificationSeverity.ERROR,
})

_SENSITIVE_KEY_PARTS = (
    "authorization", "credential", "password", "private_key", "secret", "token",
    "api_key", "apikey", "account_number", "email", "phone",
)
_SENSITIVE_TEXT = re.compile(
    r"(?i)(?:bearer\s+\S+|(?:token|password|secret|api[_-]?key|authorization|"
    r"credential)\s*[:=]\s*\S+)"
)
_REDACTED = "[REDACTED]"
PayloadValue = str | int | bool | Decimal | None


def _text(value: str | None, name: str, *, optional: bool = False) -> None:
    if optional and value is None:
        return
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a nonempty string")


def _key_is_sensitive(key: str) -> bool:
    normalized = key.strip().lower().replace("-", "_")
    return any(part in normalized for part in _SENSITIVE_KEY_PARTS)


def _safe_value(
    key: str,
    value: object,
    policy: RedactionPolicy,
) -> PayloadValue:
    sensitive_key = _key_is_sensitive(key)
    sensitive_text = isinstance(value, str) and _SENSITIVE_TEXT.search(value) is not None
    if sensitive_key or sensitive_text:
        if policy == RedactionPolicy.REJECT_SENSITIVE:
            raise ValueError(f"sensitive notification payload field rejected: {key}")
        return _REDACTED if sensitive_key else _SENSITIVE_TEXT.sub(_REDACTED, value)
    if value is None or type(value) in (str, int, bool):
        return value
    if isinstance(value, Decimal) and value.is_finite():
        return value
    raise ValueError(
        "notification payload values must be scalar strings, integers, booleans, "
        "finite Decimals, or None"
    )


def safe_payload(
    payload: Mapping[str, object] | None,
    policy: RedactionPolicy,
) -> tuple[tuple[str, PayloadValue], ...]:
    if not isinstance(policy, RedactionPolicy):
        raise ValueError("redaction policy is required")
    if payload is None:
        return ()
    if not isinstance(payload, Mapping):
        raise ValueError("notification payload must be a mapping")
    safe = []
    for key, value in payload.items():
        _text(key, "payload key")
        safe.append((key, _safe_value(key, value, policy)))
    return tuple(sorted(safe, key=lambda item: item[0]))


@dataclass(frozen=True)
class NotificationIdentity:
    account_id: str | None = None
    firm_id: str | None = None
    program_id: str | None = None
    profile_version: str | None = None

    def __post_init__(self) -> None:
        for name in ("account_id", "firm_id", "program_id", "profile_version"):
            _text(getattr(self, name), name, optional=True)
        profile_values = (self.firm_id, self.program_id, self.profile_version)
        if any(value is not None for value in profile_values) and not all(
            value is not None for value in profile_values
        ):
            raise ValueError("profile identity must include firm, program, and version")


def _canonical(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return str(value.normalize())
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "__dataclass_fields__"):
        return {
            name: _canonical(getattr(value, name))
            for name in value.__dataclass_fields__
            if name not in ("dedupe_identity", "event_id")
        }
    if isinstance(value, tuple):
        return [_canonical(item) for item in value]
    return value


def _digest(value: object) -> str:
    raw = json.dumps(_canonical(value), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class NotificationEvent:
    event_type: NotificationEventType
    severity: NotificationSeverity
    dedupe_key: str
    occurred_at: datetime
    identity: NotificationIdentity
    payload: tuple[tuple[str, PayloadValue], ...]
    redaction_policy: RedactionPolicy
    schema_version: str = "1"
    dedupe_identity: str = field(init=False)
    event_id: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.event_type, NotificationEventType):
            raise ValueError("invalid notification event type")
        if not isinstance(self.severity, NotificationSeverity):
            raise ValueError("invalid notification severity")
        if not isinstance(self.redaction_policy, RedactionPolicy):
            raise ValueError("invalid redaction policy")
        _text(self.dedupe_key, "dedupe_key")
        _text(self.schema_version, "schema_version")
        if (
            not isinstance(self.occurred_at, datetime)
            or self.occurred_at.tzinfo is None
            or self.occurred_at.utcoffset() is None
        ):
            raise ValueError("occurred_at must be timezone-aware")
        if not isinstance(self.identity, NotificationIdentity):
            raise ValueError("identity must be a NotificationIdentity")
        if not isinstance(self.payload, tuple) or any(
            not isinstance(item, tuple) or len(item) != 2 for item in self.payload
        ):
            raise ValueError("payload must be an immutable safe payload")
        keys = tuple(item[0] for item in self.payload)
        if len(keys) != len(set(keys)):
            raise ValueError("payload keys must be unique")
        normalized_payload = safe_payload(dict(self.payload), self.redaction_policy)
        if normalized_payload != self.payload:
            raise ValueError("payload must already be sorted and safely redacted")
        dedupe_material = (
            self.event_type.value,
            self.dedupe_key,
            self.identity.account_id,
            self.identity.firm_id,
            self.identity.program_id,
            self.identity.profile_version,
        )
        object.__setattr__(self, "dedupe_identity", _digest(dedupe_material))
        object.__setattr__(self, "event_id", _digest(self))


def create_notification_event(
    event_type: NotificationEventType,
    dedupe_key: str,
    occurred_at: datetime,
    *,
    identity: NotificationIdentity | None = None,
    payload: Mapping[str, object] | None = None,
    severity: NotificationSeverity | None = None,
    redaction_policy: RedactionPolicy = RedactionPolicy.REDACT_SENSITIVE,
) -> NotificationEvent:
    if not isinstance(event_type, NotificationEventType):
        raise ValueError("invalid notification event type")
    selected_severity = severity or DEFAULT_SEVERITY[event_type]
    return NotificationEvent(
        event_type=event_type,
        severity=selected_severity,
        dedupe_key=dedupe_key,
        occurred_at=occurred_at,
        identity=identity or NotificationIdentity(),
        payload=safe_payload(payload, redaction_policy),
        redaction_policy=redaction_policy,
    )
