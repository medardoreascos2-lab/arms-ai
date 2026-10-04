"""P105C notification channel preference tests."""

from datetime import time
import inspect
import sqlite3

import pytest
from pydantic import ValidationError

from backend.product.notification_preferences import (
    CategoryNotificationPreference,
    LocalSqliteNotificationPreferenceStore,
    NotificationPreferenceProfile,
    QuietHours,
)
from backend.product.notification_store import NotificationScope
from backend.product.notifications import (
    NotificationCategory,
    NotificationChannel,
    NotificationPriority,
)


SCOPE = NotificationScope("synthetic-tenant-1", "synthetic-user-1")
OTHER = NotificationScope("synthetic-tenant-1", "synthetic-user-2")


def profile(**overrides):
    body = {
        "tenant_id": SCOPE.tenant_id,
        "user_id": SCOPE.user_id,
        "preferences": (
            CategoryNotificationPreference(
                category=NotificationCategory.SECURITY,
                enabled=True,
                priority_threshold=NotificationPriority.IMPORTANT,
                quiet_hours=QuietHours(start=time(22), end=time(7)),
                critical_override=True,
                channels=(
                    NotificationChannel.IN_APP,
                    NotificationChannel.EMAIL,
                ),
            ),
        ),
    }
    body.update(overrides)
    return NotificationPreferenceProfile(**body)


def test_supported_channels_match_contract_and_no_arbitrary_channel_is_accepted():
    assert {item.value for item in NotificationChannel} == {
        "IN_APP", "VOICE", "PUSH", "TELEGRAM", "WHATSAPP", "EMAIL",
    }
    with pytest.raises(ValidationError):
        CategoryNotificationPreference(
            category="SYSTEM", channels=("SMS",),
        )


def test_threshold_quiet_hours_and_critical_override_are_deterministic():
    value = profile()
    assert value.allows(
        NotificationCategory.SECURITY, NotificationPriority.IMPORTANT,
        NotificationChannel.IN_APP, time(12),
    )
    assert not value.allows(
        NotificationCategory.SECURITY, NotificationPriority.WATCH,
        NotificationChannel.IN_APP, time(12),
    )
    assert not value.allows(
        NotificationCategory.SECURITY, NotificationPriority.IMPORTANT,
        NotificationChannel.IN_APP, time(23),
    )
    assert value.allows(
        NotificationCategory.SECURITY, NotificationPriority.CRITICAL,
        NotificationChannel.IN_APP, time(23),
    )


def test_disabled_missing_and_unselected_channels_are_denied():
    value = profile()
    assert not value.allows(
        NotificationCategory.MEDAR, NotificationPriority.CRITICAL,
        NotificationChannel.IN_APP, time(12),
    )
    assert not value.allows(
        NotificationCategory.SECURITY, NotificationPriority.CRITICAL,
        NotificationChannel.PUSH, time(12),
    )


def test_duplicate_categories_channels_and_ambiguous_quiet_hours_are_rejected():
    preference = CategoryNotificationPreference(
        category=NotificationCategory.SYSTEM,
        channels=(NotificationChannel.IN_APP,),
    )
    with pytest.raises(ValidationError):
        profile(preferences=(preference, preference))
    with pytest.raises(ValidationError):
        CategoryNotificationPreference(
            category=NotificationCategory.SYSTEM,
            channels=(NotificationChannel.IN_APP, NotificationChannel.IN_APP),
        )
    with pytest.raises(ValidationError):
        QuietHours(start=time(8), end=time(8))


def test_local_store_is_scoped_and_has_no_send_operation():
    connection = sqlite3.connect(":memory:")
    store = LocalSqliteNotificationPreferenceStore(
        connection, environment="LOCAL_TEST_ONLY",
    )
    value = profile()
    assert store.put(SCOPE, value) == value
    assert store.get(SCOPE) == value
    assert store.get(OTHER) is None
    with pytest.raises(PermissionError):
        store.put(OTHER, value)
    methods = {
        name for name, item in LocalSqliteNotificationPreferenceStore.__dict__.items()
        if callable(item)
    }
    assert methods.isdisjoint({"send", "deliver", "publish"})
    connection.close()


def test_preference_store_rejects_production_environment():
    connection = sqlite3.connect(":memory:")
    with pytest.raises(ValueError):
        LocalSqliteNotificationPreferenceStore(
            connection, environment="PRODUCTION",
        )
    connection.close()
