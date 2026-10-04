"""P105B scoped local SQLite notification store tests."""

from datetime import datetime, timedelta, timezone
import inspect

import pytest

from backend.product.notification_store import (
    LocalSqliteNotificationStore,
    NotificationScope,
    ProductNotificationStore,
)
from backend.product.notifications import (
    NotificationCategory,
    NotificationPriority,
    NotificationStatus,
    ProductNotification,
)


NOW = datetime(2026, 10, 4, 12, tzinfo=timezone.utc)
SCOPE = NotificationScope("synthetic-tenant-1", "synthetic-user-1")
OTHER_USER = NotificationScope("synthetic-tenant-1", "synthetic-user-2")
OTHER_TENANT = NotificationScope("synthetic-tenant-2", "synthetic-user-1")


def notification(**overrides):
    body = {
        "notification_id": "synthetic-notification-1",
        "user_id": SCOPE.user_id,
        "tenant_id": SCOPE.tenant_id,
        "category": NotificationCategory.SECURITY,
        "priority": NotificationPriority.CRITICAL,
        "title": "Synthetic security review",
        "summary": "Local test only.",
        "source_type": "PRODUCT",
        "source_reference": "synthetic-source-1",
        "created_at": NOW,
        "requires_acknowledgement": True,
    }
    body.update(overrides)
    return ProductNotification(**body)


@pytest.fixture
def store(tmp_path):
    value = LocalSqliteNotificationStore(
        str(tmp_path / "notifications.sqlite3"),
        environment="LOCAL_TEST_ONLY",
    )
    yield value
    value.close()


def test_store_protocol_has_only_required_inbox_operations():
    public_methods = {
        name for name, value in ProductNotificationStore.__dict__.items()
        if not name.startswith("_") and callable(value)
    }
    assert public_methods == {
        "append", "list", "get", "mark_read",
        "acknowledge", "snooze", "dismiss",
    }
    source = inspect.getsource(LocalSqliteNotificationStore)
    assert "DELETE FROM" not in source
    assert "send(" not in source
    assert "publish(" not in source


def test_append_is_idempotent_and_conflicting_reuse_is_rejected(store):
    item = notification()
    assert store.append(SCOPE, item, "request-1") == item
    assert store.append(SCOPE, item, "request-1") == item
    with pytest.raises(ValueError):
        store.append(
            SCOPE,
            notification(notification_id="synthetic-notification-2"),
            "request-1",
        )
    assert len(store.list(SCOPE)) == 1


def test_append_requires_exact_tenant_and_user_scope(store):
    item = notification()
    with pytest.raises(PermissionError):
        store.append(OTHER_USER, item, "wrong-user")
    with pytest.raises(PermissionError):
        store.append(OTHER_TENANT, item, "wrong-tenant")
    assert store.list(SCOPE) == ()


def test_cross_user_and_cross_tenant_reads_return_no_records(store):
    item = store.append(SCOPE, notification(), "request-1")
    assert store.get(SCOPE, item.notification_id) == item
    assert store.get(OTHER_USER, item.notification_id) is None
    assert store.get(OTHER_TENANT, item.notification_id) is None
    assert store.list(OTHER_USER) == ()
    assert store.list(OTHER_TENANT) == ()


def test_scoped_transitions_are_persisted_and_timestamped(store):
    item = store.append(
        SCOPE,
        notification(requires_acknowledgement=False),
        "request-1",
    )
    read = store.mark_read(SCOPE, item.notification_id, NOW + timedelta(minutes=1))
    assert read.status is NotificationStatus.READ
    snoozed = store.snooze(
        SCOPE, item.notification_id,
        NOW + timedelta(hours=1), NOW + timedelta(minutes=2),
    )
    assert snoozed.status is NotificationStatus.SNOOZED
    dismissed = store.dismiss(
        SCOPE, item.notification_id, NOW + timedelta(minutes=3),
    )
    assert dismissed.status is NotificationStatus.DISMISSED
    assert store.get(SCOPE, item.notification_id) == dismissed


def test_acknowledgement_required_notification_cannot_be_dismissed_early(store):
    item = store.append(SCOPE, notification(), "request-1")
    with pytest.raises(PermissionError):
        store.dismiss(SCOPE, item.notification_id, NOW + timedelta(minutes=1))
    acknowledged = store.acknowledge(
        SCOPE, item.notification_id, NOW + timedelta(minutes=2),
    )
    assert acknowledged.status is NotificationStatus.ACKNOWLEDGED
    dismissed = store.dismiss(
        SCOPE, item.notification_id, NOW + timedelta(minutes=3),
    )
    assert dismissed.status is NotificationStatus.DISMISSED


def test_wrong_scope_cannot_mutate_a_notification(store):
    item = store.append(SCOPE, notification(), "request-1")
    for other in (OTHER_USER, OTHER_TENANT):
        with pytest.raises(PermissionError):
            store.mark_read(other, item.notification_id, NOW)
        with pytest.raises(PermissionError):
            store.acknowledge(other, item.notification_id, NOW)


def test_store_rejects_production_environment_and_non_utc_transitions(tmp_path, store):
    with pytest.raises(ValueError):
        LocalSqliteNotificationStore(
            str(tmp_path / "production.sqlite3"), environment="PRODUCTION",
        )
    item = store.append(SCOPE, notification(), "request-1")
    with pytest.raises(ValueError):
        store.mark_read(SCOPE, item.notification_id, datetime(2026, 10, 4, 12))
