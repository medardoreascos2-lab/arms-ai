"""Canonical, exact serialization for Phase 3 durable state records."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import hmac
import json
import re
from typing import NoReturn

from .state_contracts import (
    AccountIdentity,
    DecimalUnit,
    DurableDecimal,
    DurableStateKind,
    DurableStatePayload,
    DurableStateRecord,
    DurableValue,
    PropFirmProfileIdentity,
    SchemaIdentity,
    SourceIdentity,
    TenantIdentity,
    UserIdentity,
)


SERIALIZATION_FORMAT = "arms.phase3.durable-state-json.v1"
MAX_SERIALIZED_BYTES = 1_048_576
MAX_DECIMAL_CHARACTERS = 4096
_HASH = re.compile(r"^[0-9a-f]{64}$")


def canonical_decimal_text(value: Decimal) -> str:
    """Return a non-exponential, scale-independent exact decimal string."""
    if not isinstance(value, Decimal) or not value.is_finite():
        raise ValueError("value must be a finite Decimal")
    if value == 0:
        return "0"

    _, digits, exponent = value.as_tuple()
    integer_characters = max(len(digits) + exponent, 1)
    fractional_characters = max(-exponent, 0)
    if integer_characters + fractional_characters > MAX_DECIMAL_CHARACTERS:
        raise ValueError("decimal canonical representation exceeds size limit")

    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def _canonical_timestamp(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def _encode_decimal(value: DurableDecimal) -> dict[str, object]:
    return {
        "$type": "decimal",
        "currency": value.currency,
        "unit": value.unit.value,
        "value": canonical_decimal_text(value.value),
    }


def _encode_value(value: DurableValue) -> object:
    if value is None or type(value) in (bool, int) or isinstance(value, str):
        return value
    if isinstance(value, DurableDecimal):
        return _encode_decimal(value)
    if isinstance(value, datetime):
        return {"$type": "timestamp", "value": _canonical_timestamp(value)}
    if isinstance(value, tuple):
        return [_encode_value(item) for item in value]
    raise ValueError("unsupported durable value")


def _identity(value: object | None, fields: tuple[str, ...]) -> object:
    if value is None:
        return None
    return {field: getattr(value, field) for field in fields}


def _record_document(record: DurableStateRecord) -> dict[str, object]:
    if not isinstance(record, DurableStateRecord):
        raise ValueError("record must be a DurableStateRecord")
    profile = None
    if record.profile is not None:
        profile = {
            "account_size": _encode_decimal(record.profile.account_size),
            "config_hash": record.profile.config_hash,
            "firm_id": record.profile.firm_id,
            "profile_version": record.profile.profile_version,
            "program_id": record.profile.program_id,
            "stage": record.profile.stage,
        }
    return {
        "account": _identity(record.account, ("account_id", "tenant_id")),
        "authority": {
            "canonical_admin_authorized": False,
            "execution_authorized": False,
            "production_mutation_authorized": False,
        },
        "format": SERIALIZATION_FORMAT,
        "kind": record.kind.value,
        "observed_at": _canonical_timestamp(record.observed_at),
        "payload": [
            {"name": name, "value": _encode_value(value)}
            for name, value in record.payload.entries
        ],
        "profile": profile,
        "record_id": record.record_id,
        "schema": {
            "name": record.schema.name,
            "namespace": record.schema.namespace,
            "version": record.schema.version,
        },
        "source": {
            "simulated": record.source.simulated,
            "source_id": record.source.source_id,
            "source_version": record.source.source_version,
        },
        "tenant": {"tenant_id": record.tenant.tenant_id},
        "user": _identity(record.user, ("tenant_id", "user_id")),
    }


def serialize_state_record(record: DurableStateRecord) -> bytes:
    """Serialize a record to deterministic UTF-8 JSON bytes."""
    try:
        encoded = json.dumps(
            _record_document(record),
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError("record contains text that is not valid UTF-8") from exc
    if len(encoded) > MAX_SERIALIZED_BYTES:
        raise ValueError("serialized record exceeds size limit")
    return encoded


def state_record_hash(record: DurableStateRecord) -> str:
    return hashlib.sha256(serialize_state_record(record)).hexdigest()


def verify_serialized_hash(payload: bytes | str, expected_hash: str) -> bool:
    if not isinstance(expected_hash, str) or _HASH.fullmatch(expected_hash) is None:
        return False
    if isinstance(payload, str):
        try:
            encoded = payload.encode("utf-8")
        except UnicodeEncodeError:
            return False
    else:
        encoded = payload
    if not isinstance(encoded, bytes) or len(encoded) > MAX_SERIALIZED_BYTES:
        return False
    return hmac.compare_digest(hashlib.sha256(encoded).hexdigest(), expected_hash)


def _reject_float(_: str) -> NoReturn:
    raise ValueError("JSON floating-point numbers are forbidden")


def _reject_constant(_: str) -> NoReturn:
    raise ValueError("non-finite JSON numbers are forbidden")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON field is forbidden: {key}")
        value[key] = item
    return value


def _object(value: object, keys: frozenset[str], name: str) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError(f"{name} must contain exactly the required fields")
    if not all(isinstance(key, str) for key in value):
        raise ValueError(f"{name} keys must be strings")
    return value


def _string(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    return value


def _timestamp(value: object, name: str) -> datetime:
    text = _string(value, name)
    if not text.endswith("Z"):
        raise ValueError(f"{name} must be canonical UTC")
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError(f"{name} must be a valid timestamp") from exc
    if _canonical_timestamp(parsed) != text:
        raise ValueError(f"{name} must be canonical UTC")
    return parsed


def _decode_decimal(value: object, name: str) -> DurableDecimal:
    item = _object(
        value,
        frozenset({"$type", "currency", "unit", "value"}),
        name,
    )
    if item["$type"] != "decimal":
        raise ValueError(f"{name} has an invalid type marker")
    text = _string(item["value"], f"{name}.value")
    try:
        number = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"{name}.value must be a decimal") from exc
    if canonical_decimal_text(number) != text:
        raise ValueError(f"{name}.value must use canonical decimal text")
    try:
        unit = DecimalUnit(_string(item["unit"], f"{name}.unit"))
    except ValueError as exc:
        raise ValueError(f"{name}.unit is invalid") from exc
    currency = item["currency"]
    if currency is not None and not isinstance(currency, str):
        raise ValueError(f"{name}.currency must be a string or null")
    return DurableDecimal(number, unit, currency)


def _decode_value(value: object, name: str) -> DurableValue:
    if value is None or type(value) in (bool, int) or isinstance(value, str):
        return value
    if isinstance(value, list):
        return tuple(_decode_value(item, name) for item in value)
    if isinstance(value, dict):
        marker = value.get("$type")
        if marker == "decimal":
            return _decode_decimal(value, name)
        if marker == "timestamp":
            item = _object(value, frozenset({"$type", "value"}), name)
            return _timestamp(item["value"], f"{name}.value")
    raise ValueError(f"{name} contains an unsupported durable value")


def _optional_identity(
    value: object,
    keys: frozenset[str],
    name: str,
) -> dict[str, object] | None:
    if value is None:
        return None
    return _object(value, keys, name)


def deserialize_state_record(payload: bytes | str) -> DurableStateRecord:
    """Strictly decode canonical Phase 3 state JSON without numeric coercion."""
    if isinstance(payload, str):
        try:
            encoded = payload.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise ValueError("payload must be valid UTF-8") from exc
        text = payload
    elif isinstance(payload, bytes):
        encoded = payload
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("payload must be valid UTF-8") from exc
    else:
        raise ValueError("payload must be bytes or string")
    if len(encoded) > MAX_SERIALIZED_BYTES:
        raise ValueError("serialized record exceeds size limit")

    try:
        raw = json.loads(
            text,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
            object_pairs_hook=_unique_object,
        )
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise ValueError("payload must be valid JSON") from exc

    document = _object(
        raw,
        frozenset({
            "account", "authority", "format", "kind", "observed_at",
            "payload", "profile", "record_id", "schema", "source",
            "tenant", "user",
        }),
        "record",
    )
    if document["format"] != SERIALIZATION_FORMAT:
        raise ValueError("unsupported serialization format")

    authority = _object(
        document["authority"],
        frozenset({
            "canonical_admin_authorized", "execution_authorized",
            "production_mutation_authorized",
        }),
        "authority",
    )
    if any(value is not False for value in authority.values()):
        raise ValueError("durable state cannot carry operational authority")

    schema_data = _object(
        document["schema"],
        frozenset({"name", "namespace", "version"}),
        "schema",
    )
    source_data = _object(
        document["source"],
        frozenset({"simulated", "source_id", "source_version"}),
        "source",
    )
    tenant_data = _object(
        document["tenant"], frozenset({"tenant_id"}), "tenant"
    )
    account_data = _optional_identity(
        document["account"], frozenset({"account_id", "tenant_id"}), "account"
    )
    user_data = _optional_identity(
        document["user"], frozenset({"tenant_id", "user_id"}), "user"
    )

    profile = None
    if document["profile"] is not None:
        profile_data = _object(
            document["profile"],
            frozenset({
                "account_size", "config_hash", "firm_id", "profile_version",
                "program_id", "stage",
            }),
            "profile",
        )
        profile = PropFirmProfileIdentity(
            firm_id=_string(profile_data["firm_id"], "profile.firm_id"),
            program_id=_string(profile_data["program_id"], "profile.program_id"),
            stage=_string(profile_data["stage"], "profile.stage"),
            account_size=_decode_decimal(profile_data["account_size"], "profile.account_size"),
            profile_version=_string(
                profile_data["profile_version"], "profile.profile_version"
            ),
            config_hash=_string(profile_data["config_hash"], "profile.config_hash"),
        )

    raw_entries = document["payload"]
    if not isinstance(raw_entries, list):
        raise ValueError("payload must be a list")
    entries: list[tuple[str, DurableValue]] = []
    for index, raw_entry in enumerate(raw_entries):
        entry = _object(
            raw_entry, frozenset({"name", "value"}), f"payload[{index}]"
        )
        field_name = _string(entry["name"], f"payload[{index}].name")
        entries.append((field_name, _decode_value(entry["value"], field_name)))

    try:
        kind = DurableStateKind(_string(document["kind"], "kind"))
    except ValueError as exc:
        raise ValueError("kind is invalid") from exc

    version = schema_data["version"]
    if type(version) is not int:
        raise ValueError("schema.version must be an integer")
    simulated = source_data["simulated"]
    if type(simulated) is not bool:
        raise ValueError("source.simulated must be a boolean")

    tenant_id = _string(tenant_data["tenant_id"], "tenant.tenant_id")
    return DurableStateRecord(
        record_id=_string(document["record_id"], "record_id"),
        schema=SchemaIdentity(
            namespace=_string(schema_data["namespace"], "schema.namespace"),
            name=_string(schema_data["name"], "schema.name"),
            version=version,
        ),
        kind=kind,
        observed_at=_timestamp(document["observed_at"], "observed_at"),
        tenant=TenantIdentity(tenant_id),
        source=SourceIdentity(
            source_id=_string(source_data["source_id"], "source.source_id"),
            source_version=_string(
                source_data["source_version"], "source.source_version"
            ),
            simulated=simulated,
        ),
        payload=DurableStatePayload(tuple(entries)),
        user=(
            UserIdentity(
                _string(user_data["tenant_id"], "user.tenant_id"),
                _string(user_data["user_id"], "user.user_id"),
            )
            if user_data is not None else None
        ),
        account=(
            AccountIdentity(
                _string(account_data["tenant_id"], "account.tenant_id"),
                _string(account_data["account_id"], "account.account_id"),
            )
            if account_data is not None else None
        ),
        profile=profile,
    )
