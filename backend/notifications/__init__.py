"""Provider-independent notification domain and delivery seams."""

from .event_domain import (
    DEFAULT_SEVERITY,
    NotificationEvent,
    NotificationEventType,
    NotificationIdentity,
    NotificationSeverity,
    RedactionPolicy,
    create_notification_event,
    safe_payload,
)
from .dispatch import (
    DisabledNotificationProvider,
    DispatchAttempt,
    DispatchResult,
    DispatchStatus,
    FakeNotificationProvider,
    FixedWindowNotificationRateLimiter,
    InMemoryNotificationDedupeStore,
    NotificationDedupeStore,
    NotificationDispatcher,
    NotificationProvider,
    NotificationProviderKind,
    NotificationRateLimiter,
    ProviderAttemptResult,
    ProviderAttemptStatus,
    RetryPolicy,
    RetryWaiter,
)
from .telegram import (
    FakeTelegramTransport,
    TelegramConfiguration,
    TelegramEventFormatter,
    TelegramMessage,
    TelegramMode,
    TelegramNotificationProvider,
    TelegramTransport,
    build_telegram_provider,
)
