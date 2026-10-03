"""Append-only, tenant-scoped Phase 3 audit evidence."""

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
from .state_contracts import (
    AccountIdentity,
    DurableStatePayload,
    PropFirmProfileIdentity,
    SourceIdentity,
    TenantIdentity,
    UserIdentity,
)


AUDIT_SERIALIZATION_FORMAT = "arms.phase3.audit-event-json.v1"
MAX_AUDIT_EVENT_BYTES = 1_048_576
_HASH = re.compile(r"^[0-9a-f]{64}$")


class AuditEventKind(str, Enum):
    SNAPSHOT_RECEIVED = "SNAPSHOT_RECEIVED"
    SNAPSHOT_REJECTED = "SNAPSHOT_REJECTED"
    PROFILE_RESOLVED = "PROFILE_RESOLVED"
    EVALUATION_COMPLETED = "EVALUATION_COMPLETED"
    AUTHORIZATION_DENIED = "AUTHORIZATION_DENIED"
    NOTIFICATION_QUEUED = "NOTIFICATION_QUEUED"
    NOTIFICATION_SENT = "NOTIFICATION_SENT"
    NOTIFICATION_TESTED = "NOTIFICATION_TESTED"
    RESEARCH_JOB_CREATED = "RESEARCH_JOB_CREATED"
    RESEARCH_JOB_COMPLETED = "RESEARCH_JOB_COMPLETED"
    CANDIDATE_PROMOTED_TO_PAPER_REVIEW = "CANDIDATE_PROMOTED_TO_PAPER_REVIEW"
    CANDIDATE_REJECTED = "CANDIDATE_REJECTED"


class AuditLogError(RuntimeError):
    """Base audit log failure."""


class AuditLogIntegrityError(AuditLogError):
    """Stored audit evidence is corrupt or inconsistent."""


def _object(value: object, keys: frozenset[str], name: str) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError(f"{name} must contain exactly the required fields")
    return value


def _optional_text(value: object, name: str) -> str | None:
    if value is not None and (not isinstance(value, str) or not value.strip()):
        raise ValueError(f"{name} must be nonempty text or null")
    return value


def _event_document(event: "AuditEvent", *, include_event_id: bool) -> dict[str, object]:
    profile = None
    if event.profile is not None:
        profile = {
            "account_size": _encode_value(event.profile.account_size),
            "config_hash": event.profile.config_hash,
            "firm_id": event.profile.firm_id,
            "profile_version": event.profile.profile_version,
            "program_id": event.profile.program_id,
            "stage": event.profile.stage,
        }
    document = {
        "account_id": event.account.account_id if event.account else None,
        "actor_user_id": event.actor.user_id if event.actor else None,
        "authority": {
            "canonical_admin_authorized": False,
            "execution_authorized": False,
            "production_mutation_authorized": False,
        },
        "causation_id": event.causation_id,
        "correlation_id": event.correlation_id,
        "event_kind": event.kind.value,
        "format": AUDIT_SERIALIZATION_FORMAT,
        "occurred_at": _canonical_utc(event.occurred_at, "occurred_at"),
        "payload": [
            {"name": name, "value": _encode_value(value)}
            for name, value in event.payload.entries
        ],
        "profile": profile,
        "source": {
            "simulated": event.source.simulated,
            "source_id": event.source.source_id,
            "source_version": event.source.source_version,
        },
        "tenant_id": event.tenant.tenant_id,
    }
    if include_event_id:
        document["event_id"] = event.event_id
    return document


