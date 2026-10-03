"""Durable Phase 3 outbox foundation with no external transport."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import hmac
import json
import re
import sqlite3

from .durable_store import (
    DurableStoreIntegrityError,
    DurableStoreReadOnlyError,
    Phase3DurableStateStore,
    _canonical_utc,
    _parse_canonical_utc,
)
from .financial_serialization import (
    _decode_value,
    _encode_value,
    _reject_constant,
    _reject_float,
    _unique_object,
)
from .state_contracts import DurableStatePayload, TenantIdentity


OUTBOX_SERIALIZATION_FORMAT = "arms.phase3.outbox-event-json.v1"
MAX_OUTBOX_EVENT_BYTES = 1_048_576
_HASH = re.compile(r"^[0-9a-f]{64}$")
_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$")
_KIND = re.compile(r"^[A-Z][A-Z0-9_]{0,127}$")
_SENSITIVE_ERROR = re.compile(
    r"(?i)\b(password|api[_-]?key|token|secret|authorization)\s*[:=]\s*\S+"
)


class OutboxStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    DELIVERED = "DELIVERED"
    DEAD_LETTER = "DEAD_LETTER"


class OutboxError(RuntimeError):
    """Base outbox failure."""


class OutboxConflictError(OutboxError):
    """A dedupe key already identifies different immutable content."""


class OutboxIntegrityError(OutboxError):
    """Stored outbox evidence failed validation."""


def sanitize_outbox_error(value: str) -> str:
    """Return bounded single-line diagnostic text with common secrets redacted."""
    if not isinstance(value, str):
        raise ValueError("outbox error must be text")
    clean = " ".join(value.split())
    clean = _SENSITIVE_ERROR.sub(lambda match: f"{match.group(1)}=[REDACTED]", clean)
    return clean[:512]


def _object(value: object, keys: frozenset[str], name: str) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError(f"{name} must contain exactly the required fields")
    return value


def _document(event: "OutboxEvent", *, include_event_id: bool) -> dict[str, object]:
    document = {
        "available_at": _canonical_utc(event.available_at, "available_at"),
        "created_at": _canonical_utc(event.created_at, "created_at"),
        "dedupe_key": event.dedupe_key,
        "event_kind": event.event_kind,
        "format": OUTBOX_SERIALIZATION_FORMAT,
        "payload": [
            {"name": name, "value": _encode_value(value)}
            for name, value in event.payload.entries
        ],
        "tenant_id": event.tenant.tenant_id,
    }
    if include_event_id:
        document["event_id"] = event.event_id
    return document


def _json_bytes(document: dict[str, object]) -> bytes:
    encoded = json.dumps(
        document, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    if len(encoded) > MAX_OUTBOX_EVENT_BYTES:
        raise ValueError("serialized outbox event exceeds size limit")
    return encoded


def outbox_event_hash(event: "OutboxEvent") -> str:
    return hashlib.sha256(_json_bytes(_document(event, include_event_id=False))).hexdigest()


@dataclass(frozen=True)
class OutboxEvent:
    tenant: TenantIdentity
    event_kind: str
    dedupe_key: str
    payload: DurableStatePayload
    created_at: datetime
    available_at: datetime
    event_id: str = field(init=False)
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.tenant, TenantIdentity):
            raise ValueError("tenant must be a TenantIdentity")
        if not isinstance(self.event_kind, str) or _KIND.fullmatch(self.event_kind) is None:
            raise ValueError("event_kind must be an uppercase identifier")
        if not isinstance(self.dedupe_key, str) or _KEY.fullmatch(self.dedupe_key) is None:
            raise ValueError("dedupe_key contains unsupported characters")
        if not isinstance(self.payload, DurableStatePayload):
            raise ValueError("payload must be a DurableStatePayload")
        _canonical_utc(self.created_at, "created_at")
        _canonical_utc(self.available_at, "available_at")
        if self.available_at.astimezone(timezone.utc) < self.created_at.astimezone(timezone.utc):
            raise ValueError("available_at cannot precede created_at")
        object.__setattr__(self, "event_id", outbox_event_hash(self))


def serialize_outbox_event(event: OutboxEvent) -> bytes:
    if not isinstance(event, OutboxEvent):
        raise ValueError("event must be an OutboxEvent")
    return _json_bytes(_document(event, include_event_id=True))


def deserialize_outbox_event(payload: bytes | str) -> OutboxEvent:
    if isinstance(payload, str):
        encoded = payload.encode("utf-8")
    elif isinstance(payload, bytes):
        encoded = payload
    else:
        raise ValueError("outbox payload must be bytes or text")
    if len(encoded) > MAX_OUTBOX_EVENT_BYTES:
        raise ValueError("serialized outbox event exceeds size limit")
    try:
        raw = json.loads(
            encoded.decode("utf-8"), object_pairs_hook=_unique_object,
            parse_float=_reject_float, parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, UnicodeEncodeError, json.JSONDecodeError) as exc:
        raise ValueError("outbox payload is not valid canonical JSON") from exc
    item = _object(raw, frozenset({
        "available_at", "created_at", "dedupe_key", "event_id",
        "event_kind", "format", "payload", "tenant_id",
    }), "outbox event")
    if item["format"] != OUTBOX_SERIALIZATION_FORMAT:
        raise ValueError("unsupported outbox serialization format")
    payload_items = item["payload"]
    if not isinstance(payload_items, list):
        raise ValueError("outbox payload fields must be a list")
    entries = []
    for index, raw_entry in enumerate(payload_items):
        entry = _object(raw_entry, frozenset({"name", "value"}), f"payload[{index}]")
        entries.append((entry["name"], _decode_value(entry["value"], f"payload[{index}]")))
    try:
        created_at = _parse_canonical_utc(item["created_at"], "created_at")
        available_at = _parse_canonical_utc(item["available_at"], "available_at")
    except DurableStoreIntegrityError as exc:
        raise ValueError("outbox timestamps must be canonical UTC") from exc
    event = OutboxEvent(
        tenant=TenantIdentity(item["tenant_id"]),
        event_kind=item["event_kind"],
        dedupe_key=item["dedupe_key"],
        payload=DurableStatePayload(tuple(entries)),
        created_at=created_at,
        available_at=available_at,
    )
    supplied_id = item["event_id"]
    if (
        not isinstance(supplied_id, str)
        or _HASH.fullmatch(supplied_id) is None
        or not hmac.compare_digest(event.event_id, supplied_id)
        or serialize_outbox_event(event) != encoded
    ):
        raise ValueError("outbox event identity or canonical payload mismatch")
    return event


@dataclass(frozen=True)
class StoredOutboxEvent:
    event: OutboxEvent
    status: OutboxStatus
    attempt_count: int
    next_attempt_at: datetime
    last_error: str | None
    updated_at: datetime
    storage_hash: str
    lease_owner: str | None
    lease_token: str | None
    lease_expires_at: datetime | None
    delivered_at: datetime | None
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)


@dataclass(frozen=True)
class OutboxEnqueueResult:
    record: StoredOutboxEvent
    inserted: bool
    duplicate: bool
    execution_authorized: bool = field(default=False, init=False)


_SELECT = """
SELECT tenant_id, event_id, dedupe_key, event_kind, status, attempt_count,
       next_attempt_at, last_error, created_at, updated_at, payload, payload_sha256,
       lease_owner, lease_token, lease_expires_at, delivered_at
