"""Durable, append-only repository for validated prop-firm snapshots."""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import hmac
import json
import re
import sqlite3
from typing import NoReturn

from backend.prop_firms import (
    AccountSnapshot,
    AccountStage,
    ExposurePosition,
    PayoutCycleSnapshot,
    PropFirmAccountSnapshot,
)

from .durable_store import (
    DurableStoreIntegrityError,
    DurableStoreReadOnlyError,
    Phase3DurableStateStore,
    _canonical_utc,
    _parse_canonical_utc,
    _profile_account_size_payload,
)
from .financial_serialization import canonical_decimal_text
from .snapshot_ingestion import (
    IngestionCode,
    SnapshotCursor,
    SnapshotIngestionDecision,
    SnapshotIngestionRequest,
)
from .state_contracts import AccountIdentity, SourceIdentity, TenantIdentity


SNAPSHOT_SERIALIZATION_FORMAT = "arms.phase3.prop-firm-snapshot-json.v1"
MAX_SNAPSHOT_BYTES = 1_048_576
_HASH = re.compile(r"^[0-9a-f]{64}$")


class SnapshotRepositoryError(RuntimeError):
    """Base repository failure."""


class SnapshotRepositoryRejectedError(SnapshotRepositoryError):
    """The ingestion decision does not authorize a durable snapshot append."""


class SnapshotRepositoryConflictError(SnapshotRepositoryError):
    """An immutable snapshot identity conflicts with stored evidence."""


class SnapshotRepositoryOrderError(SnapshotRepositoryError):
    """A new snapshot would regress sequence or capture time."""


class SnapshotRepositoryIntegrityError(SnapshotRepositoryError):
    """Stored snapshot evidence failed strict validation."""


def _reject_float(_: str) -> NoReturn:
    raise ValueError("snapshot JSON floating-point numbers are forbidden")


def _reject_constant(_: str) -> NoReturn:
    raise ValueError("snapshot JSON non-finite numbers are forbidden")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate snapshot JSON field: {key}")
        result[key] = value
    return result


def _object(value: object, keys: frozenset[str], name: str) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError(f"{name} must contain exactly the required fields")
    return value


def _decimal_document(value: Decimal) -> dict[str, object]:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise ValueError("snapshot decimal must be finite")
    return {
        "$type": "decimal",
        "source_normalized": str(value.normalize()),
        "value": canonical_decimal_text(value),
    }


def _decode_decimal(value: object, name: str) -> Decimal:
    item = _object(value, frozenset({"$type", "source_normalized", "value"}), name)
    if item["$type"] != "decimal":
        raise ValueError(f"{name} must be a decimal")
    source = item["source_normalized"]
    canonical = item["value"]
    if not isinstance(source, str) or not isinstance(canonical, str):
        raise ValueError(f"{name} decimal values must be strings")
    try:
        number = Decimal(source)
    except InvalidOperation as exc:
        raise ValueError(f"{name} contains an invalid decimal") from exc
    if (
        not number.is_finite()
        or str(number.normalize()) != source
        or canonical_decimal_text(number) != canonical
    ):
        raise ValueError(f"{name} decimal representation is not canonical")
    return number


def _timestamp_document(value: datetime) -> dict[str, object]:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("snapshot timestamp must be timezone-aware")
    offset = value.utcoffset()
    offset_microseconds = (
        (offset.days * 86400 + offset.seconds) * 1_000_000 + offset.microseconds
    )
    return {
        "$type": "timestamp",
        "offset_microseconds": offset_microseconds,
        "utc": _canonical_utc(value, "timestamp"),
    }


def _decode_timestamp(value: object, name: str) -> datetime:
    item = _object(value, frozenset({"$type", "offset_microseconds", "utc"}), name)
    if item["$type"] != "timestamp":
        raise ValueError(f"{name} must be a timestamp")
    offset = item["offset_microseconds"]
    utc = item["utc"]
    if type(offset) is not int or not -86_399_999_999 < offset < 86_399_999_999:
        raise ValueError(f"{name} offset is invalid")
    try:
        parsed = _parse_canonical_utc(utc, name)
    except DurableStoreIntegrityError as exc:
        raise ValueError(f"{name} timestamp is not canonical") from exc
    return parsed.astimezone(timezone(timedelta(microseconds=offset)))


