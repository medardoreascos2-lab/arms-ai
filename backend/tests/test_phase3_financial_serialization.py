"""R32B tests for exact deterministic financial serialization."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
import hashlib
import json

import pytest

from backend.phase3 import (
    AccountIdentity,
    DecimalUnit,
    DurableDecimal,
    DurableStateKind,
    DurableStatePayload,
    DurableStateRecord,
    PropFirmProfileIdentity,
    SchemaIdentity,
    SourceIdentity,
    TenantIdentity,
    canonical_decimal_text,
    deserialize_state_record,
    serialize_state_record,
    state_record_hash,
    verify_serialized_hash,
)


NOW = datetime(2026, 10, 3, 14, 30, 1, 25, tzinfo=timezone.utc)


def state(**changes):
    values = dict(
        record_id="snapshot-1",
        schema=SchemaIdentity("arms.phase3", "account_snapshot", 1),
        kind=DurableStateKind.ACCOUNT_SNAPSHOT,
        observed_at=NOW,
        tenant=TenantIdentity("tenant-a"),
        source=SourceIdentity("runtime://paper/account-1", "snapshot-v1", True),
        payload=DurableStatePayload((
            ("balance", DurableDecimal(D("52341.0700"), DecimalUnit.CURRENCY, "USD")),
            ("blocking_reasons", ("daily_loss_near_limit", "spread_near_limit")),
            ("drawdown_ratio", DurableDecimal(D("0.040000"), DecimalUnit.RATIO)),
            ("payout_value", DurableDecimal(D("-125.50"), DecimalUnit.CURRENCY, "USD")),
            ("session_ends_at", NOW + timedelta(hours=2)),
            ("zero_risk", DurableDecimal(D("0.0000"), DecimalUnit.PERCENT)),
        )),
        account=AccountIdentity("tenant-a", "account-1"),
        profile=PropFirmProfileIdentity(
            "lucid", "lucidpro_funded_no_dll", "funded",
            DurableDecimal(D("50000.00"), DecimalUnit.CURRENCY, "USD"),
            "2026-10-03", "a" * 64,
        ),
    )
    values.update(changes)
    return DurableStateRecord(**values)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (D("0"), "0"),
        (D("-0.000"), "0"),
        (D("0.00000000000000000001"), "0.00000000000000000001"),
        (D("999999999999999999999999.999999"), "999999999999999999999999.999999"),
        (D("-125.5000"), "-125.5"),
        (D("1.23456789012345678901234567890"), "1.2345678901234567890123456789"),
        (D("1E+12"), "1000000000000"),
    ],
)
def test_decimal_text_is_exact_non_exponential_and_canonical(value, expected):
    assert canonical_decimal_text(value) == expected


@pytest.mark.parametrize("value", [1.2, D("NaN"), D("Infinity"), D("1E+5000")])
def test_decimal_text_rejects_inexact_nonfinite_or_oversized_values(value):
    with pytest.raises(ValueError):
        canonical_decimal_text(value)


def test_state_round_trip_preserves_values_identity_scope_and_no_authority():
    original = state()
    encoded = serialize_state_record(original)
    restored = deserialize_state_record(encoded)
    assert restored == original
    assert restored.execution_authorized is False
    assert restored.production_mutation_authorized is False
    assert restored.canonical_admin_authorized is False


def test_json_is_deterministic_and_financial_values_are_explicit_strings():
    encoded = serialize_state_record(state())
    assert encoded == serialize_state_record(state())
    document = json.loads(encoded)
    assert document["profile"]["account_size"] == {
        "$type": "decimal", "currency": "USD", "unit": "currency", "value": "50000"
    }
    balance = next(
        item["value"] for item in document["payload"] if item["name"] == "balance"
    )
    assert balance == {
        "$type": "decimal", "currency": "USD", "unit": "currency", "value": "52341.07"
    }
    assert b"52341.07" in encoded
    assert b"52341.0700" not in encoded


def test_equivalent_decimal_scales_produce_identical_bytes_and_hashes():
    first = state()
    second_payload = DurableStatePayload(tuple(
        (name, DurableDecimal(D("52341.07"), DecimalUnit.CURRENCY, "USD"))
        if name == "balance" else (name, value)
        for name, value in first.payload.entries
    ))
    second = replace(first, payload=second_payload)
    assert serialize_state_record(first) == serialize_state_record(second)
    assert state_record_hash(first) == state_record_hash(second)


def test_equivalent_timestamp_offsets_produce_identical_bytes():
    eastern = timezone(timedelta(hours=-4))
    shifted = replace(state(), observed_at=NOW.astimezone(eastern))
    assert serialize_state_record(state()) == serialize_state_record(shifted)


def test_hash_is_stable_verifiable_and_changes_with_state():
    original = state()
    encoded = serialize_state_record(original)
    digest = state_record_hash(original)
    assert digest == hashlib.sha256(encoded).hexdigest()
    assert verify_serialized_hash(encoded, digest) is True
    assert verify_serialized_hash(encoded.decode("utf-8"), digest) is True
    changed = replace(original, record_id="snapshot-2")
    assert state_record_hash(changed) != digest
    assert verify_serialized_hash(encoded, "not-a-hash") is False


def test_decoder_rejects_float_tokens_unknown_fields_and_authority_escalation():
    encoded = serialize_state_record(state()).decode("utf-8")
    with pytest.raises(ValueError, match="floating-point"):
        deserialize_state_record(encoded.replace('"record_id":"snapshot-1"', '"extra":1.5,"record_id":"snapshot-1"'))

    document = json.loads(encoded)
    document["unknown"] = "field"
    with pytest.raises(ValueError, match="exactly"):
        deserialize_state_record(json.dumps(document))

    document.pop("unknown")
    document["authority"]["execution_authorized"] = True
    with pytest.raises(ValueError, match="authority"):
        deserialize_state_record(json.dumps(document))


def test_decoder_rejects_duplicate_json_fields():
    encoded = serialize_state_record(state()).decode("utf-8")
    duplicated = encoded.replace(
        '"record_id":"snapshot-1"',
        '"record_id":"snapshot-1","record_id":"snapshot-2"',
    )
    with pytest.raises(ValueError, match="duplicate JSON field"):
        deserialize_state_record(duplicated)


def test_serializer_rejects_text_that_cannot_be_encoded_as_utf8():
    original = state()
    bad_payload = DurableStatePayload(tuple(
        (name, "\ud800") if name == "blocking_reasons" else (name, value)
        for name, value in original.payload.entries
    ))
    with pytest.raises(ValueError, match="valid UTF-8"):
        serialize_state_record(replace(original, payload=bad_payload))


@pytest.mark.parametrize(
    "mutate",
    [
        lambda document: document.update({"format": "unknown.v1"}),
        lambda document: document["schema"].pop("version"),
        lambda document: document["payload"][0]["value"].update({"value": "52341.070"}),
        lambda document: document.update({"observed_at": "2026-10-03T14:30:01+00:00"}),
    ],
)
def test_decoder_rejects_noncanonical_or_incomplete_documents(mutate):
    document = json.loads(serialize_state_record(state()))
    mutate(document)
    with pytest.raises(ValueError):
        deserialize_state_record(json.dumps(document))


def test_decoder_rejects_nonfinite_json_constants_and_invalid_utf8():
    encoded = serialize_state_record(state()).decode("utf-8")
    with pytest.raises(ValueError, match="non-finite"):
        deserialize_state_record(encoded.replace('"record_id":"snapshot-1"', '"bad":NaN,"record_id":"snapshot-1"'))
    with pytest.raises(ValueError, match="UTF-8"):
        deserialize_state_record(b"\xff")
    with pytest.raises(ValueError, match="UTF-8"):
        deserialize_state_record("\ud800")
    assert verify_serialized_hash("\ud800", "0" * 64) is False


def test_serialization_module_performs_no_io_or_execution_imports():
    from pathlib import Path
    from backend.phase3 import financial_serialization

    source = Path(financial_serialization.__file__).read_text(encoding="utf-8")
    forbidden = ("sqlite3", "sqlalchemy", "backend.execution", "requests", "subprocess")
    assert all(token not in source for token in forbidden)