FROM phase3_outbox
"""


class DurableOutbox:
    """Persistence-only outbox; no transport or delivery authority."""

    execution_authorized = False
    production_mutation_authorized = False
    external_delivery_authorized = False

    def __init__(self, store: Phase3DurableStateStore):
        if not isinstance(store, Phase3DurableStateStore):
            raise ValueError("store must be a Phase3DurableStateStore")
        self.store = store

    def _connection(self) -> sqlite3.Connection:
        return self.store._require_open()

    @staticmethod
    def _record(row: tuple[object, ...]) -> StoredOutboxEvent:
        (
            tenant_id, event_id, dedupe_key, event_kind, status, attempt_count,
            next_attempt_at, last_error, created_at, updated_at, payload, payload_hash,
            lease_owner, lease_token, lease_expires_at, delivered_at,
        ) = row
        if (
            not isinstance(payload, bytes)
            or not isinstance(payload_hash, str)
            or _HASH.fullmatch(payload_hash) is None
            or not hmac.compare_digest(hashlib.sha256(payload).hexdigest(), payload_hash)
        ):
            raise OutboxIntegrityError("stored outbox payload hash mismatch")
        try:
            event = deserialize_outbox_event(payload)
            outbox_status = OutboxStatus(status)
            next_attempt = _parse_canonical_utc(next_attempt_at, "next_attempt_at")
            created = _parse_canonical_utc(created_at, "created_at")
            updated = _parse_canonical_utc(updated_at, "updated_at")
            lease_expires = (
                _parse_canonical_utc(lease_expires_at, "lease_expires_at")
                if lease_expires_at is not None else None
            )
            delivered = (
                _parse_canonical_utc(delivered_at, "delivered_at")
                if delivered_at is not None else None
            )
        except (TypeError, ValueError, DurableStoreIntegrityError) as exc:
            raise OutboxIntegrityError("stored outbox event is invalid") from exc
        if (
            (tenant_id, event_id, dedupe_key, event_kind, created_at)
            != (
                event.tenant.tenant_id, event.event_id, event.dedupe_key,
                event.event_kind, _canonical_utc(event.created_at, "created_at"),
            )
            or type(attempt_count) is not int
            or attempt_count < 0
            or (
                last_error is not None
                and (
                    not isinstance(last_error, str)
                    or last_error != sanitize_outbox_error(last_error)
                )
            )
            or updated < created
        ):
            raise OutboxIntegrityError("stored outbox index or state mismatch")
        lease_values = (lease_owner, lease_token, lease_expires)
        if outbox_status is OutboxStatus.IN_PROGRESS:
            if (
                not isinstance(lease_owner, str) or not lease_owner
                or not isinstance(lease_token, str) or not lease_token
                or lease_expires is None or lease_expires <= updated
                or delivered is not None or last_error is not None
                or attempt_count < 1
            ):
                raise OutboxIntegrityError("in-progress outbox lease is invalid")
        elif any(value is not None for value in lease_values):
            raise OutboxIntegrityError("inactive outbox event retains a lease")
        if outbox_status is OutboxStatus.DELIVERED:
            if (
                delivered is None or delivered != updated
                or last_error is not None or attempt_count < 1
            ):
                raise OutboxIntegrityError("delivered outbox state is invalid")
        elif delivered is not None:
            raise OutboxIntegrityError("undelivered outbox event has delivered_at")
        if (
            outbox_status is OutboxStatus.DEAD_LETTER
            and (not last_error or attempt_count < 1)
        ):
            raise OutboxIntegrityError("dead-letter outbox state requires an error")
        if (
            outbox_status is OutboxStatus.PENDING
            and attempt_count > 0 and not last_error
        ):
            raise OutboxIntegrityError("retrying outbox state requires an error")
        return StoredOutboxEvent(
            event, outbox_status, attempt_count, next_attempt, last_error,
            updated, payload_hash, lease_owner, lease_token, lease_expires, delivered,
        )

    def enqueue(self, event: OutboxEvent) -> OutboxEnqueueResult:
        connection = self._connection()
        if self.store.read_only:
            raise DurableStoreReadOnlyError("phase3 store is read-only")
        if not isinstance(event, OutboxEvent):
            raise ValueError("event must be an OutboxEvent")
        payload = serialize_outbox_event(event)
        payload_hash = hashlib.sha256(payload).hexdigest()
        tenant_id = event.tenant.tenant_id
        created_text = _canonical_utc(event.created_at, "created_at")
        available_text = _canonical_utc(event.available_at, "available_at")
        try:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                _SELECT + " WHERE tenant_id = ? AND dedupe_key = ?",
                (tenant_id, event.dedupe_key),
            ).fetchone()
            if existing is not None:
                record = self._record(existing)
                if record.event.event_id != event.event_id:
                    raise OutboxConflictError(
                        "dedupe key already identifies different immutable content"
                    )
                connection.execute("COMMIT")
                return OutboxEnqueueResult(record, False, True)
            connection.execute(
                "INSERT OR IGNORE INTO phase3_tenants VALUES (?, ?)",
                (tenant_id, created_text),
            )
            connection.execute(
                """INSERT INTO phase3_outbox(
                    tenant_id, event_id, dedupe_key, event_kind, status,
                    attempt_count, next_attempt_at, last_error, created_at,
                    updated_at, payload, payload_sha256
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    tenant_id, event.event_id, event.dedupe_key, event.event_kind,
                    OutboxStatus.PENDING.value, 0, available_text, None,
                    created_text, created_text, payload, payload_hash,
                ),
            )
            row = connection.execute(
                _SELECT + " WHERE tenant_id = ? AND event_id = ?",
                (tenant_id, event.event_id),
            ).fetchone()
            record = self._record(row)
            connection.execute("COMMIT")
            return OutboxEnqueueResult(record, True, False)
        except BaseException:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise

    def by_id(self, *, tenant_id: str, event_id: str) -> StoredOutboxEvent | None:
        row = self._connection().execute(
            _SELECT + " WHERE tenant_id = ? AND event_id = ?", (tenant_id, event_id)
        ).fetchone()
        return None if row is None else self._record(row)

    def ready(self, *, tenant_id: str, now: datetime, limit: int = 100) -> tuple[StoredOutboxEvent, ...]:
        now_text = _canonical_utc(now, "now")
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        rows = self._connection().execute(
            _SELECT + """ WHERE tenant_id = ? AND status = ? AND next_attempt_at <= ?
                ORDER BY next_attempt_at, created_at, event_id LIMIT ?""",
            (tenant_id, OutboxStatus.PENDING.value, now_text, limit),
        ).fetchall()
        return tuple(self._record(row) for row in rows)
