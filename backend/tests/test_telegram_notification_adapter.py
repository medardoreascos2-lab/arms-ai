"""Telegram notification adapter architecture tests."""

from dataclasses import FrozenInstanceError, fields
from datetime import datetime, timezone
from decimal import Decimal as D

import pytest

from backend.notifications import (
    DispatchStatus,
    FakeTelegramTransport,
    InMemoryNotificationDedupeStore,
    NotificationDispatcher,
    NotificationEventType,
    NotificationIdentity,
    ProviderAttemptResult,
    ProviderAttemptStatus,
    RedactionPolicy,
    RetryPolicy,
    TelegramConfiguration,
    TelegramEventFormatter,
    TelegramMessage,
    TelegramMode,
    TelegramNotificationProvider,
    build_telegram_provider,
    create_notification_event,
)


NOW = datetime(2026, 10, 4, 17, 0, tzinfo=timezone.utc)


class AllowAll:
    def allow(self, provider, event, attempt_number, now):
        return True


class RecordingWaiter:
    def __init__(self):
        self.delays = []

    def wait(self, delay_seconds):
        self.delays.append(delay_seconds)


class ExplodingDependency:
    def __getattr__(self, name):
        raise AssertionError(f"disabled Telegram touched {name}")


def notification(payload=None):
    return create_notification_event(
        NotificationEventType.DRAWDOWN_WARNING,
        "drawdown-warning-1",
        NOW,
        identity=NotificationIdentity(
            account_id="account-1",
            firm_id="topstep",
            program_id="combine",
            profile_version="2026-10-03/no-dll",
        ),
        payload=payload or {"remaining": D("750.25")},
    )


def dispatch(provider, *, retry=None, waiter=None):
    return NotificationDispatcher(
        provider,
        InMemoryNotificationDedupeStore(),
        AllowAll(),
        retry,
        waiter,
        clock=lambda: NOW,
    )


def test_disabled_mode_builds_global_disabled_provider_without_touching_transport():
    provider = build_telegram_provider(
        TelegramConfiguration(),
        transport=ExplodingDependency(),
        formatter=ExplodingDependency(),
    )
    result = NotificationDispatcher(
        provider,
        ExplodingDependency(),
        ExplodingDependency(),
    ).dispatch(notification())
    assert result.status == DispatchStatus.DISABLED
    assert result.execution_authorized is False


def test_configuration_has_no_credential_or_live_mode_and_is_immutable():
    names = {item.name for item in fields(TelegramConfiguration)}
    assert names == {"mode", "channel_alias", "maximum_message_characters"}
    assert set(TelegramMode) == {TelegramMode.DISABLED, TelegramMode.TEST}
    configuration = TelegramConfiguration(TelegramMode.TEST, "risk_alerts")
    with pytest.raises(FrozenInstanceError):
        configuration.channel_alias = "changed"


@pytest.mark.parametrize("alias", [None, "", "has spaces", "@real-chat", "a" * 65])
def test_test_mode_requires_a_safe_logical_channel_alias(alias):
    with pytest.raises(ValueError, match="channel alias"):
        TelegramConfiguration(TelegramMode.TEST, alias)


def test_disabled_mode_rejects_channel_configuration():
    with pytest.raises(ValueError, match="cannot select"):
        TelegramConfiguration(TelegramMode.DISABLED, "risk_alerts")


def test_test_mode_requires_explicit_transport():
    configuration = TelegramConfiguration(TelegramMode.TEST, "risk_alerts")
    with pytest.raises(ValueError, match="explicit transport"):
        build_telegram_provider(configuration)
    with pytest.raises(ValueError, match="transport is invalid"):
        TelegramNotificationProvider(configuration, None)


def test_custom_formatter_cannot_exceed_configuration_limit():
    configuration = TelegramConfiguration(TelegramMode.TEST, "risk_alerts", 256)
    with pytest.raises(ValueError, match="exceeds"):
        TelegramNotificationProvider(
            configuration,
            FakeTelegramTransport(),
            TelegramEventFormatter(257),
        )


