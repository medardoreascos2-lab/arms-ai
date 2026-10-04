"""P105E independent notification safety and scope regression matrix."""

from datetime import datetime, timedelta, timezone
import ast
from pathlib import Path

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


def build_fixture(tmp_path):
    owner = synthetic_customer_session(
        issued_at=NOW - timedelta(minutes=5),
        expires_at=NOW + timedelta(hours=1),
    )
    other_user = synthetic_customer_session(
        session_id="synthetic-session-2",
        user_id="synthetic-user-2",
        tenant_id=owner.tenant_id,
        issued_at=owner.issued_at,
        expires_at=owner.expires_at,
    )
    other_tenant = synthetic_customer_session(
        session_id="synthetic-session-3",
        user_id=owner.user_id,
        tenant_id="synthetic-tenant-2",
        issued_at=owner.issued_at,
        expires_at=owner.expires_at,
    )
    sessions = LocalSyntheticSessionProvider((owner, other_user, other_tenant))
    store = LocalSqliteNotificationStore(
        str(tmp_path / "security.sqlite3"),
        environment="LOCAL_TEST_ONLY",
    )
    owner_scope = NotificationScope(owner.tenant_id, owner.user_id)
    store.append(owner_scope, ProductNotification(
        notification_id="synthetic-critical-1",
        user_id=owner.user_id,
        tenant_id=owner.tenant_id,
        category=NotificationCategory.SECURITY,
        priority=NotificationPriority.CRITICAL,
        title="Critical synthetic notice",
        summary="Must remain tenant and user scoped.",
        source_type="SECURITY",
        source_reference="synthetic-event-1",
        created_at=NOW,
        requires_acknowledgement=True,
    ), "critical-seed")
    app = FastAPI()
    app.include_router(create_local_test_product_notification_router(
        session_provider=sessions,
        notification_store=store,
        clock=lambda: NOW + timedelta(minutes=10),
    ))
    return TestClient(app, client=("127.0.0.1", 50000)), store, owner_scope


def auth(session_id):
    return {"X-ARMS-Local-Test-Session": session_id}


def test_wrong_user_and_wrong_tenant_have_zero_read_or_mutation_access(tmp_path):
    client, store, owner_scope = build_fixture(tmp_path)
    for session_id in ("synthetic-session-2", "synthetic-session-3"):
        inbox = client.get(
            "/product/notifications", headers=auth(session_id),
        ).json()
        assert inbox["status"] == "READY"
        assert inbox["notifications"] == []
        transition = client.post(
            "/product/notifications/synthetic-critical-1/read",
            headers=auth(session_id),
        ).json()
        assert transition["status"] == "PERMISSION_BLOCKED"
    owner = store.get(owner_scope, "synthetic-critical-1")
    assert owner.status.value == "UNREAD"
    assert owner.priority is NotificationPriority.CRITICAL


def test_critical_priority_and_acknowledgement_survive_every_allowed_transition(tmp_path):
    client, _, _ = build_fixture(tmp_path)
    session = auth("synthetic-session-1")
    for action, status in (
        ("read", "READ"),
        ("snooze", "SNOOZED"),
        ("acknowledge", "ACKNOWLEDGED"),
        ("dismiss", "DISMISSED"),
    ):
        body = client.post(
            "/product/notifications/synthetic-critical-1/" + action,
            headers=session,
        ).json()
        item = body["notification"]
        assert item["status"] == status
        assert item["priority"] == "CRITICAL"
        assert item["requires_acknowledgement"] is True


def test_notification_modules_have_no_external_transport_or_financial_dependencies():
    paths = (
        Path("backend/product/notifications.py"),
        Path("backend/product/notification_store.py"),
        Path("backend/product/notification_preferences.py"),
        Path("backend/api/product_notification_api.py"),
    )
    forbidden_roots = {
        "requests", "httpx", "smtplib", "telegram", "twilio",
        "stripe", "broker", "execution", "portfolio",
    }
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = {
            node.names[0].name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
        }
        imports.update(
            node.module.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        )
        assert imports.isdisjoint(forbidden_roots), path


def test_every_api_shape_fixes_delivery_and_financial_authority_false(tmp_path):
    client, _, _ = build_fixture(tmp_path)
    session = auth("synthetic-session-1")
    inbox = client.get("/product/notifications", headers=session).json()
    transition = client.post(
        "/product/notifications/synthetic-critical-1/read",
        headers=session,
    ).json()
    for body in (inbox, transition):
        assert body["external_delivery_authorized"] is False
        assert body["financial_authority"] is False
        assert body["execution_authorized"] is False
        assert body["portfolio_mutation_authorized"] is False