def _encode_value(value: object) -> object:
    if isinstance(value, AccountStage):
        return {"$type": "account_stage", "value": value.value}
    if value is None or type(value) in (bool, int) or isinstance(value, str):
        return value
    if isinstance(value, Decimal):
        return _decimal_document(value)
    if isinstance(value, datetime):
        return _timestamp_document(value)
    raise ValueError("unsupported snapshot value")


def _decode_value(value: object, name: str) -> object:
    if value is None or type(value) in (bool, int) or isinstance(value, str):
        return value
    if not isinstance(value, dict):
        raise ValueError(f"{name} contains an unsupported value")
    value_type = value.get("$type")
    if value_type == "decimal":
        return _decode_decimal(value, name)
    if value_type == "timestamp":
        return _decode_timestamp(value, name)
    if value_type == "account_stage":
        item = _object(value, frozenset({"$type", "value"}), name)
        try:
            return AccountStage(item["value"])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} contains an invalid account stage") from exc
    raise ValueError(f"{name} contains an unknown tagged value")


def _dataclass_document(value: object) -> dict[str, object]:
    return {
        item.name: _encode_value(getattr(value, item.name))
        for item in fields(value)
    }


def _state_document(state: AccountSnapshot) -> dict[str, object]:
    document = {
        item.name: _encode_value(getattr(state, item.name))
        for item in fields(state)
        if item.name not in {"exposures", "payout_cycle"}
    }
    if state.exposures is not None:
        document["exposures"] = [
            _dataclass_document(exposure) for exposure in state.exposures
        ]
    if state.payout_cycle is not None:
        document["payout_cycle"] = _dataclass_document(state.payout_cycle)
    return document


def _decode_exposures(value: object) -> tuple[ExposurePosition, ...] | None:
    if value is None:
        return None
    if not isinstance(value, list) or len(value) > 10_000:
        raise ValueError("exposures must be a bounded list")
    required = frozenset(item.name for item in fields(ExposurePosition))
    result = []
    for index, raw in enumerate(value):
        item = _object(raw, required, f"exposures[{index}]")
        result.append(ExposurePosition(**{
            name: _decode_value(field_value, f"exposures[{index}].{name}")
            for name, field_value in item.items()
        }))
    return tuple(result)


def _decode_payout_cycle(value: object) -> PayoutCycleSnapshot | None:
    if value is None:
        return None
    required = frozenset(item.name for item in fields(PayoutCycleSnapshot))
    item = _object(value, required, "payout_cycle")
    return PayoutCycleSnapshot(**{
        name: _decode_value(field_value, f"payout_cycle.{name}")
        for name, field_value in item.items()
    })


