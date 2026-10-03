"""Provider-independent notification dispatch tests."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal as D

import pytest

from backend.notifications import (
    DisabledNotificationProvider,
    DispatchStatus,
    FakeNotificationProvider,
    FixedWindowNotificationRateLimiter,
    InMemoryNotificationDedupeStore,
    NotificationDispatcher,
    NotificationEventType,
    NotificationProviderKind,
    ProviderAttemptResult,
    ProviderAttemptStatus,
    RedactionPolicy,
    RetryPolicy,
    create_notification_event,
)


NOW = datetime(2026, 10, 4, 16, 0, tzinfo=timezone.utc)


def event(payload=None):
    return create_notification_event(
        NotificationEventType.RISK_BLOCK,
        "risk-1",
        NOW,
        payload=payload or {"reason": "DAILY_LIMIT"},
    )


class RecordingRateLimiter:
    def __init__(self, decisions=(True,)):
        self.decisions = decisions
        self.calls = []

    def allow(self, provider, notification, attempt_number, now):
        self.calls.append((provider, notification, attempt_number, now))
        index = min(len(self.calls) - 1, len(self.decisions) - 1)
        return self.decisions[index]


class RecordingWaiter:
    def __init__(self):
        self.delays = []

    def wait(self, delay_seconds):
        self.delays.append(delay_seconds)


class ExplodingDependency:
    def __getattr__(self, name):
        raise AssertionError(f"disabled dispatch touched {name}")


def dispatcher(provider, *, store=None, limiter=None, retry=None, waiter=None):
    return NotificationDispatcher(
        provider,
        store or InMemoryNotificationDedupeStore(),
        limiter or RecordingRateLimiter(),
        retry,
        waiter,
        clock=lambda: NOW,
    )


def test_disabled_provider_has_zero_dispatch_side_effects():
    result = NotificationDispatcher(
        DisabledNotificationProvider(),
        ExplodingDependency(),
        ExplodingDependency(),
    ).dispatch(event())
    assert result.status == DispatchStatus.DISABLED
    assert result.attempts == ()
    assert result.execution_authorized is False


def test_fake_delivery_is_deduplicated_after_success():
    provider = FakeNotificationProvider()
    store = InMemoryNotificationDedupeStore()
    service = dispatcher(provider, store=store)
    first = service.dispatch(event())
    duplicate = service.dispatch(event())
    assert first.status == DispatchStatus.DELIVERED
    assert duplicate.status == DispatchStatus.DEDUPLICATED
    assert provider.attempted_events == [event()]
    assert provider.delivered_events == [event()]
    assert first.execution_authorized is False
    assert duplicate.execution_authorized is False


def test_retry_policy_uses_waiter_and_rate_limit_seam_per_attempt():
    provider = FakeNotificationProvider((
        ProviderAttemptResult(
            ProviderAttemptStatus.RETRYABLE_FAILURE,
            "TEMPORARY_PROVIDER_FAILURE",
        ),
        ProviderAttemptResult(ProviderAttemptStatus.DELIVERED),
    ))
    limiter = RecordingRateLimiter((True, True))
    waiter = RecordingWaiter()
    service = dispatcher(
        provider,
        limiter=limiter,
        retry=RetryPolicy(2, (D("1.5"),)),
        waiter=waiter,
    )
    result = service.dispatch(event())
    assert result.status == DispatchStatus.DELIVERED
    assert [attempt.status for attempt in result.attempts] == [
        ProviderAttemptStatus.RETRYABLE_FAILURE,
        ProviderAttemptStatus.DELIVERED,
    ]
    assert result.attempts[0].retry_delay_seconds == D("1.5")
    assert waiter.delays == [D("1.5")]
    assert len(limiter.calls) == 2


def test_retryable_failure_without_waiter_fails_closed_before_second_attempt():
    provider = FakeNotificationProvider((
        ProviderAttemptResult(ProviderAttemptStatus.RETRYABLE_FAILURE, "TEMPORARY"),
        ProviderAttemptResult(ProviderAttemptStatus.DELIVERED),
    ))
    result = dispatcher(
        provider,
        retry=RetryPolicy(2, (D("1"),)),
    ).dispatch(event())
    assert result.status == DispatchStatus.FAILED
    assert result.failure_code == "RETRY_WAITER_UNAVAILABLE"
    assert len(provider.attempted_events) == 1


def test_retry_exhaustion_releases_claim_for_a_future_dispatch():
    failed = ProviderAttemptResult(ProviderAttemptStatus.RETRYABLE_FAILURE, "TEMPORARY")
    provider = FakeNotificationProvider((failed,))
    store = InMemoryNotificationDedupeStore()
    service = dispatcher(provider, store=store)
    first = service.dispatch(event())
    second = service.dispatch(event())
    assert first.status == DispatchStatus.RETRY_EXHAUSTED
    assert second.status == DispatchStatus.RETRY_EXHAUSTED
    assert len(provider.attempted_events) == 2


def test_permanent_failure_does_not_retry_and_releases_claim():
    provider = FakeNotificationProvider((
        ProviderAttemptResult(ProviderAttemptStatus.PERMANENT_FAILURE, "INVALID_TARGET"),
    ))
    store = InMemoryNotificationDedupeStore()
    service = dispatcher(
        provider,
        store=store,
        retry=RetryPolicy(3, (D("1"), D("2"))),
        waiter=RecordingWaiter(),
    )
    first = service.dispatch(event())
    second = service.dispatch(event())
    assert first.status == DispatchStatus.FAILED
    assert first.failure_code == "INVALID_TARGET"
    assert second.status == DispatchStatus.FAILED
    assert len(provider.attempted_events) == 2


def test_rate_limit_blocks_before_provider_and_releases_claim():
    provider = FakeNotificationProvider()
    limiter = RecordingRateLimiter((False,))
    store = InMemoryNotificationDedupeStore()
    service = dispatcher(provider, store=store, limiter=limiter)
    first = service.dispatch(event())
    second = service.dispatch(event())
    assert first.status == DispatchStatus.RATE_LIMITED
    assert second.status == DispatchStatus.RATE_LIMITED
    assert provider.attempted_events == []


def test_dedupe_unavailable_fails_before_rate_limit_or_provider():
    class UnavailableStore:
        def try_claim(self, identity):
            raise RuntimeError("offline")

    provider = FakeNotificationProvider()
    limiter = RecordingRateLimiter()
    result = dispatcher(provider, store=UnavailableStore(), limiter=limiter).dispatch(event())
    assert result.status == DispatchStatus.FAILED
    assert result.failure_code == "DEDUPE_UNAVAILABLE"
    assert provider.attempted_events == []
    assert limiter.calls == []


@pytest.mark.parametrize("invalid_claim", [1, "yes", None])
def test_nonboolean_dedupe_decision_fails_closed(invalid_claim):
    class InvalidStore:
        def try_claim(self, identity):
            return invalid_claim

    provider = FakeNotificationProvider()
    result = dispatcher(provider, store=InvalidStore()).dispatch(event())
    assert result.status == DispatchStatus.FAILED
    assert result.failure_code == "DEDUPE_UNAVAILABLE"
    assert provider.attempted_events == []


@pytest.mark.parametrize("invalid_decision", [1, "yes", None])
def test_nonboolean_rate_limit_decision_fails_closed(invalid_decision):
    class InvalidLimiter:
        def allow(self, provider, notification, attempt_number, now):
            return invalid_decision

    provider = FakeNotificationProvider()
    result = dispatcher(provider, limiter=InvalidLimiter()).dispatch(event())
    assert result.status == DispatchStatus.FAILED
    assert result.failure_code == "RATE_LIMITER_UNAVAILABLE"
    assert provider.attempted_events == []


def test_failed_dedupe_commit_reports_unconfirmed_and_does_not_resend():
    class CommitFailingStore(InMemoryNotificationDedupeStore):
        def mark_delivered(self, identity):
            raise RuntimeError("offline")

    provider = FakeNotificationProvider()
    service = dispatcher(provider, store=CommitFailingStore())
    first = service.dispatch(event())
    second = service.dispatch(event())
    assert first.status == DispatchStatus.DELIVERY_UNCONFIRMED
    assert first.failure_code == "DEDUPE_COMMIT_FAILED"
    assert second.status == DispatchStatus.DEDUPLICATED
    assert len(provider.attempted_events) == 1


def test_redacted_payload_is_the_only_payload_visible_to_provider():
    provider = FakeNotificationProvider()
    notification = event({
        "api_key": "unsafe-value",
        "message": "authorization=secret-value",
    })
    result = dispatcher(provider).dispatch(notification)
    delivered = dict(provider.delivered_events[0].payload)
    assert result.status == DispatchStatus.DELIVERED
    assert delivered == {"api_key": "[REDACTED]", "message": "[REDACTED]"}


def test_strict_redaction_rejects_event_before_dispatch_exists():
    provider = FakeNotificationProvider()
    with pytest.raises(ValueError, match="sensitive"):
        event_with_secret = create_notification_event(
            NotificationEventType.DATA_FAULT,
            "data-1",
            NOW,
            payload={"token": "unsafe"},
            redaction_policy=RedactionPolicy.REJECT_SENSITIVE,
        )
        dispatcher(provider).dispatch(event_with_secret)
    assert provider.attempted_events == []


def test_fixed_window_rate_limiter_is_provider_scoped_and_fails_on_clock_rewind():
    limiter = FixedWindowNotificationRateLimiter(2, timedelta(minutes=1))
    notification = event()
    assert limiter.allow(NotificationProviderKind.TEST, notification, 1, NOW)
    assert limiter.allow(NotificationProviderKind.TEST, notification, 2, NOW)
    assert not limiter.allow(NotificationProviderKind.TEST, notification, 3, NOW)
    assert limiter.allow(NotificationProviderKind.TELEGRAM, notification, 1, NOW)
    assert not limiter.allow(
        NotificationProviderKind.TEST,
        notification,
        4,
        NOW - timedelta(seconds=1),
    )
    assert limiter.allow(
        NotificationProviderKind.TEST,
        notification,
        1,
        NOW + timedelta(minutes=1),
    )


def test_dedupe_capacity_exhaustion_blocks_before_provider():
    store = InMemoryNotificationDedupeStore(capacity=1)
    first_provider = FakeNotificationProvider()
    first_result = dispatcher(first_provider, store=store).dispatch(event())
    assert first_result.status == DispatchStatus.DELIVERED
    second_provider = FakeNotificationProvider()
    second_event = create_notification_event(
        NotificationEventType.DATA_FAULT,
        "data-2",
        NOW,
    )
    result = dispatcher(second_provider, store=store).dispatch(second_event)
    assert result.status == DispatchStatus.FAILED
    assert result.failure_code == "DEDUPE_UNAVAILABLE"
    assert second_provider.attempted_events == []


def test_provider_seams_include_telegram_and_future_channels_without_network_code():
    assert set(NotificationProviderKind) == {
        NotificationProviderKind.DISABLED,
        NotificationProviderKind.TEST,
        NotificationProviderKind.TELEGRAM,
        NotificationProviderKind.WHATSAPP,
        NotificationProviderKind.EMAIL,
        NotificationProviderKind.IN_APP,
    }
