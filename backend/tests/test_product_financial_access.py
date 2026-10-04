"""P104-PRE1 trusted Product financial identity scope."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from backend.product.customer_session import LocalSyntheticSessionProvider, synthetic_customer_session
from backend.product.financial_access import (
    CustomerFinancialAccessScope,
    ProductFinancialSurface,
    validate_customer_financial_scope,
)


NOW = datetime(2026, 10, 4, 12, tzinfo=timezone.utc)


def fixture():
    session = synthetic_customer_session(
        issued_at=NOW - timedelta(minutes=5), expires_at=NOW + timedelta(minutes=30)
    )
    provider = LocalSyntheticSessionProvider((session,))
    scope = CustomerFinancialAccessScope(
        user_id=session.user_id,
        tenant_id=session.tenant_id,
        customer_session_id=session.session_id,
        financial_profile_id="synthetic-financial-profile-1",
        account_refs=("synthetic-account-nq", "synthetic-account-mnq"),
        portfolio_refs=("synthetic-portfolio-1",),
        allowed_surfaces=frozenset(ProductFinancialSurface),
        issued_at=session.issued_at,
        expires_at=session.expires_at,
        source="LOCAL_TEST_ONLY",
    )
    return session, provider, scope


def test_scope_is_read_only_and_bound_to_trusted_session_identity():
    session, provider, scope = fixture()
    assert validate_customer_financial_scope(scope, session, provider, NOW)
    assert scope.broker_authorized is False
    assert scope.portfolio_mutation_authorized is False
    assert scope.paper_authorized is False
    assert scope.live_authorized is False


@pytest.mark.parametrize("field,value", [
    ("user_id", "synthetic-attacker"),
    ("tenant_id", "synthetic-other-tenant"),
    ("customer_session_id", "synthetic-other-session"),
    ("financial_profile_id", "bad value"),
])
def test_scope_rejects_forged_identity_or_invalid_profile(field, value):
    session, provider, scope = fixture()
    if field == "financial_profile_id":
        with pytest.raises(ValueError):
            replace(scope, **{field: value})
    else:
        assert not validate_customer_financial_scope(
            replace(scope, **{field: value}), session, provider, NOW
        )


def test_expired_or_revoked_session_invalidates_financial_scope():
    session, provider, scope = fixture()
    assert not validate_customer_financial_scope(scope, session, provider, scope.expires_at)
    provider.revoke(session.session_id)
    assert not validate_customer_financial_scope(scope, session, provider, NOW)


def test_references_and_surfaces_are_nonempty_unique_server_scope():
    _, _, scope = fixture()
    for changes in (
        {"account_refs": ()},
        {"portfolio_refs": ()},
        {"account_refs": ("synthetic-account-nq", "synthetic-account-nq")},
        {"allowed_surfaces": frozenset()},
    ):
        with pytest.raises(ValueError):
            replace(scope, **changes)
