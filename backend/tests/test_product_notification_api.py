"""P105D local Product notification inbox API tests."""

from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.product_notification_api import (
    create_local_test_product_notification_router,
)
from backend.product.customer_session import (
    LocalSyntheticSessionProvider,
    synthetic_customer_session,
)
from backend.product.notification_store import (
    LocalSqliteNotificationStore,
    NotificationScope,
)
from backend.product.notifications import (
    NotificationCategory,
    NotificationPriority,
    ProductNotification,
)


NOW = datetime(2026, 10, 4, 12, tzinfo=timezone.utc)


def fixture(tmp_path):
    session = synthetic_customer_session(
        issued_at=NOW - timedelta(minutes=5),
        expires_at=NOW + timedelta(hours=1),
    )
    sessions = LocalSyntheticSessionProvider((session,))
    store = LocalSqliteNotificationStore(
        str(tmp_path / "inbox.sqlite3"),
        environment="LOCAL_TEST_ONLY",
    )
    scope = NotificationScope(session.tenant_id, session.user_id)
    store.append(scope, ProductNotification(
        notification_id="synthetic-notification-1",
        user_id=session.user_id,
        tenant_id=session.tenant_id,
        category=NotificationCategory.SECURITY,
        priority=NotificationPriority.CRITICAL,
        title="Synthetic security review",
        summary="Local fixture only.",
        source_type="PRODUCT",
        source_reference="synthetic-source-1",
        created_at=NOW,
        requires_acknowledgement=True,
    ), "seed-1")
    app = FastAPI()
    app.include_router(create_local_test_product_notification_router(
        session_provider=sessions,
        notification_store=store,
        clock=lambda: NOW + timedelta(minutes=10),
    ))
    return (
        TestClient(app, client=("127.0.0.1", 50000)),
        store,
        scope,
    )


def headers():
    return {"X-ARMS-Local-Test-Session": "synthetic-session-1"}


def test_inbox_get_is_scoped_read_only_and_reports_no_authority(tmp_path):
    client, store, scope = fixture(tmp_path)
    response = client.get(
        "/product/notifications",
        params={"user_id": "synthetic-attacker", "tenant_id": "synthetic-other"},
        headers=headers(),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "READY"
    assert [item["notification_id"] for item in body["notifications"]] == [
        "synthetic-notification-1",
    ]
    assert body["external_delivery_authorized"] is False
    assert body["financial_authority"] is False
    assert body["execution_authorized"] is False
    assert body["portfolio_mutation_authorized"] is False
    assert store.get(scope, "synthetic-notification-1").status.value == "UNREAD"


def test_explicit_post_routes_transition_status_without_delivery(tmp_path):
    client, store, scope = fixture(tmp_path)
    assert client.post(
        "/product/notifications/synthetic-notification-1/read",
        headers=headers(),
    ).json()["notification"]["status"] == "READ"
    assert client.post(
        "/product/notifications/synthetic-notification-1/acknowledge",
        headers=headers(),
    ).json()["notification"]["status"] == "ACKNOWLEDGED"
    assert client.post(
        "/product/notifications/synthetic-notification-1/dismiss",
        headers=headers(),
    ).json()["notification"]["status"] == "DISMISSED"
    assert store.get(scope, "synthetic-notification-1").status.value == "DISMISSED"


def test_missing_session_and_non_loopback_clients_are_denied(tmp_path):
    client, _, _ = fixture(tmp_path)
    assert client.get("/product/notifications").json()["status"] == "SESSION_INVALID"
    remote = TestClient(client.app, client=("203.0.113.5", 50000))
    assert remote.get(
        "/product/notifications", headers=headers(),
    ).json()["status"] == "SESSION_INVALID"


def test_openapi_exposes_get_and_explicit_status_posts_only(tmp_path):
    client, _, _ = fixture(tmp_path)
    paths = client.app.openapi()["paths"]
    assert set(paths["/product/notifications"]) == {"get"}
    for action in ("read", "acknowledge", "snooze", "dismiss"):
        assert set(paths[
            "/product/notifications/{notification_id}/" + action
        ]) == {"post"}