def serialize_account_snapshot(snapshot: PropFirmAccountSnapshot) -> bytes:
    if not isinstance(snapshot, PropFirmAccountSnapshot):
        raise ValueError("snapshot must be a PropFirmAccountSnapshot")
    document = {
        "account_id": snapshot.account_id,
        "account_size": _decimal_document(snapshot.account_size),
        "captured_at": _timestamp_document(snapshot.captured_at),
        "content_hash": snapshot.content_hash,
        "data_source": snapshot.data_source,
        "firm_id": snapshot.firm_id,
        "format": SNAPSHOT_SERIALIZATION_FORMAT,
        "profile_version": snapshot.profile_version,
        "program_id": snapshot.program_id,
        "simulated": snapshot.simulated,
        "stage": snapshot.stage.value,
        "state": _state_document(snapshot.state),
    }
    try:
        payload = json.dumps(
            document,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError("snapshot contains invalid UTF-8 text") from exc
    if len(payload) > MAX_SNAPSHOT_BYTES:
        raise ValueError("serialized snapshot exceeds size limit")
    return payload


def deserialize_account_snapshot(payload: bytes | str) -> PropFirmAccountSnapshot:
    if isinstance(payload, str):
        try:
            encoded = payload.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise ValueError("snapshot payload is not valid UTF-8") from exc
    elif isinstance(payload, bytes):
        encoded = payload
    else:
        raise ValueError("snapshot payload must be bytes or text")
    if len(encoded) > MAX_SNAPSHOT_BYTES:
        raise ValueError("serialized snapshot exceeds size limit")
    try:
        document = json.loads(
            encoded.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("snapshot payload is not valid canonical JSON") from exc
    top_keys = frozenset({
        "account_id", "account_size", "captured_at", "content_hash",
        "data_source", "firm_id", "format", "profile_version", "program_id",
        "simulated", "stage", "state",
    })
    item = _object(document, top_keys, "snapshot")
    if item["format"] != SNAPSHOT_SERIALIZATION_FORMAT:
        raise ValueError("unsupported snapshot serialization format")
    state_keys = frozenset(field_info.name for field_info in fields(AccountSnapshot))
    state_document = _object(item["state"], state_keys, "state")
    state_values = {
        name: _decode_value(value, f"state.{name}")
        for name, value in state_document.items()
        if name not in {"exposures", "payout_cycle"}
    }
    state_values["exposures"] = _decode_exposures(state_document["exposures"])
    state_values["payout_cycle"] = _decode_payout_cycle(
        state_document["payout_cycle"]
    )
    try:
        stage = AccountStage(item["stage"])
    except (TypeError, ValueError) as exc:
        raise ValueError("snapshot stage is invalid") from exc
    snapshot = PropFirmAccountSnapshot(
        account_id=item["account_id"],
        firm_id=item["firm_id"],
        program_id=item["program_id"],
        profile_version=item["profile_version"],
        stage=stage,
        account_size=_decode_decimal(item["account_size"], "account_size"),
        captured_at=_decode_timestamp(item["captured_at"], "captured_at"),
        data_source=item["data_source"],
        simulated=item["simulated"],
        state=AccountSnapshot(**state_values),
    )
    content_hash = item["content_hash"]
    if (
        not isinstance(content_hash, str)
        or _HASH.fullmatch(content_hash) is None
        or not hmac.compare_digest(snapshot.content_hash, content_hash)
    ):
        raise ValueError("snapshot content hash mismatch")
    if serialize_account_snapshot(snapshot) != encoded:
        raise ValueError("snapshot payload is not canonical")
    return snapshot


@dataclass(frozen=True)
class SnapshotStreamIdentity:
    tenant_id: str
    account_id: str
    source_id: str
    source_version: str
    source_simulated: bool
    profile_config_hash: str
    currency: str

    def __post_init__(self) -> None:
        TenantIdentity(self.tenant_id)
        AccountIdentity(self.tenant_id, self.account_id)
        SourceIdentity(self.source_id, self.source_version, self.source_simulated)
        if not isinstance(self.profile_config_hash, str) or _HASH.fullmatch(
            self.profile_config_hash
        ) is None:
            raise ValueError("profile_config_hash must be a lowercase sha256 digest")
        if not isinstance(self.currency, str) or re.fullmatch(
            r"[A-Z]{3}", self.currency
        ) is None:
            raise ValueError("currency must be a three-letter ISO code")


@dataclass(frozen=True)
class StoredAccountSnapshot:
    snapshot_id: str
    stream: SnapshotStreamIdentity
    sequence: int
    received_at: datetime
    stored_at: datetime
    snapshot: PropFirmAccountSnapshot
    snapshot_hash: str
    storage_hash: str
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)
    canonical_admin_authorized: bool = field(default=False, init=False)


@dataclass(frozen=True)
class SnapshotAppendResult:
    record: StoredAccountSnapshot
    inserted: bool
    duplicate: bool
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)
    canonical_admin_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if type(self.inserted) is not bool or type(self.duplicate) is not bool:
            raise ValueError("inserted and duplicate must be boolean")
        if self.inserted == self.duplicate:
            raise ValueError("append result must be inserted or duplicate")


_SELECT = """
SELECT snapshot_id, tenant_id, account_id, source_id, source_version,
       source_simulated, profile_config_hash, currency, sequence, captured_at,
       received_at, stored_at, snapshot_hash, payload, payload_sha256,
       profile_firm_id, profile_program_id, profile_stage,
       profile_version, profile_account_size_payload
FROM (
    SELECT snapshots.*,
           profiles.firm_id AS profile_firm_id,
           profiles.program_id AS profile_program_id,
           profiles.stage AS profile_stage,
           profiles.profile_version AS profile_version,
           profiles.account_size_payload AS profile_account_size_payload
    FROM phase3_account_snapshots AS snapshots
    JOIN phase3_profiles AS profiles
      ON profiles.config_hash = snapshots.profile_config_hash
) AS snapshot_rows
"""


def _stream_from_request(request: SnapshotIngestionRequest) -> SnapshotStreamIdentity:
    return SnapshotStreamIdentity(
        tenant_id=request.tenant.tenant_id,
        account_id=request.account.account_id,
        source_id=request.source.identity.source_id,
        source_version=request.source.identity.source_version,
        source_simulated=request.source.identity.simulated,
        profile_config_hash=request.profile.config_hash,
        currency=request.currency,
    )