def _json_bytes(document: dict[str, object]) -> bytes:
    encoded = json.dumps(
        document, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    if len(encoded) > MAX_AUDIT_EVENT_BYTES:
        raise ValueError("serialized audit event exceeds size limit")
    return encoded


def audit_event_hash(event: "AuditEvent") -> str:
    return hashlib.sha256(_json_bytes(_event_document(event, include_event_id=False))).hexdigest()


@dataclass(frozen=True)
class AuditEvent:
    kind: AuditEventKind
    occurred_at: datetime
    tenant: TenantIdentity
    source: SourceIdentity
    payload: DurableStatePayload
    actor: UserIdentity | None = None
    account: AccountIdentity | None = None
    profile: PropFirmProfileIdentity | None = None
    correlation_id: str | None = None
    causation_id: str | None = None
    event_id: str = field(init=False)
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)
    canonical_admin_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.kind, AuditEventKind):
            raise ValueError("kind must be an AuditEventKind")
        _canonical_utc(self.occurred_at, "occurred_at")
        if not isinstance(self.tenant, TenantIdentity):
            raise ValueError("tenant must be a TenantIdentity")
        if not isinstance(self.source, SourceIdentity):
            raise ValueError("source must be a SourceIdentity")
        if not isinstance(self.payload, DurableStatePayload):
            raise ValueError("payload must be a DurableStatePayload")
        if self.actor is not None and (
            not isinstance(self.actor, UserIdentity)
            or self.actor.tenant_id != self.tenant.tenant_id
        ):
            raise ValueError("actor must belong to the event tenant")
        if self.account is not None and (
            not isinstance(self.account, AccountIdentity)
            or self.account.tenant_id != self.tenant.tenant_id
        ):
            raise ValueError("account must belong to the event tenant")
        if self.profile is not None and not isinstance(self.profile, PropFirmProfileIdentity):
            raise ValueError("profile must be a PropFirmProfileIdentity")
        _optional_text(self.correlation_id, "correlation_id")
        _optional_text(self.causation_id, "causation_id")
        object.__setattr__(self, "event_id", audit_event_hash(self))


def serialize_audit_event(event: AuditEvent) -> bytes:
    if not isinstance(event, AuditEvent):
        raise ValueError("event must be an AuditEvent")
    return _json_bytes(_event_document(event, include_event_id=True))


def deserialize_audit_event(payload: bytes | str) -> AuditEvent:
    if isinstance(payload, str):
        encoded = payload.encode("utf-8")
    elif isinstance(payload, bytes):
        encoded = payload
    else:
        raise ValueError("audit payload must be bytes or text")
    if len(encoded) > MAX_AUDIT_EVENT_BYTES:
        raise ValueError("serialized audit event exceeds size limit")
    try:
        raw = json.loads(
            encoded.decode("utf-8"), object_pairs_hook=_unique_object,
            parse_float=_reject_float, parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, UnicodeEncodeError, json.JSONDecodeError) as exc:
        raise ValueError("audit payload is not valid canonical JSON") from exc
    item = _object(raw, frozenset({
        "account_id", "actor_user_id", "authority", "causation_id",
        "correlation_id", "event_id", "event_kind", "format", "occurred_at",
        "payload", "profile", "source", "tenant_id",
    }), "audit event")
    if item["format"] != AUDIT_SERIALIZATION_FORMAT:
        raise ValueError("unsupported audit serialization format")
    if item["authority"] != {
        "canonical_admin_authorized": False,
        "execution_authorized": False,
        "production_mutation_authorized": False,
    }:
        raise ValueError("audit authority fields must remain false")
    tenant = TenantIdentity(item["tenant_id"])
    source_item = _object(
        item["source"], frozenset({"simulated", "source_id", "source_version"}), "source"
    )
    source = SourceIdentity(
        source_item["source_id"], source_item["source_version"], source_item["simulated"]
    )
    actor_id = _optional_text(item["actor_user_id"], "actor_user_id")
    account_id = _optional_text(item["account_id"], "account_id")
    profile_item = item["profile"]
    profile = None
    if profile_item is not None:
        profile_value = _object(profile_item, frozenset({
            "account_size", "config_hash", "firm_id", "profile_version",
            "program_id", "stage",
        }), "profile")
        profile = PropFirmProfileIdentity(
            firm_id=profile_value["firm_id"],
            program_id=profile_value["program_id"],
            stage=profile_value["stage"],
            account_size=_decode_value(profile_value["account_size"], "profile.account_size"),
            profile_version=profile_value["profile_version"],
            config_hash=profile_value["config_hash"],
        )
    payload_items = item["payload"]
    if not isinstance(payload_items, list):
        raise ValueError("audit payload fields must be a list")
    entries = []
    for index, raw_entry in enumerate(payload_items):
        entry = _object(raw_entry, frozenset({"name", "value"}), f"payload[{index}]")
        entries.append((entry["name"], _decode_value(entry["value"], f"payload[{index}]")))
    try:
        occurred_at = _parse_canonical_utc(item["occurred_at"], "occurred_at")
    except DurableStoreIntegrityError as exc:
        raise ValueError("occurred_at must be canonical UTC") from exc
    event = AuditEvent(
        kind=AuditEventKind(item["event_kind"]),
        occurred_at=occurred_at,
        tenant=tenant,
        source=source,
        payload=DurableStatePayload(tuple(entries)),
        actor=UserIdentity(tenant.tenant_id, actor_id) if actor_id else None,
        account=AccountIdentity(tenant.tenant_id, account_id) if account_id else None,
        profile=profile,
        correlation_id=_optional_text(item["correlation_id"], "correlation_id"),
        causation_id=_optional_text(item["causation_id"], "causation_id"),
    )
    supplied_id = item["event_id"]
    if (
        not isinstance(supplied_id, str)
        or _HASH.fullmatch(supplied_id) is None
        or not hmac.compare_digest(event.event_id, supplied_id)
        or serialize_audit_event(event) != encoded
    ):
        raise ValueError("audit event identity or canonical payload mismatch")
    return event


