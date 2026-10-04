"""Local Product MEDAR requests must authorize before any cognitive invocation."""

from dataclasses import replace
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
from backend.medar.response import CognitiveResponse, ResponseStatus
from backend.memberships import (
    MembershipPlan, MembershipRecord, MembershipStatus,
    resolve_membership_entitlements,
)
from backend.product.customer_session import LocalSyntheticSessionProvider, synthetic_customer_session
from backend.product.surface import ProductDecisionCode, ProductSurface, ProductTier, resolve_product_access
from backend.product.medar_usage import ProductMedarLimits, ProductMedarUsageGate


NOW = datetime(2026, 10, 4, 12, tzinfo=timezone.utc)
BODY = {
    "request_id": "request-1",
    "conversation_id": "conversation-1",
    "message": "Explain the evidence.",
}


class Memberships:
    def __init__(self, record):
        self.record = record
        self.reads = 0

    def get_membership(self, tenant_id, user_id):
        self.reads += 1
        return self.record


class Runtime:
    def __init__(self):
        self.calls = 0
        self.memory_reads = 0
        self.model_calls = 0
        self.tool_calls = 0
        self.invocation = None

    def invoke(self, invocation):
        self.calls += 1
        self.invocation = invocation
        return CognitiveResponse(
            response_id="response-1",
            request_id=invocation.request.request_id,
            status=ResponseStatus.SUCCESS,
            answer="A supported result.",
            confidence=0.8,
            reasoning_summary="Local evidence was reviewed.",
        )


def fixture(*, session_changes=None, membership_changes=None, features=None, runtime=True, usage_gate=None):
    source = synthetic_customer_session(
        issued_at=NOW - timedelta(minutes=1),
        expires_at=NOW + timedelta(minutes=15),
    )
    if session_changes:
        source = replace(source, **session_changes)
    provider = LocalSyntheticSessionProvider((source,))
    plan = MembershipPlan(
        plan_id="PREMIUM", version="1",
        features=frozenset(features if features is not None else {
            FeatureEntitlement.DASHBOARD, FeatureEntitlement.MEDAR_CONVERSATION,
        }),
        account_limits=AccountEntitlementLimits(0, 0),
        signal_limits=SignalEntitlementLimits(0),
        dashboard_access=DashboardAccess.READ_ONLY,
    )
    record = MembershipRecord(
        membership_id="synthetic-membership-1",
        user_id=source.user_id, tenant_id=source.tenant_id,
        plan=plan, status=MembershipStatus.ACTIVE,
        effective_from=NOW - timedelta(days=1),
        effective_until=NOW + timedelta(days=1),
        grace_ends_at=NOW + timedelta(days=1),
    )
    if membership_changes:
        record = replace(record, **membership_changes)
    memberships = Memberships(record)
    medar = Runtime()
    app = FastAPI()
    app.include_router(create_local_test_product_medar_router(
        session_provider=provider, membership_adapter=memberships,
        runtime=medar if runtime else None, usage_gate=usage_gate, clock=lambda: NOW,
    ))
    client = TestClient(app, client=("127.0.0.1", 50000))
    return client, provider, memberships, medar


def post(client, *, session_id="synthetic-session-1", body=None):
    headers = {} if session_id is None else {"X-ARMS-Local-Test-Session": session_id}
    return client.post("/product/medar/conversations", json=body or BODY, headers=headers)


def assert_no_invocation(runtime):
    assert (runtime.calls, runtime.memory_reads, runtime.model_calls, runtime.tool_calls) == (0, 0, 0, 0)


@pytest.mark.parametrize("session_id", [None, "unknown", "synthetic-other-tenant-session"])
def test_missing_or_unknown_session_denied_before_membership_or_medar(session_id):
    client, _, memberships, runtime = fixture()
    response = post(client, session_id=session_id)
    assert response.status_code == 200
    assert response.json()["status"] == "PERMISSION_DENIED"
    assert memberships.reads == 0
    assert_no_invocation(runtime)


def test_expired_and_revoked_sessions_have_zero_invocation():
    client, provider, memberships, runtime = fixture(
        session_changes={"expires_at": NOW}
    )
    assert post(client).json()["status"] == "PERMISSION_DENIED"
    assert memberships.reads == 0
    assert_no_invocation(runtime)
    client, provider, memberships, runtime = fixture()
    provider.revoke("synthetic-session-1")
    assert post(client).json()["status"] == "PERMISSION_DENIED"
    assert memberships.reads == 0
    assert_no_invocation(runtime)


@pytest.mark.parametrize("membership_changes", [
    {"user_id": "synthetic-other-user"},
    {"tenant_id": "synthetic-other-tenant"},
    {"status": MembershipStatus.SUSPENDED},
])
def test_wrong_identity_or_inactive_membership_has_zero_invocation(membership_changes):
    client, _, memberships, runtime = fixture(membership_changes=membership_changes)
    assert post(client).json()["status"] == "ENTITLEMENT_REQUIRED"
    assert memberships.reads == 1
    assert_no_invocation(runtime)