def _stream_values(stream: SnapshotStreamIdentity) -> tuple[object, ...]:
    return (
        stream.tenant_id,
        stream.account_id,
        stream.source_id,
        stream.source_version,
        int(stream.source_simulated),
        stream.profile_config_hash,
        stream.currency,
    )


class AccountSnapshotRepository:
    """Trusted persistence adapter; authorization remains an outer boundary."""

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
    def _validate_decision(
        request: SnapshotIngestionRequest,
        decision: SnapshotIngestionDecision,
    ) -> None:
        if not isinstance(request, SnapshotIngestionRequest):
            raise ValueError("request must be a SnapshotIngestionRequest")
        if not isinstance(decision, SnapshotIngestionDecision):
            raise ValueError("decision must be a SnapshotIngestionDecision")
        if decision.code not in {
            IngestionCode.ACCEPTED,
            IngestionCode.DUPLICATE_IDEMPOTENT,
        }:
            raise SnapshotRepositoryRejectedError(
                f"snapshot ingestion was rejected: {decision.code.value}"
            )
        expected = SnapshotCursor(
            tenant_id=request.tenant.tenant_id,
            account_id=request.account.account_id,
            source_id=request.source.identity.source_id,
            source_version=request.source.identity.source_version,
            profile_config_hash=request.profile.config_hash,
            currency=request.currency,
            sequence=request.sequence,
            captured_at=request.snapshot.captured_at,
            payload_hash=request.snapshot.content_hash,
        )
        if decision.next_cursor != expected:
            raise SnapshotRepositoryRejectedError(
                "ingestion decision cursor does not match the snapshot"
            )

    @staticmethod
    def _limit(value: int) -> int:
        if type(value) is not int or not 1 <= value <= 10_000:
            raise ValueError("limit must be between 1 and 10000")
        return value

    @staticmethod
    def _record(row: tuple[object, ...]) -> StoredAccountSnapshot:
        (
            snapshot_id, tenant_id, account_id, source_id, source_version,
            source_simulated, profile_hash, currency, sequence, captured_at,
            received_at, stored_at, snapshot_hash, payload, payload_sha256,
            profile_firm_id, profile_program_id, profile_stage,
            profile_version, profile_account_size_payload,
        ) = row
        if (
            not isinstance(payload, bytes)
            or not isinstance(payload_sha256, str)
            or _HASH.fullmatch(payload_sha256) is None
            or not hmac.compare_digest(
                hashlib.sha256(payload).hexdigest(), payload_sha256
            )
        ):
            raise SnapshotRepositoryIntegrityError("stored snapshot payload hash mismatch")
        try:
            snapshot = deserialize_account_snapshot(payload)
            stream = SnapshotStreamIdentity(
                tenant_id=tenant_id,
                account_id=account_id,
                source_id=source_id,
                source_version=source_version,
                source_simulated=bool(source_simulated),
                profile_config_hash=profile_hash,
                currency=currency,
            )
            captured = _parse_canonical_utc(captured_at, "captured_at")
            received = _parse_canonical_utc(received_at, "received_at")
            stored = _parse_canonical_utc(stored_at, "stored_at")
        except (TypeError, ValueError, DurableStoreIntegrityError) as exc:
            raise SnapshotRepositoryIntegrityError("stored snapshot is invalid") from exc
        expected_profile_payload = json.dumps(
            {
                "currency": currency,
                "unit": "currency",
                "value": canonical_decimal_text(snapshot.account_size),
            },
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        if (
            not isinstance(snapshot_id, str)
            or type(source_simulated) is not int
            or source_simulated not in (0, 1)
            or type(sequence) is not int
            or sequence < 1
            or snapshot.account_id != account_id
            or snapshot.data_source != source_id
            or snapshot.simulated is not bool(source_simulated)
            or snapshot.captured_at != captured
            or snapshot.content_hash != snapshot_hash
            or snapshot.firm_id != profile_firm_id
            or snapshot.program_id != profile_program_id
            or snapshot.stage.value != profile_stage
            or snapshot.profile_version != profile_version
            or expected_profile_payload != profile_account_size_payload
        ):
            raise SnapshotRepositoryIntegrityError("stored snapshot index mismatch")
        return StoredAccountSnapshot(
            snapshot_id=snapshot_id,
            stream=stream,
            sequence=sequence,
            received_at=received,
            stored_at=stored,
            snapshot=snapshot,
            snapshot_hash=snapshot_hash,
            storage_hash=payload_sha256,
        )

    def append(
        self,
        request: SnapshotIngestionRequest,
        decision: SnapshotIngestionDecision,
        *,
        stored_at: datetime,
    ) -> SnapshotAppendResult:
        self._validate_decision(request, decision)
        connection = self._connection()
        if self.store.read_only:
            raise DurableStoreReadOnlyError("phase3 store is read-only")
        stored_text = _canonical_utc(stored_at, "stored_at")
        if stored_at.astimezone(timezone.utc) < request.received_at.astimezone(timezone.utc):
            raise ValueError("stored_at cannot precede received_at")
        stream = _stream_from_request(request)
        values = _stream_values(stream)
        payload = serialize_account_snapshot(request.snapshot)
        storage_hash = hashlib.sha256(payload).hexdigest()
        captured_text = _canonical_utc(request.snapshot.captured_at, "captured_at")
        received_text = _canonical_utc(request.received_at, "received_at")

        try:
            connection.execute("BEGIN IMMEDIATE")
            by_id = connection.execute(
                _SELECT + " WHERE tenant_id = ? AND snapshot_id = ?",
                (stream.tenant_id, request.ingestion_id),
            ).fetchone()
            if by_id is not None:
                existing = self._record(by_id)
                if not self._same(existing, request, stream, payload):
                    raise SnapshotRepositoryConflictError(
                        "snapshot_id already has different immutable content"
                    )
                connection.execute("COMMIT")
                return SnapshotAppendResult(existing, inserted=False, duplicate=True)

            by_sequence = connection.execute(
                _SELECT + """
                WHERE tenant_id = ? AND account_id = ? AND source_id = ?
                  AND source_version = ? AND source_simulated = ?
                  AND profile_config_hash = ? AND currency = ? AND sequence = ?
                """,
                values + (request.sequence,),
            ).fetchone()
            if by_sequence is not None:
                existing = self._record(by_sequence)
                if not self._same(existing, request, stream, payload):
                    raise SnapshotRepositoryConflictError(
                        "snapshot sequence already has different immutable content"
                    )
                connection.execute("COMMIT")
                return SnapshotAppendResult(existing, inserted=False, duplicate=True)

            if decision.code is IngestionCode.DUPLICATE_IDEMPOTENT:
                raise SnapshotRepositoryRejectedError(
                    "idempotent decision has no matching stored snapshot"
                )
            latest = connection.execute(
                """
                SELECT sequence, captured_at FROM phase3_account_snapshots
                WHERE tenant_id = ? AND account_id = ? AND source_id = ?
                  AND source_version = ? AND source_simulated = ?
                  AND profile_config_hash = ? AND currency = ?
                ORDER BY sequence DESC LIMIT 1
                """,
                values,
            ).fetchone()
            if latest is not None:
                if request.sequence <= latest[0]:
                    raise SnapshotRepositoryOrderError("snapshot sequence is not increasing")
                latest_time = _parse_canonical_utc(latest[1], "latest_captured_at")
                if request.snapshot.captured_at <= latest_time:
                    raise SnapshotRepositoryOrderError("snapshot capture time is not increasing")

            self._ensure_scope(connection, request, stored_text)
            connection.execute(
                """
                INSERT INTO phase3_account_snapshots(
                    tenant_id, snapshot_id, account_id, source_id, source_version,
                    source_simulated, profile_config_hash, currency, sequence,
                    captured_at, received_at, stored_at, snapshot_hash, payload,
                    payload_sha256
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    stream.tenant_id, request.ingestion_id, stream.account_id,
                    stream.source_id, stream.source_version,
                    int(stream.source_simulated), stream.profile_config_hash,
                    stream.currency, request.sequence, captured_text, received_text,
                    stored_text, request.snapshot.content_hash, payload, storage_hash,
                ),
            )
            row = connection.execute(
                _SELECT + " WHERE tenant_id = ? AND snapshot_id = ?",
                (stream.tenant_id, request.ingestion_id),
            ).fetchone()
            record = self._record(row)
            connection.execute("COMMIT")
            return SnapshotAppendResult(record, inserted=True, duplicate=False)
        except BaseException:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise

    @staticmethod
    def _same(
        existing: StoredAccountSnapshot,
        request: SnapshotIngestionRequest,
        stream: SnapshotStreamIdentity,
        payload: bytes,
    ) -> bool:
        return (
            existing.stream == stream
            and existing.sequence == request.sequence
            and existing.received_at == request.received_at
            and existing.snapshot_hash == request.snapshot.content_hash
            and existing.storage_hash == hashlib.sha256(payload).hexdigest()
            and existing.snapshot == request.snapshot
        )

    @staticmethod
    def _ensure_scope(
        connection: sqlite3.Connection,
        request: SnapshotIngestionRequest,
        stored_text: str,
    ) -> None:
        tenant_id = request.tenant.tenant_id
        connection.execute(
            "INSERT OR IGNORE INTO phase3_tenants VALUES (?, ?)",
            (tenant_id, stored_text),
        )
        connection.execute(
            "INSERT OR IGNORE INTO phase3_accounts VALUES (?, ?, ?)",
            (tenant_id, request.account.account_id, stored_text),
        )
        profile_payload = _profile_account_size_payload(request.profile)
        connection.execute(
            """
            INSERT OR IGNORE INTO phase3_profiles(
                config_hash, firm_id, program_id, stage, profile_version,
                account_size_payload, first_recorded_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request.profile.config_hash, request.profile.firm_id,
                request.profile.program_id, request.profile.stage,
                request.profile.profile_version, profile_payload, stored_text,
            ),
        )
        saved = connection.execute(
            """
            SELECT firm_id, program_id, stage, profile_version, account_size_payload
            FROM phase3_profiles WHERE config_hash = ?
            """,
            (request.profile.config_hash,),
        ).fetchone()
        expected = (
            request.profile.firm_id, request.profile.program_id,
            request.profile.stage, request.profile.profile_version, profile_payload,
        )
        if saved != expected:
            raise SnapshotRepositoryConflictError("profile hash identity conflict")

    def by_id(
        self, *, tenant_id: str, snapshot_id: str
    ) -> StoredAccountSnapshot | None:
        row = self._connection().execute(
            _SELECT + " WHERE tenant_id = ? AND snapshot_id = ?",
            (tenant_id, snapshot_id),
        ).fetchone()
        return None if row is None else self._record(row)

    def latest(self, stream: SnapshotStreamIdentity) -> StoredAccountSnapshot | None:
        if not isinstance(stream, SnapshotStreamIdentity):
            raise ValueError("stream must be a SnapshotStreamIdentity")
        row = self._connection().execute(
            _SELECT + """
            WHERE tenant_id = ? AND account_id = ? AND source_id = ?
              AND source_version = ? AND source_simulated = ?
              AND profile_config_hash = ? AND currency = ?
            ORDER BY sequence DESC LIMIT 1
            """,
            _stream_values(stream),
        ).fetchone()
        return None if row is None else self._record(row)

    def history(
        self,
        stream: SnapshotStreamIdentity,
        *,
        after_sequence: int = 0,
        limit: int = 100,
    ) -> tuple[StoredAccountSnapshot, ...]:
        if not isinstance(stream, SnapshotStreamIdentity):
            raise ValueError("stream must be a SnapshotStreamIdentity")
        if type(after_sequence) is not int or after_sequence < 0:
            raise ValueError("after_sequence must be a nonnegative integer")
        rows = self._connection().execute(
            _SELECT + """
            WHERE tenant_id = ? AND account_id = ? AND source_id = ?
              AND source_version = ? AND source_simulated = ?
              AND profile_config_hash = ? AND currency = ? AND sequence > ?
            ORDER BY sequence ASC LIMIT ?
            """,
            _stream_values(stream) + (after_sequence, self._limit(limit)),
        ).fetchall()
        return tuple(self._record(row) for row in rows)

    def time_range(
        self,
        stream: SnapshotStreamIdentity,
        *,
        start: datetime,
        end: datetime,
        limit: int = 1000,
    ) -> tuple[StoredAccountSnapshot, ...]:
        if not isinstance(stream, SnapshotStreamIdentity):
            raise ValueError("stream must be a SnapshotStreamIdentity")
        start_text = _canonical_utc(start, "start")
        end_text = _canonical_utc(end, "end")
        if start.astimezone(timezone.utc) >= end.astimezone(timezone.utc):
            raise ValueError("time range start must precede end")
        rows = self._connection().execute(
            _SELECT + """
            WHERE tenant_id = ? AND account_id = ? AND source_id = ?
              AND source_version = ? AND source_simulated = ?
              AND profile_config_hash = ? AND currency = ?
              AND captured_at >= ? AND captured_at < ?
            ORDER BY captured_at ASC, sequence ASC LIMIT ?
            """,
            _stream_values(stream) + (start_text, end_text, self._limit(limit)),
        ).fetchall()
        return tuple(self._record(row) for row in rows)