@dataclass(frozen=True)
class StoredAuditEvent:
    event: AuditEvent
    recorded_at: datetime
    storage_hash: str
    inserted: bool
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)


class AuditLog:
    """Append-only audit repository with deterministic idempotence."""

    execution_authorized = False
    production_mutation_authorized = False
    canonical_admin_authorized = False

    def __init__(self, store: Phase3DurableStateStore):
        if not isinstance(store, Phase3DurableStateStore):
            raise ValueError("store must be a Phase3DurableStateStore")
        self.store = store

    def _connection(self) -> sqlite3.Connection:
        return self.store._require_open()

    @staticmethod
    def _record(row: tuple[object, ...], *, inserted: bool = False) -> StoredAuditEvent:
        (
            tenant_id, event_id, event_kind, occurred_at, recorded_at,
            source_id, source_version, source_simulated, actor_user_id,
            account_id, profile_hash, payload, payload_hash,
        ) = row
        if (
            not isinstance(payload, bytes)
            or not isinstance(payload_hash, str)
            or _HASH.fullmatch(payload_hash) is None
            or not hmac.compare_digest(hashlib.sha256(payload).hexdigest(), payload_hash)
        ):
            raise AuditLogIntegrityError("stored audit payload hash mismatch")
        try:
            event = deserialize_audit_event(payload)
            recorded = _parse_canonical_utc(recorded_at, "recorded_at")
        except (TypeError, ValueError, DurableStoreIntegrityError) as exc:
            raise AuditLogIntegrityError("stored audit event is invalid") from exc
        expected = (
            event.tenant.tenant_id, event.event_id, event.kind.value,
            _canonical_utc(event.occurred_at, "occurred_at"),
            event.source.source_id, event.source.source_version,
            int(event.source.simulated), event.actor.user_id if event.actor else None,
            event.account.account_id if event.account else None,
            event.profile.config_hash if event.profile else None,
        )
        actual = (
            tenant_id, event_id, event_kind, occurred_at, source_id,
            source_version, source_simulated, actor_user_id, account_id, profile_hash,
        )
        if expected != actual:
            raise AuditLogIntegrityError("stored audit index mismatch")
        return StoredAuditEvent(event, recorded, payload_hash, inserted)

    def append(self, event: AuditEvent, *, recorded_at: datetime) -> StoredAuditEvent:
        connection = self._connection()
        if self.store.read_only:
            raise DurableStoreReadOnlyError("phase3 store is read-only")
        if not isinstance(event, AuditEvent):
            raise ValueError("event must be an AuditEvent")
        recorded_text = _canonical_utc(recorded_at, "recorded_at")
        if recorded_at.astimezone(timezone.utc) < event.occurred_at.astimezone(timezone.utc):
            raise ValueError("recorded_at cannot precede occurred_at")
        payload = serialize_audit_event(event)
        payload_hash = hashlib.sha256(payload).hexdigest()
        tenant_id = event.tenant.tenant_id
        try:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                """SELECT tenant_id, event_id, event_kind, occurred_at, recorded_at,
                          source_id, source_version, source_simulated, actor_user_id,
                          account_id, profile_config_hash, payload, payload_sha256
                   FROM phase3_audit_events WHERE tenant_id = ? AND event_id = ?""",
                (tenant_id, event.event_id),
            ).fetchone()
            if existing is not None:
                record = self._record(existing)
                connection.execute("COMMIT")
                return record
            connection.execute(
                "INSERT OR IGNORE INTO phase3_tenants VALUES (?, ?)",
                (tenant_id, recorded_text),
            )
            connection.execute(
                """INSERT INTO phase3_audit_events(
                    tenant_id, event_id, event_kind, occurred_at, recorded_at,
                    source_id, source_version, source_simulated, actor_user_id,
                    account_id, profile_config_hash, payload, payload_sha256
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    tenant_id, event.event_id, event.kind.value,
                    _canonical_utc(event.occurred_at, "occurred_at"), recorded_text,
                    event.source.source_id, event.source.source_version,
                    int(event.source.simulated), event.actor.user_id if event.actor else None,
                    event.account.account_id if event.account else None,
                    event.profile.config_hash if event.profile else None,
                    payload, payload_hash,
                ),
            )
            row = connection.execute(
                """SELECT tenant_id, event_id, event_kind, occurred_at, recorded_at,
                          source_id, source_version, source_simulated, actor_user_id,
                          account_id, profile_config_hash, payload, payload_sha256
                   FROM phase3_audit_events WHERE tenant_id = ? AND event_id = ?""",
                (tenant_id, event.event_id),
            ).fetchone()
            record = self._record(row, inserted=True)
            connection.execute("COMMIT")
            return record
        except BaseException:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise

    def by_id(self, *, tenant_id: str, event_id: str) -> StoredAuditEvent | None:
        row = self._connection().execute(
            """SELECT tenant_id, event_id, event_kind, occurred_at, recorded_at,
                      source_id, source_version, source_simulated, actor_user_id,
                      account_id, profile_config_hash, payload, payload_sha256
               FROM phase3_audit_events WHERE tenant_id = ? AND event_id = ?""",
            (tenant_id, event_id),
        ).fetchone()
        return None if row is None else self._record(row)

    def history(
        self, *, tenant_id: str, kind: AuditEventKind | None = None, limit: int = 1000
    ) -> tuple[StoredAuditEvent, ...]:
        if type(limit) is not int or not 1 <= limit <= 10_000:
            raise ValueError("limit must be between 1 and 10000")
        if kind is not None and not isinstance(kind, AuditEventKind):
            raise ValueError("kind must be an AuditEventKind or None")
        where = "tenant_id = ?"
        values: tuple[object, ...] = (tenant_id,)
        if kind is not None:
            where += " AND event_kind = ?"
            values += (kind.value,)
        rows = self._connection().execute(
            f"""SELECT tenant_id, event_id, event_kind, occurred_at, recorded_at,
                       source_id, source_version, source_simulated, actor_user_id,
                       account_id, profile_config_hash, payload, payload_sha256
                FROM phase3_audit_events WHERE {where}
                ORDER BY occurred_at, event_id LIMIT ?""",
            values + (limit,),
        ).fetchall()
        return tuple(self._record(row) for row in rows)
