"""R41B regression tests for centralized operational secret redaction."""

from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from backend.phase4.secret_redaction import (
    REDACTED,
    REDACTED_BINARY,
    REDACTED_CYCLE,
    REDACTED_UNSUPPORTED,
    RedactedRecord,
    RedactionChannel,
    SecretRedactor,
    redact_mapping,
    redact_text,
    sensitive_key,
)


SECRET_FIXTURES = (
    "fixture-token-41b",
    "fixture-password-41b",
    "fixture-secret-41b",
    "fixture-api-key-41b",
    "fixture-auth-41b",
    "fixture-cookie-41b",
    "fixture-webhook-41b",
)


def _assert_no_fixture_leaked(value):
    rendered = repr(value)
    for fixture in SECRET_FIXTURES:
        assert fixture not in rendered


def test_all_required_sensitive_key_variants_are_detected():
    for key in (
        "token",
        "password",
        "secret_value",
        "api-key",
        "Authorization",
        "session_cookie",
        "webhook_url",
        "clientSecret",
        "private_key",
        "credential",
    ):
        assert sensitive_key(key) is True
    assert sensitive_key("retry_count") is False


def test_mapping_redacts_sensitive_keys_recursively_and_preserves_safe_scalars():
    payload = {
        "token": SECRET_FIXTURES[0],
        "nested": {
            "password": SECRET_FIXTURES[1],
            "attempt": 2,
            "price": Decimal("20123.25"),
        },
        "binary": b"opaque-secret-bytes",
        "items": [True, None, "safe"],
        "object": object(),
    }
    redacted = dict(redact_mapping(payload))
    assert redacted["token"] == REDACTED
    assert dict(redacted["nested"])["password"] == REDACTED
    assert dict(redacted["nested"])["attempt"] == 2
    assert redacted["binary"] == REDACTED_BINARY
    assert redacted["items"] == (True, None, "safe")
    assert redacted["object"] == REDACTED_UNSUPPORTED
    _assert_no_fixture_leaked(redacted)


def test_text_redaction_handles_assignments_auth_schemes_uri_credentials_and_jwt():
    jwt = "eyJabcde.abcdefgh.ijklmnop"
    message = (
        f"token={SECRET_FIXTURES[0]} password: {SECRET_FIXTURES[1]} "
        f"api_key='{SECRET_FIXTURES[3]}' Authorization=Bearer-{SECRET_FIXTURES[4]} "
        f"Cookie:{SECRET_FIXTURES[5]} webhook={SECRET_FIXTURES[6]} "
        f"Bearer {SECRET_FIXTURES[4]} postgresql://user:{SECRET_FIXTURES[1]}@host/db "
        f"jwt={jwt}"
    )
    safe = redact_text(message)
    _assert_no_fixture_leaked(safe)
    assert jwt not in safe
    assert "user:" not in safe
    assert safe.count(REDACTED) >= 8


def test_every_required_output_channel_removes_sensitive_fixtures():
    redactor = SecretRedactor()
    fields = {
        "api_key": SECRET_FIXTURES[3],
        "context": f"cookie={SECRET_FIXTURES[5]}",
    }
    records = (
        redactor.log(f"token={SECRET_FIXTURES[0]}", fields),
        redactor.audit({"password": SECRET_FIXTURES[1]}),
        redactor.exception(RuntimeError(f"secret={SECRET_FIXTURES[2]}")),
        redactor.notification({"webhook": SECRET_FIXTURES[6]}),
        redactor.api_error(503, f"authorization={SECRET_FIXTURES[4]}", fields),
        redactor.worker_failure(
            "outbox_worker",
            RuntimeError(f"token={SECRET_FIXTURES[0]}"),
            fields,
        ),
    )
    assert {record.channel for record in records} == set(RedactionChannel)
    for record in records:
        _assert_no_fixture_leaked(record)
        assert record.execution_authorized is False
        assert record.production_mutation_authorized is False


def test_exception_objects_are_not_retained_and_direct_unsafe_records_are_rejected():
    error = RuntimeError(f"password={SECRET_FIXTURES[1]}")
    record = SecretRedactor().exception(error)
    assert record.error_type == "RuntimeError"
    assert not any(value is error for _, value in record.fields)
    _assert_no_fixture_leaked(record)
    with pytest.raises(ValueError, match="safely redacted"):
        RedactedRecord(
            channel=RedactionChannel.LOG,
            message=f"token={SECRET_FIXTURES[0]}",
        )
    with pytest.raises(ValueError, match="safely redacted"):
        RedactedRecord(
            channel=RedactionChannel.LOG,
            message="safe",
            fields=(("nested", (("token", SECRET_FIXTURES[0]),)),),
        )


def test_cycles_and_oversized_collections_are_bounded_without_repr_leakage():
    cyclic = {}
    cyclic["self"] = cyclic
    redacted = dict(redact_mapping({"cycle": cyclic, "many": list(range(100))}))
    assert dict(redacted["cycle"])["self"] == REDACTED_CYCLE
    assert len(redacted["many"]) == 65
    assert redacted["many"][-1] == REDACTED_UNSUPPORTED


def test_redacted_records_are_immutable_sorted_and_source_independent():
    source = {"z": "safe", "token": SECRET_FIXTURES[0], "a": 1}
    record = SecretRedactor().log("ready", source)
    source["z"] = SECRET_FIXTURES[1]
    assert tuple(key for key, _ in record.fields) == ("a", "token", "z")
    assert dict(record.fields)["z"] == "safe"
    with pytest.raises(FrozenInstanceError):
        record.message = "changed"


def test_api_and_worker_validation_fail_before_record_creation():
    redactor = SecretRedactor()
    with pytest.raises(ValueError, match="status_code"):
        redactor.api_error(200, "not an error")
    with pytest.raises(ValueError, match="worker_id"):
        redactor.worker_failure("bad worker id", RuntimeError("failed"))
