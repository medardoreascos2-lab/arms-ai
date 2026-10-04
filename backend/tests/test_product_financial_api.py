"""P104-PRE7 Product financial API remains trusted, scoped, and GET-only."""

from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.product_financial_api import create_local_test_product_financial_router
from backend.entitlements import (
    AccountEntitlementLimits,
    DashboardAccess,
    FeatureEntitlement,
    SignalEntitlementLimits,
)
from backend.memberships import MembershipPlan, MembershipRecord, MembershipStatus
from backend.product.customer_session import LocalSyntheticSessionProvider, synthetic_customer_session
from backend.product.financial_access import CustomerFinancialAccessScope, ProductFinancialSurface
from backend.product.synthetic_financial_provider import LocalSyntheticFinancialProvider


NOW = datetime(2026, 10, 4, 12, tzinfo=timezone.utc)
FEATURES = frozenset({
    FeatureEntitlement.FINANCIAL_OVERVIEW,
    FeatureEntitlement.TRADING_WORKSPACE,
    FeatureEntitlement.PORTFOLIO_GUARDIAN,
    FeatureEntitlement.TRADING_COACH,
    FeatureEntitlement.SHADOW_MEDAR,
})


class Memberships:
    def __init__(self, record):
        self.record = record

    def get_membership(self, tenant_id, user_id):
        return self.record


class Scopes:
    def __init__(self, scope):
        self.scope = scope

    def get_scope(self, session, evaluated_at):
        return self.scope


def fixture(features=FEATURES):
    session = synthetic_customer_session(
        issued_at=NOW - timedelta(minutes=5), expires_at=NOW + timedelta(minutes=30),
        entitlements=frozenset(features),
    )
    sessions = LocalSyntheticSessionProvider((session,))
    plan = MembershipPlan(
        plan_id="PREMIUM", version="1", features=frozenset(features),
        account_limits=AccountEntitlementLimits(2, 1),
        signal_limits=SignalEntitlementLimits(0),
        dashboard_access=DashboardAccess.READ_ONLY,
    )
    membership = MembershipRecord(
        membership_id="synthetic-membership-1",
        tenant_id=session.tenant_id, user_id=session.user_id,
        plan=plan, status=MembershipStatus.ACTIVE,
        effective_from=NOW - timedelta(days=1),
        effective_until=NOW + timedelta(days=1),
        grace_ends_at=NOW + timedelta(days=2),
    )
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
    financial = LocalSyntheticFinancialProvider(scope, NOW)
    app = FastAPI()
    app.include_router(create_local_test_product_financial_router(
        session_provider=sessions,
        membership_adapter=Memberships(membership),
        scope_provider=Scopes(scope),
        financial_provider=financial,
        clock=lambda: NOW,
    ))
    return TestClient(app, client=("127.0.0.1", 50000)), financial


def test_all_product_financial_routes_are_get_only_and_return_provenance():
    client, financial = fixture()
    paths = {
        "/product/financial/overview",
        "/product/financial/trading",
        "/product/financial/portfolio",
        "/product/financial/coach",
        "/product/financial/shadow",
    }
    for path in paths:
        response = client.get(path, headers={
            "X-ARMS-Local-Test-Session": "synthetic-session-1",
        })
        assert response.status_code == 200
        body = response.json()
        assert body["source_status"] == "SYNTHETIC"
        assert body["provenance"]["freshness_seconds"] == 0
        assert body["execution_authorized"] is False
        assert body["portfolio_mutation_authorized"] is False
        assert client.post(path).status_code == 405
    for path in paths:
        assert set(client.app.openapi()["paths"][path]) == {"get"}
    assert sum(financial.calls.values()) >= len(paths)


def test_caller_scope_parameters_never_override_trusted_scope():
    client, _ = fixture()
    response = client.get(
        "/product/financial/trading",
        params={
            "user_id": "synthetic-attacker",
            "tenant_id": "synthetic-other",
            "account_ref": "synthetic-attacker-account",
            "portfolio_ref": "synthetic-attacker-portfolio",
        },
        headers={"X-ARMS-Local-Test-Session": "synthetic-session-1"},
    )
    assert response.status_code == 200
    assert response.json()["account_ref"] == "synthetic-account-nq"


def test_missing_entitlement_or_session_has_zero_provider_invocation():
    client, financial = fixture(features={
        FeatureEntitlement.FINANCIAL_OVERVIEW,
    })
    response = client.get(
        "/product/financial/trading",
        headers={"X-ARMS-Local-Test-Session": "synthetic-session-1"},
    )
    assert response.json()["status"] == "ENTITLEMENT_REQUIRED"
    assert sum(financial.calls.values()) == 0
    response = client.get("/product/financial/overview")
    assert response.json()["status"] == "SESSION_INVALID"
    assert sum(financial.calls.values()) == 0
