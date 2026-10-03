"""Provider-independent notification dispatch with fail-closed delivery controls."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
import re
from threading import Lock
from typing import Callable, Protocol

from .event_domain import NotificationEvent, safe_payload


class NotificationProviderKind(str, Enum):
    DISABLED = "DISABLED"
    TEST = "TEST"
    TELEGRAM = "TELEGRAM"
    WHATSAPP = "WHATSAPP"
    EMAIL = "EMAIL"
    IN_APP = "IN_APP"


class ProviderAttemptStatus(str, Enum):
    DELIVERED = "DELIVERED"
    RETRYABLE_FAILURE = "RETRYABLE_FAILURE"
    PERMANENT_FAILURE = "PERMANENT_FAILURE"


class DispatchStatus(str, Enum):
    DISABLED = "DISABLED"
    DELIVERED = "DELIVERED"
    DEDUPLICATED = "DEDUPLICATED"
    RATE_LIMITED = "RATE_LIMITED"
    RETRY_EXHAUSTED = "RETRY_EXHAUSTED"
    FAILED = "FAILED"
    DELIVERY_UNCONFIRMED = "DELIVERY_UNCONFIRMED"


_ERROR_CODE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")


def _validate_error_code(value: str | None, *, required: bool) -> None:
    if value is None and not required:
        return
    if not isinstance(value, str) or _ERROR_CODE.fullmatch(value) is None:
        raise ValueError("error_code must be an uppercase safe identifier")


@dataclass(frozen=True)
class ProviderAttemptResult:
    status: ProviderAttemptStatus
    error_code: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, ProviderAttemptStatus):
            raise ValueError("invalid provider attempt status")
        delivered = self.status == ProviderAttemptStatus.DELIVERED
        _validate_error_code(self.error_code, required=not delivered)
        if delivered and self.error_code is not None:
            raise ValueError("delivered attempt cannot include an error code")


@dataclass(frozen=True)
class DispatchAttempt:
    number: int
    status: ProviderAttemptStatus
    error_code: str | None
    retry_delay_seconds: Decimal | None = None

    def __post_init__(self) -> None:
        if type(self.number) is not int or self.number < 1:
            raise ValueError("attempt number must be a positive integer")
        if not isinstance(self.status, ProviderAttemptStatus):
            raise ValueError("invalid attempt status")
        _validate_error_code(
            self.error_code,
            required=self.status != ProviderAttemptStatus.DELIVERED,
        )
        if self.retry_delay_seconds is not None and (
            not isinstance(self.retry_delay_seconds, Decimal)
            or not self.retry_delay_seconds.is_finite()
            or self.retry_delay_seconds < 0
        ):
            raise ValueError("retry delay must be a nonnegative finite Decimal")


@dataclass(frozen=True)
class DispatchResult:
    status: DispatchStatus
    provider: NotificationProviderKind
    event_id: str
    dedupe_identity: str
    attempts: tuple[DispatchAttempt, ...] = ()
    failure_code: str | None = None
    execution_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.status, DispatchStatus):
            raise ValueError("invalid dispatch status")
        if not isinstance(self.provider, NotificationProviderKind):
            raise ValueError("invalid notification provider")
        for name in ("event_id", "dedupe_identity"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} is required")
        if not isinstance(self.attempts, tuple) or any(
            not isinstance(item, DispatchAttempt) for item in self.attempts
        ):
            raise ValueError("attempts must be an immutable attempt tuple")
        _validate_error_code(self.failure_code, required=False)


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 1
    delays_seconds: tuple[Decimal, ...] = ()

    def __post_init__(self) -> None:
        if type(self.max_attempts) is not int or self.max_attempts < 1:
            raise ValueError("max_attempts must be a positive integer")
        if len(self.delays_seconds) != self.max_attempts - 1:
            raise ValueError("retry delays must contain one value per retry")
        if any(
            not isinstance(delay, Decimal)
            or not delay.is_finite()
            or delay < 0
            for delay in self.delays_seconds
        ):
            raise ValueError("retry delays must be nonnegative finite Decimals")

    def delay_after(self, attempt_number: int) -> Decimal:
        if attempt_number < 1 or attempt_number >= self.max_attempts:
            raise ValueError("attempt does not have a configured retry")
        return self.delays_seconds[attempt_number - 1]


class NotificationProvider(Protocol):
    @property
    def kind(self) -> NotificationProviderKind: ...

    def deliver(self, event: NotificationEvent) -> ProviderAttemptResult: ...


class NotificationDedupeStore(Protocol):
    def try_claim(self, identity: str) -> bool: ...

    def mark_delivered(self, identity: str) -> None: ...

    def release(self, identity: str) -> None: ...


class NotificationRateLimiter(Protocol):
    def allow(
        self,
        provider: NotificationProviderKind,
        event: NotificationEvent,
        attempt_number: int,
        now: datetime,
    ) -> bool: ...


class RetryWaiter(Protocol):
    def wait(self, delay_seconds: Decimal) -> None: ...


class DisabledNotificationProvider:
    kind = NotificationProviderKind.DISABLED

    def deliver(self, event: NotificationEvent) -> ProviderAttemptResult:
        raise RuntimeError("disabled notification provider cannot deliver")


class FakeNotificationProvider:
    """Deterministic in-process provider for tests; it performs no I/O."""

    kind = NotificationProviderKind.TEST

    def __init__(
        self,
        outcomes: tuple[ProviderAttemptResult, ...] | None = None,
    ) -> None:
        self._outcomes = (
            outcomes
            if outcomes is not None
            else (ProviderAttemptResult(ProviderAttemptStatus.DELIVERED),)
        )
        if not self._outcomes:
            raise ValueError("fake provider requires at least one outcome")
        if any(not isinstance(item, ProviderAttemptResult) for item in self._outcomes):
            raise ValueError("fake provider outcomes are invalid")
        self.delivered_events: list[NotificationEvent] = []
        self.attempted_events: list[NotificationEvent] = []

    def deliver(self, event: NotificationEvent) -> ProviderAttemptResult:
        self.attempted_events.append(event)
        index = min(len(self.attempted_events) - 1, len(self._outcomes) - 1)
        result = self._outcomes[index]
        if result.status == ProviderAttemptStatus.DELIVERED:
            self.delivered_events.append(event)
        return result


class InMemoryNotificationDedupeStore:
    """Process-local bounded dedupe store; persistence is a later integration seam."""

    def __init__(self, capacity: int = 10_000) -> None:
        if type(capacity) is not int or capacity < 1:
            raise ValueError("dedupe capacity must be a positive integer")
        self._capacity = capacity
        self._claimed: set[str] = set()
        self._delivered: set[str] = set()
        self._lock = Lock()

    def try_claim(self, identity: str) -> bool:
        if not isinstance(identity, str) or not identity:
            raise ValueError("dedupe identity is required")
        with self._lock:
            if identity in self._claimed or identity in self._delivered:
                return False
            if len(self._claimed) + len(self._delivered) >= self._capacity:
                raise RuntimeError("notification dedupe capacity exhausted")
            self._claimed.add(identity)
            return True

    def mark_delivered(self, identity: str) -> None:
        with self._lock:
            if identity not in self._claimed:
                raise RuntimeError("notification dedupe claim is missing")
            self._claimed.remove(identity)
            self._delivered.add(identity)

    def release(self, identity: str) -> None:
        with self._lock:
            self._claimed.discard(identity)


class FixedWindowNotificationRateLimiter:
    """Thread-safe provider-level fixed-window attempt limiter."""

    def __init__(self, max_attempts: int, window: timedelta) -> None:
        if type(max_attempts) is not int or max_attempts < 1:
            raise ValueError("rate limit must be a positive integer")
        if not isinstance(window, timedelta) or window <= timedelta(0):
            raise ValueError("rate limit window must be positive")
        self._max_attempts = max_attempts
        self._window = window
        self._windows: dict[NotificationProviderKind, tuple[datetime, int]] = {}
        self._lock = Lock()

    def allow(
        self,
        provider: NotificationProviderKind,
        event: NotificationEvent,
        attempt_number: int,
        now: datetime,
    ) -> bool:
        if not isinstance(provider, NotificationProviderKind):
            raise ValueError("invalid notification provider")
        if not isinstance(event, NotificationEvent):
            raise ValueError("invalid notification event")
        if type(attempt_number) is not int or attempt_number < 1:
            raise ValueError("attempt number must be positive")
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("rate limit clock must be timezone-aware")
        with self._lock:
            current = self._windows.get(provider)
            if current is None or now - current[0] >= self._window:
                self._windows[provider] = (now, 1)
                return True
            if now < current[0] or current[1] >= self._max_attempts:
                return False
            self._windows[provider] = (current[0], current[1] + 1)
            return True


class NotificationDispatcher:
    def __init__(
        self,
        provider: NotificationProvider,
        dedupe_store: NotificationDedupeStore,
        rate_limiter: NotificationRateLimiter,
        retry_policy: RetryPolicy | None = None,
        retry_waiter: RetryWaiter | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._provider = provider
        self._provider_kind = provider.kind
        if not isinstance(self._provider_kind, NotificationProviderKind):
            raise ValueError("provider kind is invalid")
        self._dedupe_store = dedupe_store
        self._rate_limiter = rate_limiter
        self._retry_policy = retry_policy or RetryPolicy()
        self._retry_waiter = retry_waiter
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def _result(
        self,
        event: NotificationEvent,
        status: DispatchStatus,
        attempts: tuple[DispatchAttempt, ...] = (),
        failure_code: str | None = None,
    ) -> DispatchResult:
        return DispatchResult(
            status=status,
            provider=self._provider_kind,
            event_id=event.event_id,
            dedupe_identity=event.dedupe_identity,
            attempts=attempts,
            failure_code=failure_code,
        )

    def _release_or_fail(
        self,
        event: NotificationEvent,
        dedupe_key: str,
        status: DispatchStatus,
        attempts: tuple[DispatchAttempt, ...],
        failure_code: str,
    ) -> DispatchResult:
        try:
            self._dedupe_store.release(dedupe_key)
        except Exception:
            return self._result(
                event,
                DispatchStatus.FAILED,
                attempts,
                "DEDUPE_RELEASE_FAILED",
            )
        return self._result(event, status, attempts, failure_code)

    def dispatch(self, event: NotificationEvent) -> DispatchResult:
        if not isinstance(event, NotificationEvent):
            raise ValueError("dispatch requires a NotificationEvent")
        if safe_payload(dict(event.payload), event.redaction_policy) != event.payload:
            raise ValueError("notification event payload is not safe")
        if self._provider_kind == NotificationProviderKind.DISABLED:
            return self._result(event, DispatchStatus.DISABLED)

        dedupe_key = f"{self._provider_kind.value}:{event.dedupe_identity}"
        try:
            claimed = self._dedupe_store.try_claim(dedupe_key)
            if type(claimed) is not bool:
                raise TypeError("dedupe result must be boolean")
        except Exception:
            return self._result(event, DispatchStatus.FAILED, failure_code="DEDUPE_UNAVAILABLE")
        if not claimed:
            return self._result(event, DispatchStatus.DEDUPLICATED)

        attempts: list[DispatchAttempt] = []
        for attempt_number in range(1, self._retry_policy.max_attempts + 1):
            try:
                now = self._clock()
                if (
                    not isinstance(now, datetime)
                    or now.tzinfo is None
                    or now.utcoffset() is None
                ):
                    raise ValueError("dispatch clock must be timezone-aware")
                allowed = self._rate_limiter.allow(
                    self._provider_kind,
                    event,
                    attempt_number,
                    now,
                )
                if type(allowed) is not bool:
                    raise TypeError("rate limit result must be boolean")
            except Exception:
                return self._release_or_fail(
                    event,
                    dedupe_key,
                    DispatchStatus.FAILED,
                    tuple(attempts),
                    "RATE_LIMITER_UNAVAILABLE",
                )
            if not allowed:
                return self._release_or_fail(
                    event,
                    dedupe_key,
                    DispatchStatus.RATE_LIMITED,
                    tuple(attempts),
                    "RATE_LIMITED",
                )

            try:
                provider_result = self._provider.deliver(event)
                if not isinstance(provider_result, ProviderAttemptResult):
                    raise TypeError("invalid provider result")
            except Exception:
                provider_result = ProviderAttemptResult(
                    ProviderAttemptStatus.RETRYABLE_FAILURE,
                    "PROVIDER_EXCEPTION",
                )

            if provider_result.status == ProviderAttemptStatus.DELIVERED:
                attempts.append(DispatchAttempt(attempt_number, provider_result.status, None))
                try:
                    self._dedupe_store.mark_delivered(dedupe_key)
                except Exception:
                    return self._result(
                        event,
                        DispatchStatus.DELIVERY_UNCONFIRMED,
                        tuple(attempts),
                        "DEDUPE_COMMIT_FAILED",
                    )
                return self._result(event, DispatchStatus.DELIVERED, tuple(attempts))

            retryable = provider_result.status == ProviderAttemptStatus.RETRYABLE_FAILURE
            has_retry = attempt_number < self._retry_policy.max_attempts
            delay = (
                self._retry_policy.delay_after(attempt_number)
                if retryable and has_retry
                else None
            )
            attempts.append(
                DispatchAttempt(
                    attempt_number,
                    provider_result.status,
                    provider_result.error_code,
                    delay,
                )
            )
            if not retryable:
                return self._release_or_fail(
                    event,
                    dedupe_key,
                    DispatchStatus.FAILED,
                    tuple(attempts),
                    provider_result.error_code or "PROVIDER_FAILURE",
                )
            if not has_retry:
                return self._release_or_fail(
                    event,
                    dedupe_key,
                    DispatchStatus.RETRY_EXHAUSTED,
                    tuple(attempts),
                    provider_result.error_code or "RETRY_EXHAUSTED",
                )
            if self._retry_waiter is None:
                return self._release_or_fail(
                    event,
                    dedupe_key,
                    DispatchStatus.FAILED,
                    tuple(attempts),
                    "RETRY_WAITER_UNAVAILABLE",
                )
            try:
                self._retry_waiter.wait(delay)
            except Exception:
                return self._release_or_fail(
                    event,
                    dedupe_key,
                    DispatchStatus.FAILED,
                    tuple(attempts),
                    "RETRY_WAIT_FAILED",
                )

        raise RuntimeError("unreachable notification dispatch state")