def test_formatter_is_deterministic_plain_text_and_escapes_control_characters():
    event = notification({"note": "line one\nline two", "remaining": D("750.25")})
    formatter = TelegramEventFormatter()
    first = formatter.format(event, "risk_alerts")
    second = formatter.format(event, "risk_alerts")
    assert first == second
    assert first.text.startswith("ARMS AI notification\ntype=DRAWDOWN_WARNING")
    assert "account_id=\"account-1\"" in first.text
    assert "payload.remaining=750.25" in first.text
    assert "line one\\nline two" in first.text
    assert "line one\nline two" not in first.text


def test_redaction_is_preserved_before_fake_transport_receives_message():
    event = notification({
        "api_key": "unsafe-key",
        "message": "Bearer unsafe-token",
    })
    transport = FakeTelegramTransport()
    provider = build_telegram_provider(
        TelegramConfiguration(TelegramMode.TEST, "risk_alerts"),
        transport=transport,
    )
    result = dispatch(provider).dispatch(event)
    assert result.status == DispatchStatus.DELIVERED
    assert len(transport.messages) == 1
    assert "unsafe-key" not in transport.messages[0].text
    assert "unsafe-token" not in transport.messages[0].text
    assert transport.messages[0].text.count("[REDACTED]") == 2


def test_strict_redaction_rejects_before_transport_or_provider_construction():
    transport = FakeTelegramTransport()
    with pytest.raises(ValueError, match="sensitive"):
        create_notification_event(
            NotificationEventType.DATA_FAULT,
            "data-fault-1",
            NOW,
            payload={"token": "unsafe"},
            redaction_policy=RedactionPolicy.REJECT_SENSITIVE,
        )
    assert transport.messages == []


def test_fake_transport_integrates_with_dispatch_retry_seam():
    transport = FakeTelegramTransport((
        ProviderAttemptResult(
            ProviderAttemptStatus.RETRYABLE_FAILURE,
            "TELEGRAM_TEMPORARY_FAILURE",
        ),
        ProviderAttemptResult(ProviderAttemptStatus.DELIVERED),
    ))
    provider = TelegramNotificationProvider(
        TelegramConfiguration(TelegramMode.TEST, "risk_alerts"),
        transport,
    )
    waiter = RecordingWaiter()
    result = dispatch(
        provider,
        retry=RetryPolicy(2, (D("2"),)),
        waiter=waiter,
    ).dispatch(notification())
    assert result.status == DispatchStatus.DELIVERED
    assert len(transport.messages) == 2
    assert transport.messages[0] == transport.messages[1]
    assert waiter.delays == [D("2")]


def test_formatter_limit_failure_is_permanent_and_never_touches_transport():
    transport = FakeTelegramTransport()
    provider = TelegramNotificationProvider(
        TelegramConfiguration(TelegramMode.TEST, "risk_alerts", 256),
        transport,
    )
    large_event = notification({"details": "x" * 400})
    result = dispatch(
        provider,
        retry=RetryPolicy(2, (D("1"),)),
        waiter=RecordingWaiter(),
    ).dispatch(large_event)
    assert result.status == DispatchStatus.FAILED
    assert result.failure_code == "TELEGRAM_FORMAT_REJECTED"
    assert len(result.attempts) == 1
    assert transport.messages == []


def test_transport_exception_uses_retryable_result_without_error_detail_leakage():
    class FailingTransport:
        def submit(self, message):
            raise RuntimeError("secret endpoint detail")

    provider = TelegramNotificationProvider(
        TelegramConfiguration(TelegramMode.TEST, "risk_alerts"),
        FailingTransport(),
    )
    result = dispatch(provider).dispatch(notification())
    assert result.status == DispatchStatus.RETRY_EXHAUSTED
    assert result.failure_code == "TELEGRAM_TRANSPORT_EXCEPTION"
    assert "secret" not in repr(result)


def test_invalid_transport_result_fails_permanently():
    class InvalidTransport:
        def submit(self, message):
            return True

    provider = TelegramNotificationProvider(
        TelegramConfiguration(TelegramMode.TEST, "risk_alerts"),
        InvalidTransport(),
    )
    result = dispatch(provider).dispatch(notification())
    assert result.status == DispatchStatus.FAILED
    assert result.failure_code == "TELEGRAM_TRANSPORT_INVALID_RESULT"


def test_telegram_message_is_immutable():
    message = TelegramEventFormatter().format(notification(), "risk_alerts")
    assert isinstance(message, TelegramMessage)
    with pytest.raises(FrozenInstanceError):
        message.text = "changed"
