"""P104-PRE8 degraded Product financial states are explicit and fail closed."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from backend.api.product_financial_local_test import (
    ProductFinancialLocalTestConfig,
    create_local_test_product_financial_app,
)
from backend.entitlements import (
    AccountEntitlementLimits,
    DashboardAccess,
    FeatureEntitlement,
    SignalEntitlementLimits,
)
from backend.memberships import MembershipPlan, MembershipRecord, MembershipStatus
from backend.product.customer_session import LocalSyntheticSessionProvider, synthetic_customer_session
from backend.product.financial_access import CustomerFinancialAccessScope, ProductFinancialSurface
from backend.product.financial_models import FinancialReadStatus, ProductFinancialDegradedResponse
from backend.product.synthetic_financial_provider import LocalSyntheticFinancialProvider


NOW = datetime(2026, 10, 4, 12, tzinfo=timezone.utc)
FEATURES = frozenset(FeatureEntitlement)


class Memberships:
    def __init__(self, record):
        self.record = record

    def get_membership(self, tenant_id, user_id):
        return self.record


class Scopes:
    def __init__(self, value):
        self.value = value

    def get_scope(self, session, evaluated_at):
        return self.value


def dependencies(*, observed_at=NOW):
    session = synthetic_customer_session(
        issued_at=NOW - timedelta(minutes=5), expires_at=NOW + timedelta(minutes=30),
        entitlements=FEATURES,
    )
    sessions = LocalSyntheticSessionProvider((session,))
    scope = CustomerFinancialAccessScope(
        user_id=session.user_id, tenant_id=session.tenant_id,
        customer_session_id=session.session_id,
        financial_profile_id="synthetic-financial-profile-1",
        account_refs=("synthetic-account-nq", "synthetic-account-mnq"),
        portfolio_refs=("synthetic-portfolio-1",),
        allowed_surfaces=frozenset(ProductFinancialSurface),
        issued_at=session.issued_at, expires_at=session.expires_at,
        source="LOCAL_TEST_ONLY",
    )
    plan = MembershipPlan(
        plan_id="PREMIUM", version="1", features=FEATURES,
        account_limits=AccountEntitlementLimits(2, 1),
        signal_limits=SignalEntitlementLimits(0),
        dashboard_access=DashboardAccess.READ_ONLY,
    )
    record = MembershipRecord(
        membership_id="synthetic-membership-1",
        tenant_id=session.tenant_id, user_id=session.user_id,
        plan=plan, status=MembershipStatus.ACTIVE,
        effective_from=NOW - timedelta(days=1),
        effective_until=NOW + timedelta(days=1),
        grace_ends_at=NOW + timedelta(days=2),
    )
    return sessions, Memberships(record), Scopes(scope), LocalSyntheticFinancialProvider(scope, observed_at)


def test_disabled_default_returns_integration_pending_without_synthetic_data():
    app = create_local_test_product_financial_app()
    client = TestClient(app, client=("127.0.0.1", 50000))
    for suffix in ("overview", "trading", "portfolio", "coach", "shadow"):
        body = client.get(f"/product/financial/{suffix}").json()
        assert body["status"] == "INTEGRATION_PENDING"
        assert body["data"] is None
        assert "SYNTHETIC" not in str(body)


def test_enabled_mode_requires_explicit_local_config_and_synthetic_dependencies():
    with pytest.raises(ValueError):
        ProductFinancialLocalTestConfig(True, "PRODUCTION")
    with pytest.raises(TypeError):
        create_local_test_product_financial_app(
            config=ProductFinancialLocalTestConfig(True, "LOCAL")
        )
    parts = dependencies()
    app = create_local_test_product_financial_app(
        config=ProductFinancialLocalTestConfig(True, "TEST"),
        session_provider=parts[0], membership_adapter=parts[1],
        scope_provider=parts[2], financial_provider=parts[3],
        clock=lambda: NOW,
    )
    response = TestClient(app, client=("127.0.0.1", 50000)).get(
        "/product/financial/trading",
        headers={"X-ARMS-Local-Test-Session": "synthetic-session-1"},
    )
    assert response.json()["source_status"] == "SYNTHETIC"


def test_stale_projection_returns_stale_data_without_projection_payload():
    parts = dependencies(observed_at=NOW - timedelta(minutes=10))
    app = create_local_test_product_financial_app(
        config=ProductFinancialLocalTestConfig(True, "LOCAL"),
        session_provider=parts[0], membership_adapter=parts[1],
        scope_provider=parts[2], financial_provider=parts[3],
        clock=lambda: NOW, maximum_freshness_seconds=300,
    )
    response = TestClient(app, client=("127.0.0.1", 50000)).get(
        "/product/financial/trading",
        headers={"X-ARMS-Local-Test-Session": "synthetic-session-1"},
    )
    assert response.json()["status"] == "STALE_DATA"
    assert response.json()["data"] is None


@pytest.mark.parametrize("status", list(FinancialReadStatus))
def test_degraded_response_has_zero_authority(status):
    response = ProductFinancialDegradedResponse(status=status)
    assert response.data is None
    assert response.broker_authorized is False
    assert response.portfolio_mutation_authorized is False
    assert response.paper_authorized is False
    assert response.live_authorized is False