def test_missing_entitlement_in_session_or_membership_has_zero_invocation():
    client, _, _, runtime = fixture(session_changes={"entitlements": frozenset()})
    assert post(client).json()["status"] == "ENTITLEMENT_REQUIRED"
    assert_no_invocation(runtime)
    client, _, _, runtime = fixture(features={FeatureEntitlement.DASHBOARD})
    assert post(client).json()["status"] == "ENTITLEMENT_REQUIRED"
    assert_no_invocation(runtime)


def test_unavailable_runtime_and_identity_override_have_zero_invocation():
    client, _, _, runtime = fixture(runtime=False)
    assert post(client).json()["status"] == "MEDAR_UNAVAILABLE"
    assert_no_invocation(runtime)
    client, _, memberships, runtime = fixture()
    for field in ("user_id", "tenant_id", "session_id"):
        response = post(client, body={**BODY, field: "synthetic-attacker"})
        assert response.status_code == 422
    assert memberships.reads == 0
    assert_no_invocation(runtime)


def test_valid_session_invokes_once_with_only_provider_derived_scope():
    client, _, _, runtime = fixture()
    response = post(client)
    assert response.status_code == 200
    assert response.json()["status"] == "SUCCESS"
    assert runtime.calls == 1
    invocation = runtime.invocation
    assert (invocation.user_id, invocation.tenant_id, invocation.session_id) == (
        "synthetic-user-1", "synthetic-tenant-1", "synthetic-session-1",
    )
    assert invocation.auth_source == "LOCAL_TEST_ONLY"
    assert invocation.authentication_method == "SYNTHETIC_FIXTURE"
    assert invocation.request.requires_memory is False
    assert invocation.request.requires_tools is False
    assert invocation.request.requires_web is False


def test_nonloopback_peer_is_denied_before_membership_or_medar():
    client, _, memberships, runtime = fixture()
    client = TestClient(client.app, client=("203.0.113.1", 50000))
    assert post(client).json()["status"] == "PERMISSION_DENIED"
    assert memberships.reads == 0
    assert_no_invocation(runtime)


def test_projection_is_available_local_test_only_with_all_gates():
    client, provider, memberships, runtime = fixture()
    session = provider.validate_session("synthetic-session-1", NOW)
    identity = provider.resolve_identity(session, NOW)
    projection = resolve_membership_entitlements(
        memberships, identity, provider.resolve_roles(session, NOW), NOW
    )
    access = resolve_product_access(
        projection, customer_session=session, session_provider=provider,
        evaluated_at=NOW, medar_runtime_available=True,
    )
    assert access.decisions[ProductSurface.MEDAR].code == ProductDecisionCode.AVAILABLE_LOCAL_TEST
    assert access.paper_authorized is False
    assert access.live_authorized is False
    assert_no_invocation(runtime)


def test_grace_membership_and_unavailable_membership_adapter_fail_closed():
    client, _, _, runtime = fixture(membership_changes={
        "effective_until": NOW - timedelta(minutes=1),
        "grace_ends_at": NOW + timedelta(days=1),
    })
    assert post(client).json()["status"] == "ENTITLEMENT_REQUIRED"
    assert_no_invocation(runtime)

    client, _, memberships, runtime = fixture()
    memberships.get_membership = lambda tenant_id, user_id: None
    assert post(client).json()["status"] == "ENTITLEMENT_REQUIRED"
    assert_no_invocation(runtime)


def test_usage_input_rate_and_output_limits_fail_closed():
    input_gate = ProductMedarUsageGate({
        ProductTier.PREMIUM: ProductMedarLimits(2, 3600, 1, 4, 16384)
    })
    client, _, _, runtime = fixture(usage_gate=input_gate)
    assert post(client).json()["status"] == "INVALID_REQUEST"
    assert_no_invocation(runtime)

    rate_gate = ProductMedarUsageGate({
        ProductTier.PREMIUM: ProductMedarLimits(1, 3600, 1, 8192, 16384)
    })
    client, _, _, runtime = fixture(usage_gate=rate_gate)
    assert post(client).json()["status"] == "SUCCESS"
    assert post(client).json()["status"] == "RATE_LIMITED"
    assert runtime.calls == 1

    output_gate = ProductMedarUsageGate({
        ProductTier.PREMIUM: ProductMedarLimits(2, 3600, 1, 8192, 10)
    })
    client, _, _, runtime = fixture(usage_gate=output_gate)
    response = post(client).json()
    assert response["status"] == "MEDAR_UNAVAILABLE"
    assert response["answer"] is None
    assert runtime.calls == 1


def test_concurrent_limit_and_unconfigured_plan_have_zero_invocation():
    gate = ProductMedarUsageGate({
        ProductTier.PREMIUM: ProductMedarLimits(2, 3600, 1, 8192, 16384)
    })
    assert gate.acquire(
        session_id="synthetic-session-1", tier=ProductTier.PREMIUM,
        entitlements=frozenset({FeatureEntitlement.MEDAR_CONVERSATION}),
        input_chars=3, at=NOW,
    ).allowed
    client, _, _, runtime = fixture(usage_gate=gate)
    assert post(client).json()["status"] == "RATE_LIMITED"
    assert_no_invocation(runtime)
    gate.release("synthetic-session-1")

    client, _, _, runtime = fixture(usage_gate=ProductMedarUsageGate({}))
    assert post(client).json()["status"] == "ENTITLEMENT_REQUIRED"
    assert_no_invocation(runtime)
