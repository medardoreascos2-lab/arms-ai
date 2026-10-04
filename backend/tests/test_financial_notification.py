"""F110B: notification routing is a preview with zero external sends."""

from datetime import datetime, timezone

from backend.financial.alert import AlertCategory, AlertPriority, FinancialAlert
from backend.financial.notification import NotificationChannel, plan_notification

NOW = datetime(2026, 10, 4, tzinfo=timezone.utc)


def test_notification_plan_has_no_transport_or_send_authority():
    alert = FinancialAlert("synthetic:a1", AlertCategory.RISK, AlertPriority.WATCH,
                           "risk", "synthetic:source", NOW)
    plan = plan_notification(alert, (NotificationChannel.EMAIL, NotificationChannel.PUSH))
    assert plan.status == "PREVIEW_ONLY"
    assert not plan.send_authority
    assert not hasattr(plan, "send")
