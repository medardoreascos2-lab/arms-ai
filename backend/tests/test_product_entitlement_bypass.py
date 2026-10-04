"""P119B Product entitlement bypass attempts must fail before MEDAR invocation."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.product_medar_api import create_local_test_product_medar_router
from backend.entitlements import (
    AccountEntitlementLimits,
    DashboardAccess,
    FeatureEntitlement,
    SignalEntitlementLimits,
)
from backend.memberships import MembershipPlan, MembershipRecord, MembershipStatus
from backend.product.customer_session import LocalSyntheticSessionProvider, synthetic_customer_session


NOW = datetime(2026, 10, 4, 12, tzinfo=timezone.utc)
BODY = {"request_id": "bypass-1", "conversation_id": "conversation-1", "message": "Explain."}


class Memberships:
    def __init__(self, record):
        self.record = record

    def get_membership(self, tenant_id, user_id):
        return self.record


class Runtime:
    def __init__(self):
        self.calls = 0

    def readiness(self):
        return None

    def invoke(self, invocation):
        self.calls += 1
        raise AssertionError("denied bypass reached MEDAR")


def client_with_unentitled_membership():
    session = synthetic_customer_session(
        issued_at=NOW - timedelta(minutes=1), expires_at=NOW + timedelta(hours=1),
        entitlements=frozenset({FeatureEntitlement.MEDAR_CONVERSATION}),
    )
    sessions = LocalSyntheticSessionProvider((session,))
    plan = MembershipPlan(
        plan_id="FREE", version="1", features=frozenset({FeatureEntitlement.DASHBOARD}),
        account_limits=AccountEntitlementLimits(0, 0),
        signal_limits=SignalEntitlementLimits(0),
        dashboard_access=DashboardAccess.READ_ONLY,
    )
    membership = MembershipRecord(
        membership_id="synthetic-free-membership", tenant_id=session.tenant_id,
        user_id=session.user_id, plan=plan, status=MembershipStatus.ACTIVE,
        effective_from=NOW - timedelta(days=1), effective_until=NOW + timedelta(days=1),
        grace_ends_at=NOW + timedelta(days=1),
    )
    runtime = Runtime()
    app = FastAPI()
    app.include_router(create_local_test_product_medar_router(
        session_provider=sessions,
        membership_adapter=Memberships(membership),
        runtime=runtime,
        clock=lambda: NOW,
    ))
    return TestClient(app, client=("127.0.0.1", 50000)), runtime


def test_direct_url_and_frontend_plan_spoof_cannot_bypass_backend_entitlement():
    client, runtime = client_with_unentitled_membership()
    direct = client.post("/product/medar/conversations", json=BODY)
    assert direct.json()["status"] == "SESSION_INVALID"

    spoofed = client.post(
        "/product/medar/conversations",
        json=BODY,
        headers={
            "X-ARMS-Local-Test-Session": "synthetic-session-1",
            "X-Product-Plan": "ELITE",
            "X-Product-Entitled": "true",
        },
    )
    assert spoofed.json()["status"] == "ENTITLEMENT_REQUIRED"
    assert runtime.calls == 0


@pytest.mark.parametrize("field", ["plan_id", "tenant_id", "user_id", "session_id", "entitlements"])
def test_body_plan_tenant_session_and_entitlement_spoofs_are_rejected(field):
    client, runtime = client_with_unentitled_membership()
    response = client.post(
        "/product/medar/conversations",
        json={**BODY, field: "synthetic-attacker"},
        headers={"X-ARMS-Local-Test-Session": "synthetic-session-1"},
    )
    assert response.status_code == 422
    assert runtime.calls == 0