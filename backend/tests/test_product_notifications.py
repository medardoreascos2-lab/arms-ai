"""P105A canonical Product notification domain tests."""

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from backend.product.notifications import (
    NotificationCategory,
    NotificationChannel,
    NotificationPriority,
    NotificationStatus,
    ProductNotification,
)


NOW = datetime(2026, 10, 4, 12, tzinfo=timezone.utc)


def notification(**overrides):
    body = {
        "notification_id": "synthetic-notification-1",
        "user_id": "synthetic-user-1",
        "tenant_id": "synthetic-tenant-1",
        "category": NotificationCategory.SECURITY,
        "priority": NotificationPriority.CRITICAL,
        "title": "Synthetic security review",
        "summary": "Local test record only.",
        "source_type": "PRODUCT",
        "source_reference": "synthetic-source-1",
        "created_at": NOW,
        "expires_at": NOW + timedelta(hours=1),
        "status": NotificationStatus.UNREAD,
        "channels_requested": (
            NotificationChannel.IN_APP,
            NotificationChannel.EMAIL,
        ),
        "requires_acknowledgement": True,
        "metadata": {"classification": "LOCAL_TEST_ONLY"},
    }
    body.update(overrides)
    return ProductNotification(**body)


def test_notification_record_preserves_scope_priority_and_source():
    item = notification()
    assert item.user_id == "synthetic-user-1"
    assert item.tenant_id == "synthetic-tenant-1"
    assert item.priority is NotificationPriority.CRITICAL
    assert item.source_reference == "synthetic-source-1"
    assert item.requires_acknowledgement is True


def test_domain_enums_match_the_contract_exactly():
    assert {item.value for item in NotificationCategory} == {
        "FINANCIAL", "TRADING_COACH", "PORTFOLIO", "MEDAR",
        "SYSTEM", "SECURITY", "MEMORY", "PRODUCT",
    }
    assert {item.value for item in NotificationPriority} == {
        "INFO", "WATCH", "IMPORTANT", "CRITICAL",
    }
    assert {item.value for item in NotificationStatus} == {
        "UNREAD", "READ", "ACKNOWLEDGED", "SNOOZED", "DISMISSED", "EXPIRED",
    }


def test_notification_is_frozen_and_forbids_unknown_authority_fields():
    item = notification()
    with pytest.raises(ValidationError):
        item.status = NotificationStatus.READ
    with pytest.raises(ValidationError):
        ProductNotification.model_validate({
            **item.model_dump(),
            "execution_authorized": True,
        })


@pytest.mark.parametrize("field", ["created_at", "expires_at"])
def test_notification_rejects_non_utc_timestamps(field):
    with pytest.raises(ValidationError):
        notification(**{field: datetime(2026, 10, 4, 12)})


def test_notification_rejects_invalid_expiry_duplicate_channels_and_dismissed_ack():
    with pytest.raises(ValidationError):
        notification(expires_at=NOW)
    with pytest.raises(ValidationError):
        notification(channels_requested=(
            NotificationChannel.IN_APP, NotificationChannel.IN_APP,
        ))
    with pytest.raises(ValidationError):
        notification(status=NotificationStatus.DISMISSED)


def test_domain_exposes_no_delivery_or_financial_mutation_methods():
    method_names = {
        name for name, value in vars(ProductNotification).items() if callable(value)
    }
    assert not method_names.intersection({
        "send", "deliver", "publish", "execute", "trade", "mutate_portfolio",
    })
