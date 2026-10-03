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
