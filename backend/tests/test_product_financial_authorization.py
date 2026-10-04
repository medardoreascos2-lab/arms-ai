"""P104-PRE5 denied Product financial reads never reach the data provider."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from backend.entitlements import (
    AccountEntitlementLimits,
    DashboardAccess,
    FeatureEntitlement,
    SignalEntitlementLimits,
)
from backend.memberships import MembershipPlan, MembershipRecord, MembershipStatus
from backend.product.customer_session import LocalSyntheticSessionProvider, synthetic_customer_session
from backend.product.financial_access import CustomerFinancialAccessScope, ProductFinancialSurface
from backend.product.financial_authorization import (
    FinancialAccessCode,
    authorize_financial_read,
)


NOW = datetime(2026, 10, 4, 12, tzinfo=timezone.utc)
ENTITLEMENT = FeatureEntitlement.FINANCIAL_OVERVIEW


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


class DataProvider:
    def __init__(self):
        self.calls = 0

    def read(self, decision):
        if decision.allowed:
            self.calls += 1


def fixture(*, session_changes=None, membership_changes=None, session_features=None,
            membership_features=None, scope_changes=None):
    features = frozenset(
        {ENTITLEMENT} if session_features is None else session_features
    )
    session = synthetic_customer_session(
        issued_at=NOW - timedelta(minutes=5), expires_at=NOW + timedelta(minutes=30),
        entitlements=features,
    )
    if session_changes:
        session = replace(session, **session_changes)
    provider = LocalSyntheticSessionProvider((session,))
    plan = MembershipPlan(
        plan_id="PREMIUM", version="1",
        features=frozenset(
            {ENTITLEMENT} if membership_features is None else membership_features
        ),
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
    if membership_changes:
        record = replace(record, **membership_changes)
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
    if scope_changes:
        scope = replace(scope, **scope_changes)
    return session, provider, Memberships(record), Scopes(scope)


def authorize(parts, **overrides):
    session, provider, memberships, scopes = parts
    arguments = dict(
        session_id=session.session_id,
        session_provider=provider,
        membership_adapter=memberships,
        scope_provider=scopes,
        required_surface=ProductFinancialSurface.OVERVIEW,
        required_entitlement=ENTITLEMENT,
        evaluated_at=NOW,
    )
    arguments.update(overrides)
    return authorize_financial_read(**arguments)


def test_valid_trusted_scope_allows_one_read():
    decision = authorize(fixture())
    data = DataProvider()
    data.read(decision)
    assert decision.code == FinancialAccessCode.ALLOWED
    assert data.calls == 1


@pytest.mark.parametrize("case,expected", [
    ("expired", FinancialAccessCode.SESSION_INVALID),
    ("revoked", FinancialAccessCode.SESSION_INVALID),
    ("wrong_tenant", FinancialAccessCode.ENTITLEMENT_REQUIRED),
    ("wrong_user", FinancialAccessCode.ENTITLEMENT_REQUIRED),
    ("forged_account", FinancialAccessCode.ACCOUNT_SCOPE_UNAVAILABLE),
    ("forged_portfolio", FinancialAccessCode.PORTFOLIO_UNAVAILABLE),
    ("missing_session_entitlement", FinancialAccessCode.ENTITLEMENT_REQUIRED),
    ("missing_membership_entitlement", FinancialAccessCode.ENTITLEMENT_REQUIRED),
    ("inactive_membership", FinancialAccessCode.ENTITLEMENT_REQUIRED),
])
def test_denied_matrix_has_zero_data_provider_invocation(case, expected):
    parts = fixture(
        session_changes={"expires_at": NOW} if case == "expired" else None,
        membership_changes=(
            {"tenant_id": "synthetic-other-tenant"} if case == "wrong_tenant"
            else {"user_id": "synthetic-other-user"} if case == "wrong_user"
            else {"status": MembershipStatus.SUSPENDED} if case == "inactive_membership"
            else None
        ),
        session_features=set() if case == "missing_session_entitlement" else None,
        membership_features=set() if case == "missing_membership_entitlement" else None,
    )
    if case == "revoked":
        parts[1].revoke(parts[0].session_id)
    overrides = {}
    if case == "forged_account":
        overrides["requested_account_ref"] = "synthetic-attacker-account"
    if case == "forged_portfolio":
        overrides["requested_portfolio_ref"] = "synthetic-attacker-portfolio"
    decision = authorize(parts, **overrides)
    data = DataProvider()
    data.read(decision)
    assert decision.code == expected
    assert data.calls == 0
    assert decision.scope is None


@pytest.mark.parametrize("scope_changes", [
    {"tenant_id": "synthetic-other-tenant"},
    {"user_id": "synthetic-other-user"},
    {"customer_session_id": "synthetic-other-session"},
])
def test_mismatched_financial_scope_has_zero_data_provider_invocation(scope_changes):
    decision = authorize(fixture(scope_changes=scope_changes))
    data = DataProvider()
    data.read(decision)
    assert decision.code == FinancialAccessCode.ACCOUNT_SCOPE_UNAVAILABLE
    assert data.calls == 0
