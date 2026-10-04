"""P118A synthetic new-user Product rehearsal across session and customer surfaces."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend.product.customer_session import LocalSyntheticSessionProvider, synthetic_customer_session
from backend.product.notification_store import LocalSqliteNotificationStore, NotificationScope
from backend.product.notifications import ProductNotification
from backend.product.onboarding import (
    LocalSqliteOnboardingStore,
    OnboardingStep,
    ProductOnboardingState,
)


NOW = datetime(2026, 10, 4, 12, tzinfo=timezone.utc)
ROOT = Path(__file__).parents[2]


def test_synthetic_new_user_reaches_product_surfaces_without_execution(tmp_path):
    session = synthetic_customer_session(
        issued_at=NOW - timedelta(minutes=1),
        expires_at=NOW + timedelta(hours=1),
    )
    sessions = LocalSyntheticSessionProvider((session,))
    trusted = sessions.validate_session(session.session_id, NOW)
    assert trusted is session
    scope = NotificationScope(trusted.tenant_id, trusted.user_id)

    onboarding = ProductOnboardingState(
        onboarding_id="synthetic-onboarding-e2e",
        tenant_id=scope.tenant_id,
        user_id=scope.user_id,
        status="COMPLETED",
        current_step="DONE",
        completed_steps=tuple(OnboardingStep),
        selected_goals=("TRADING", "PORTFOLIO", "LEARNING"),
        goals_confirmed=True,
        memory_consent="DO_NOT_SAVE",
        memory_consent_confirmed=True,
        version=1,
        created_at=NOW,
        updated_at=NOW,
    )
    onboarding_store = LocalSqliteOnboardingStore(
        str(tmp_path / "onboarding.sqlite3"), environment="LOCAL_TEST_ONLY",
    )
    onboarding_store.save(scope, onboarding, expected_version=None)
    assert onboarding_store.get(scope).memory_consent.value == "DO_NOT_SAVE"

    notifications = LocalSqliteNotificationStore(
        str(tmp_path / "notifications.sqlite3"), environment="LOCAL_TEST_ONLY",
    )
    notification = ProductNotification(
        notification_id="synthetic-welcome-e2e",
        tenant_id=scope.tenant_id,
        user_id=scope.user_id,
        category="SYSTEM",
        priority="INFO",
        title="Welcome",
        summary="Synthetic local rehearsal only.",
        source_type="PRODUCT",
        source_reference="synthetic-onboarding-e2e",
        created_at=NOW,
    )
    notifications.append(scope, notification, "synthetic-request-e2e")
    assert notifications.list(scope) == (notification,)

    route_files = (
        "frontend/src/app/product/page.tsx",
        "frontend/src/app/product/medar/page.tsx",
        "frontend/src/app/product/daily-intelligence/page.tsx",
        "frontend/src/app/product/trading/page.tsx",
        "frontend/src/app/product/coach/page.tsx",
        "frontend/src/app/product/portfolio/page.tsx",
        "frontend/src/app/product/notifications/page.tsx",
    )
    assert all((ROOT / route).is_file() for route in route_files)

    # This rehearsal performs state setup and reads only. No execution service is present.
    assert "execution" not in ProductOnboardingState.model_fields
    assert "broker" not in ProductNotification.model_fields
    onboarding_store.close()
    notifications.close()