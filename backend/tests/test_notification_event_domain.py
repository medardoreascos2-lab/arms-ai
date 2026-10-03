"""Immutable notification event domain tests."""

from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D

import pytest

from backend.notifications import (
    DEFAULT_SEVERITY,
    NotificationEvent,
    NotificationEventType,
    NotificationIdentity,
    NotificationSeverity,
    RedactionPolicy,
    create_notification_event,
    safe_payload,
)


NOW = datetime(2026, 10, 4, 15, 0, tzinfo=timezone.utc)


def identity() -> NotificationIdentity:
    return NotificationIdentity(
        account_id="account-1",
        firm_id="topstep",
        program_id="trading_combine",
        profile_version="2026-10-03/no-dll",
    )


def test_all_required_event_types_have_default_severity_and_safe_identity():
    assert set(NotificationEventType) == {
        NotificationEventType.SIGNAL_CANDIDATE,
        NotificationEventType.SIGNAL_REJECTED,
        NotificationEventType.PAPER_TRADE_OPENED,
        NotificationEventType.PAPER_TRADE_CLOSED,
        NotificationEventType.RISK_BLOCK,
        NotificationEventType.DRAWDOWN_WARNING,
        NotificationEventType.DAILY_LIMIT_BLOCK,
        NotificationEventType.ACCOUNT_FAILED,
        NotificationEventType.PAYOUT_ELIGIBLE,
        NotificationEventType.SYSTEM_FAULT,
        NotificationEventType.DATA_FAULT,
    }
    events = tuple(
        create_notification_event(
            event_type,
            f"cause-{event_type.value}",
            NOW,
            identity=identity(),
            payload={"reason": event_type.value},
        )
        for event_type in NotificationEventType
    )
    assert all(event.severity == DEFAULT_SEVERITY[event.event_type] for event in events)
    assert all(len(event.dedupe_identity) == 64 for event in events)
    assert all(len(event.event_id) == 64 for event in events)
    assert len({event.event_id for event in events}) == len(NotificationEventType)
    with pytest.raises(TypeError):
        DEFAULT_SEVERITY[NotificationEventType.DATA_FAULT] = NotificationSeverity.INFO


def test_dedupe_identity_excludes_timestamp_and_payload_but_event_id_does_not():
    first = create_notification_event(
        NotificationEventType.RISK_BLOCK,
        "risk-check-1",
        NOW,
        identity=identity(),
        payload={"remaining": D("100")},
    )
    replay = create_notification_event(
        NotificationEventType.RISK_BLOCK,
        "risk-check-1",
        NOW + timedelta(seconds=1),
        identity=identity(),
        payload={"remaining": D("90")},
    )
    distinct = create_notification_event(
        NotificationEventType.RISK_BLOCK,
        "risk-check-2",
        NOW,
        identity=identity(),
    )
    assert first.dedupe_identity == replay.dedupe_identity
    assert first.event_id != replay.event_id
    assert first.dedupe_identity != distinct.dedupe_identity


def test_sensitive_keys_and_embedded_credentials_are_redacted_deterministically():
    event = create_notification_event(
        NotificationEventType.SYSTEM_FAULT,
        "fault-1",
        NOW,
        payload={
            "message": "upstream failed with token=abc123 and Bearer xyz789",
            "api_key": "plain-secret",
            "attempt": 2,
            "retryable": True,
            "price": D("20123.25"),
            "optional": None,
        },
    )
    payload = dict(event.payload)
    assert payload["api_key"] == "[REDACTED]"
    assert "abc123" not in payload["message"]
    assert "xyz789" not in payload["message"]
    assert payload["message"].count("[REDACTED]") == 2
    assert payload["price"] == D("20123.25")
    assert tuple(key for key, _ in event.payload) == tuple(sorted(payload))


def test_reject_sensitive_policy_fails_closed():
    with pytest.raises(ValueError, match="sensitive"):
        create_notification_event(
            NotificationEventType.DATA_FAULT,
            "data-1",
            NOW,
            payload={"authorization": "Bearer abc"},
            redaction_policy=RedactionPolicy.REJECT_SENSITIVE,
        )
    with pytest.raises(ValueError, match="sensitive"):
        safe_payload(
            {"message": "password=hunter2"},
            RedactionPolicy.REJECT_SENSITIVE,
        )


@pytest.mark.parametrize("payload", [
    {"price": 1.25},
    {"items": [1, 2]},
    {"nested": {"value": 1}},
    {"binary": b"secret"},
    {"nonfinite": D("NaN")},
])
def test_unsupported_or_lossy_payload_values_are_rejected(payload):
    with pytest.raises(ValueError):
        create_notification_event(
            NotificationEventType.DATA_FAULT,
            "data-1",
            NOW,
            payload=payload,
        )


def test_profile_identity_is_all_or_none_and_system_fault_may_be_global():
    with pytest.raises(ValueError, match="profile identity"):
        NotificationIdentity(firm_id="topstep", program_id="combine")
    global_event = create_notification_event(
        NotificationEventType.SYSTEM_FAULT,
        "system-1",
        NOW,
    )
    assert global_event.identity == NotificationIdentity()


def test_timestamp_types_and_direct_unsafe_construction_are_rejected():
    with pytest.raises(ValueError, match="timezone-aware"):
        create_notification_event(
            NotificationEventType.DATA_FAULT,
            "data-1",
            datetime(2026, 10, 4, 15, 0),
        )
    with pytest.raises(ValueError, match="safely redacted"):
        NotificationEvent(
            NotificationEventType.SYSTEM_FAULT,
            NotificationSeverity.CRITICAL,
            "fault-1",
            NOW,
            NotificationIdentity(),
            (("token", "unsafe"),),
            RedactionPolicy.REDACT_SENSITIVE,
        )


def test_event_and_payload_are_immutable_and_source_mapping_is_not_retained():
    source = {"reason": "LIMIT", "remaining": D("50")}
    event = create_notification_event(
        NotificationEventType.DAILY_LIMIT_BLOCK,
        "daily-1",
        NOW,
        identity=identity(),
        payload=source,
    )
    source["reason"] = "MUTATED"
    assert dict(event.payload)["reason"] == "LIMIT"
    with pytest.raises(FrozenInstanceError):
        event.severity = NotificationSeverity.INFO
    with pytest.raises(TypeError):
        event.payload[0] = ("reason", "MUTATED")
