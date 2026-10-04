"""P119C Product privacy regression across memory, financial, and analytics boundaries."""

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from backend.api.schemas.product_medar import ProductMedarPrompt
from backend.product.analytics_events import ProductAnalyticsEvent
from backend.product.customer_session import synthetic_customer_session
from backend.product.financial_access import CustomerFinancialAccessScope, ProductFinancialSurface
from backend.product.notification_store import NotificationScope
from backend.product.onboarding import LocalSqliteOnboardingStore, ProductOnboardingState
from backend.product.synthetic_financial_provider import LOCAL_TEST_ONLY, LocalSyntheticFinancialProvider


NOW = datetime(2026, 10, 4, 12, tzinfo=timezone.utc)


def onboarding(scope, consent):
    return ProductOnboardingState(
        onboarding_id=f"onboarding-{scope.user_id}", tenant_id=scope.tenant_id,
        user_id=scope.user_id, status="IN_PROGRESS", current_step="PRIVACY",
        completed_steps=("WELCOME", "GOALS", "FINANCIAL_EXPECTATIONS", "MEMORY_CONSENT"),
        goals_confirmed=True, memory_consent=consent, memory_consent_confirmed=True,
        version=1, created_at=NOW, updated_at=NOW,
    )


def test_memory_preferences_and_memory_input_are_user_scoped(tmp_path):
    first = NotificationScope("tenant-1", "user-1")
    second = NotificationScope("tenant-1", "user-2")
    store = LocalSqliteOnboardingStore(str(tmp_path / "onboarding.sqlite3"), environment="LOCAL_TEST_ONLY")
    store.save(first, onboarding(first, "DO_NOT_SAVE"), expected_version=None)
    store.save(second, onboarding(second, "ALLOW_LOW_SENSITIVITY"), expected_version=None)
    assert store.get(first).memory_consent.value == "DO_NOT_SAVE"
    assert store.get(second).memory_consent.value == "ALLOW_LOW_SENSITIVITY"
    with pytest.raises(ValidationError):
        ProductMedarPrompt(
            request_id="request-1", conversation_id="conversation-1", message="Hello",
            memory_content="another user's memory",
        )
    store.close()


def test_financial_provider_rejects_cross_tenant_scope_before_details():
    session = synthetic_customer_session(
        issued_at=NOW - timedelta(minutes=1), expires_at=NOW + timedelta(hours=1),
    )
    trusted = CustomerFinancialAccessScope(
        user_id=session.user_id, tenant_id=session.tenant_id,
        customer_session_id=session.session_id,
        financial_profile_id="synthetic-profile-1",
        account_refs=("synthetic-account-nq", "synthetic-account-mnq"),
        portfolio_refs=("synthetic-portfolio-1",),
        allowed_surfaces=frozenset(ProductFinancialSurface),
        issued_at=session.issued_at, expires_at=session.expires_at,
        source=LOCAL_TEST_ONLY,
    )
    provider = LocalSyntheticFinancialProvider(trusted, NOW)
    foreign = CustomerFinancialAccessScope(
        user_id="synthetic-other-user", tenant_id="synthetic-other-tenant",
        customer_session_id="synthetic-other-session",
        financial_profile_id="synthetic-other-profile",
        account_refs=trusted.account_refs, portfolio_refs=trusted.portfolio_refs,
        allowed_surfaces=trusted.allowed_surfaces,
        issued_at=trusted.issued_at, expires_at=trusted.expires_at,
        source=LOCAL_TEST_ONLY,
    )
    with pytest.raises(PermissionError):
        provider.get_portfolio_summary(foreign)


def test_private_analytics_content_is_rejected():
    base = {
        "event_id": "event-privacy-1", "pseudonymous_subject_id": "anon-1",
        "name": "feature_used", "target": "MEDAR", "occurred_at": NOW,
    }
    for field in ("conversation_text", "memory_content", "financial_positions", "private_messages"):
        with pytest.raises(ValidationError):
            ProductAnalyticsEvent.model_validate({**base, field: "private"})