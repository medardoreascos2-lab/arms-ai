"""P104-PRE4 local synthetic financial provider tests."""

from datetime import datetime, timedelta, timezone

from backend.product.customer_session import synthetic_customer_session
from backend.product.financial_access import CustomerFinancialAccessScope, ProductFinancialSurface
from backend.product.financial_models import FinancialSourceStatus
from backend.product.synthetic_financial_provider import (
    LOCAL_TEST_ONLY,
    SYNTHETIC_WARNING,
    LocalSyntheticFinancialProvider,
)


NOW = datetime(2026, 10, 4, 12, tzinfo=timezone.utc)


def scope():
    session = synthetic_customer_session(
        issued_at=NOW - timedelta(minutes=5), expires_at=NOW + timedelta(minutes=30)
    )
    return CustomerFinancialAccessScope(
        user_id=session.user_id, tenant_id=session.tenant_id,
        customer_session_id=session.session_id,
        financial_profile_id="synthetic-financial-profile-1",
        account_refs=("synthetic-account-nq", "synthetic-account-mnq"),
        portfolio_refs=("synthetic-portfolio-1",),
        allowed_surfaces=frozenset(ProductFinancialSurface),
        issued_at=session.issued_at, expires_at=session.expires_at,
        source=LOCAL_TEST_ONLY,
    )


def test_synthetic_provider_returns_all_required_samples_with_explicit_labels():
    trusted = scope()
    provider = LocalSyntheticFinancialProvider(trusted, NOW)
    projections = (
        provider.get_trading_summary(trusted),
        provider.get_nq_summary(trusted),
        provider.get_mnq_summary(trusted),
        provider.get_portfolio_summary(trusted),
        provider.get_portfolio_risk(trusted),
        provider.get_trading_coach_summary(trusted),
        provider.get_shadow_medar_summary(trusted),
        provider.get_financial_alerts(trusted),
        provider.get_daily_financial_snapshot(trusted),
    )
    assert projections[1].instrument == "NQ"
    assert projections[2].instrument == "MNQ"
    for projection in projections:
        assert projection.source_status == FinancialSourceStatus.SYNTHETIC
        assert projection.provenance.classification == "SYNTHETIC"
        assert SYNTHETIC_WARNING in projection.warnings
        assert projection.execution_authorized is False
        assert projection.portfolio_mutation_authorized is False


def test_synthetic_provider_has_no_network_or_mutation_configuration():
    provider = LocalSyntheticFinancialProvider(scope(), NOW)
    state = vars(provider)
    assert set(state) == {"_scope", "_observed_at", "calls"}
    assert not set(state).intersection({
        "url", "endpoint", "client", "broker", "exchange", "credential", "password", "token",
    })
    assert "http://" not in repr(state) and "https://" not in repr(state)


def test_provider_rejects_equal_but_unissued_scope_and_out_of_scope_refs():
    trusted = scope()
    provider = LocalSyntheticFinancialProvider(trusted, NOW)
    copy = CustomerFinancialAccessScope(**{
        name: getattr(trusted, name) for name in (
            "user_id", "tenant_id", "customer_session_id", "financial_profile_id",
            "account_refs", "portfolio_refs", "allowed_surfaces", "issued_at", "expires_at", "source",
        )
    })
    try:
        provider.get_nq_summary(copy)
        assert False, "unissued scope must fail"
    except PermissionError:
        pass
