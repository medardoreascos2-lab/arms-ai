"""Central fail-closed redaction for Phase 4 operational output channels."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
import re
from typing import TypeAlias


REDACTED = "[REDACTED]"
REDACTED_BINARY = "[REDACTED_BINARY]"
REDACTED_CYCLE = "[REDACTED_CYCLE]"
REDACTED_UNSUPPORTED = "[REDACTED_UNSUPPORTED]"
_MAX_DEPTH = 6
_MAX_FIELDS = 64
_MAX_ITEMS = 64
_MAX_TEXT = 2048
_SAFE_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/ -]{0,127}$")
_SAFE_TYPE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]{0,127}$")
_SENSITIVE_KEY_PARTS = (
    "api_key",
    "apikey",
    "authorization",
    "client_secret",
    "cookie",
    "credential",
    "password",
    "private_key",
    "secret",
    "token",
    "webhook",
)
_ASSIGNMENT = re.compile(
    r"(?i)\b(token|password|secret|api[_-]?key|authorization|cookie|webhook|"
    r"credential|private[_-]?key|client[_-]?secret)\b\s*[:=]\s*"
    r"(?:\"[^\"]*\"|'[^']*'|[^\s,]+)"
)
_AUTH_SCHEME = re.compile(r"(?i)\b(?:Bearer|Basic)\s+[A-Za-z0-9._~+/=-]+")
_URI_CREDENTIAL = re.compile(r"://[^/\s:@]+:[^/\s@]+@")
_JWT = re.compile(r"\beyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\b")


class RedactionChannel(str, Enum):
    LOG = "LOG"
    AUDIT = "AUDIT"
    EXCEPTION = "EXCEPTION"
    NOTIFICATION = "NOTIFICATION"
    API_ERROR = "API_ERROR"
    WORKER_FAILURE = "WORKER_FAILURE"


RedactedScalar: TypeAlias = str | int | bool | Decimal | None
RedactedValue: TypeAlias = RedactedScalar | tuple[object, ...]


def _normalize_key(key: str) -> str:
    separated = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", key.strip())
    return re.sub(r"[^a-z0-9]+", "_", separated.lower()).strip("_")


def sensitive_key(key: str) -> bool:
    if not isinstance(key, str):
        raise ValueError("redaction key must be text")
    normalized = _normalize_key(key)
    return any(part in normalized for part in _SENSITIVE_KEY_PARTS)


def redact_text(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("redaction text must be a string")
    clean = " ".join(value.split())
    clean = _URI_CREDENTIAL.sub("://[REDACTED]@", clean)
    clean = _AUTH_SCHEME.sub(REDACTED, clean)
    clean = _JWT.sub(REDACTED, clean)
    clean = _ASSIGNMENT.sub(
        lambda match: f"{match.group(1)}={REDACTED}", clean
    )
    return clean[:_MAX_TEXT]


def _redact_value(value: object, *, depth: int, seen: set[int]) -> RedactedValue:
    if depth > _MAX_DEPTH:
        return REDACTED_UNSUPPORTED
    if value is None or type(value) in (int, bool):
        return value
    if isinstance(value, Decimal):
        return value if value.is_finite() else REDACTED_UNSUPPORTED
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return REDACTED_BINARY
    if isinstance(value, Mapping):
        identity = id(value)
        if identity in seen:
            return REDACTED_CYCLE
        seen.add(identity)
        try:
            return _redact_mapping(value, depth=depth + 1, seen=seen)
        finally:
            seen.remove(identity)
    if isinstance(value, (list, tuple)):
        identity = id(value)
        if identity in seen:
            return REDACTED_CYCLE
        seen.add(identity)
        try:
            items = tuple(
                _redact_value(item, depth=depth + 1, seen=seen)
                for item in value[:_MAX_ITEMS]
            )
            if len(value) > _MAX_ITEMS:
                items += (REDACTED_UNSUPPORTED,)
            return items
        finally:
            seen.remove(identity)
    return REDACTED_UNSUPPORTED


def _redact_mapping(
    values: Mapping[object, object],
    *,
    depth: int,
    seen: set[int],
) -> tuple[tuple[str, RedactedValue], ...]:
    safe: list[tuple[str, RedactedValue]] = []
    for index, (key, value) in enumerate(values.items()):
        if index >= _MAX_FIELDS:
            safe.append(("truncated", REDACTED_UNSUPPORTED))
            break
        if not isinstance(key, str) or _SAFE_KEY.fullmatch(key) is None:
            safe.append((f"invalid_key_{index}", REDACTED_UNSUPPORTED))
            continue
        safe.append(
            (
                key,
                REDACTED
                if sensitive_key(key)
                else _redact_value(value, depth=depth, seen=seen),
            )
        )
    return tuple(sorted(safe, key=lambda item: item[0]))


def redact_mapping(
    values: Mapping[object, object] | None,
) -> tuple[tuple[str, RedactedValue], ...]:
    if values is None:
        return ()
    if not isinstance(values, Mapping):
        raise ValueError("redaction fields must be a mapping")
    return _redact_mapping(values, depth=1, seen={id(values)})


def _redacted_value_is_safe(value: object) -> bool:
    if value is None or type(value) in (int, bool):
        return True
    if isinstance(value, Decimal):
        return value.is_finite()
    if isinstance(value, str):
        return redact_text(value) == value
    if not isinstance(value, tuple):
        return False
    mapping_like = all(
        isinstance(item, tuple)
        and len(item) == 2
        and isinstance(item[0], str)
        for item in value
    )
    if mapping_like:
        keys = tuple(item[0] for item in value)
        if len(keys) != len(set(keys)):
            return False
        return all(
            _SAFE_KEY.fullmatch(key) is not None
            and (
                field_value == REDACTED
                if sensitive_key(key)
                else _redacted_value_is_safe(field_value)
            )
            for key, field_value in value
        )
    return all(_redacted_value_is_safe(item) for item in value)


@dataclass(frozen=True)
class RedactedRecord:
    channel: RedactionChannel
    message: str
    fields: tuple[tuple[str, RedactedValue], ...] = ()
    error_type: str | None = None
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.channel, RedactionChannel):
            raise ValueError("channel must be a RedactionChannel")
        if not isinstance(self.message, str) or redact_text(self.message) != self.message:
            raise ValueError("message must already be safely redacted")
        if not isinstance(self.fields, tuple) or any(
            not isinstance(item, tuple) or len(item) != 2 for item in self.fields
        ):
            raise ValueError("fields must be immutable key/value pairs")
        keys = tuple(item[0] for item in self.fields)
        if len(keys) != len(set(keys)):
            raise ValueError("redacted field keys must be unique")
        if (
            keys != tuple(sorted(keys))
            or any(
                _SAFE_KEY.fullmatch(key) is None
                or (
                    value != REDACTED
                    if sensitive_key(key)
                    else not _redacted_value_is_safe(value)
                )
                for key, value in self.fields
            )
        ):
            raise ValueError("fields must already be sorted and safely redacted")
        if self.error_type is not None and (
            not isinstance(self.error_type, str)
            or _SAFE_TYPE.fullmatch(self.error_type) is None
        ):
            raise ValueError("error_type must be a safe type name")


class SecretRedactor:
    execution_authorized = False
    production_mutation_authorized = False

    def _record(
        self,
        channel: RedactionChannel,
        message: str,
        fields: Mapping[object, object] | None = None,
        *,
        error_type: str | None = None,
    ) -> RedactedRecord:
        safe_type = error_type if error_type and _SAFE_TYPE.fullmatch(error_type) else None
        return RedactedRecord(
            channel=channel,
            message=redact_text(message),
            fields=redact_mapping(fields),
            error_type=safe_type,
        )

    def log(
        self, message: str, fields: Mapping[object, object] | None = None
    ) -> RedactedRecord:
        return self._record(RedactionChannel.LOG, message, fields)

    def audit(self, fields: Mapping[object, object]) -> RedactedRecord:
        return self._record(RedactionChannel.AUDIT, "audit_event", fields)

    def exception(self, error: BaseException) -> RedactedRecord:
        if not isinstance(error, BaseException):
            raise ValueError("error must be an exception")
        try:
            message = str(error)
        except Exception:
            message = "exception message unavailable"
        return self._record(
            RedactionChannel.EXCEPTION,
            message,
            error_type=type(error).__name__,
        )

    def notification(self, payload: Mapping[object, object]) -> RedactedRecord:
        return self._record(
            RedactionChannel.NOTIFICATION,
            "notification_payload",
            payload,
        )

    def api_error(
        self,
        status_code: int,
        detail: str,
        fields: Mapping[object, object] | None = None,
    ) -> RedactedRecord:
        if type(status_code) is not int or not 400 <= status_code <= 599:
            raise ValueError("API error status_code must be between 400 and 599")
        combined = dict(fields or {})
        combined["status_code"] = status_code
        return self._record(RedactionChannel.API_ERROR, detail, combined)

    def worker_failure(
        self,
        worker_id: str,
        error: BaseException,
        fields: Mapping[object, object] | None = None,
    ) -> RedactedRecord:
        if not isinstance(worker_id, str) or _SAFE_TYPE.fullmatch(worker_id) is None:
            raise ValueError("worker_id must be a safe identifier")
        if not isinstance(error, BaseException):
            raise ValueError("error must be an exception")
        combined = dict(fields or {})
        combined["worker_id"] = worker_id
        try:
            message = str(error)
        except Exception:
            message = "worker failure message unavailable"
        return self._record(
            RedactionChannel.WORKER_FAILURE,
            message,
            combined,
            error_type=type(error).__name__,
        )
