"""Fail-closed authorization for Product financial read operations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Protocol

from backend.entitlements import FeatureEntitlement, UserIdentity
from backend.memberships import (
    MembershipLifecycleState,
    MembershipReadAdapter,
    MembershipResolutionCode,
    resolve_membership_entitlements,
)
from backend.product.customer_session import CustomerSessionProvider, TrustedCustomerSession
from backend.product.financial_access import (
    CustomerFinancialAccessScope,
    ProductFinancialSurface,
    validate_customer_financial_scope,
)


class FinancialAccessCode(str, Enum):
    ALLOWED = "ALLOWED"
    SESSION_INVALID = "SESSION_INVALID"
    ENTITLEMENT_REQUIRED = "ENTITLEMENT_REQUIRED"
    ACCOUNT_SCOPE_UNAVAILABLE = "ACCOUNT_SCOPE_UNAVAILABLE"
    PORTFOLIO_UNAVAILABLE = "PORTFOLIO_UNAVAILABLE"


class CustomerFinancialScopeProvider(Protocol):
    def get_scope(
        self, session: TrustedCustomerSession, evaluated_at: datetime
    ) -> CustomerFinancialAccessScope | None: ...


@dataclass(frozen=True)
class FinancialAccessDecision:
    allowed: bool
    code: FinancialAccessCode
    scope: CustomerFinancialAccessScope | None = None

    def __post_init__(self) -> None:
        if self.allowed != (self.code == FinancialAccessCode.ALLOWED):
            raise ValueError("financial access code must match allowed state")
        if self.allowed != (self.scope is not None):
            raise ValueError("only allowed financial access may carry scope")


def _denied(code: FinancialAccessCode) -> FinancialAccessDecision:
    return FinancialAccessDecision(False, code)


def authorize_financial_read(
    *,
    session_id: str | None,
    session_provider: CustomerSessionProvider,
    membership_adapter: MembershipReadAdapter,
    scope_provider: CustomerFinancialScopeProvider,
    required_surface: ProductFinancialSurface,
    required_entitlement: FeatureEntitlement,
    evaluated_at: datetime,
    requested_account_ref: str | None = None,
    requested_portfolio_ref: str | None = None,
) -> FinancialAccessDecision:
    """Resolve all identity and scope authority server-side before a data read."""
    try:
        session = session_provider.validate_session(session_id, evaluated_at)
        if session is None:
            return _denied(FinancialAccessCode.SESSION_INVALID)
        identity = session_provider.resolve_identity(session, evaluated_at)
        roles = session_provider.resolve_roles(session, evaluated_at)
        entitlements = session_provider.resolve_entitlements(session, evaluated_at)
        tenant_id = session_provider.resolve_tenant(session, evaluated_at)
        if (
            not isinstance(identity, UserIdentity)
            or identity.user_id != session.user_id
            or identity.tenant_id != session.tenant_id
            or tenant_id != session.tenant_id
            or roles != session.roles
            or entitlements != session.entitlements
        ):
            return _denied(FinancialAccessCode.SESSION_INVALID)
    except Exception:
        return _denied(FinancialAccessCode.SESSION_INVALID)

    projection = resolve_membership_entitlements(
        membership_adapter, identity, roles, evaluated_at
    )
    if (
        projection.code != MembershipResolutionCode.ENTITLED
        or projection.lifecycle_state != MembershipLifecycleState.ACTIVE
        or projection.profile is None
        or projection.profile.identity != identity
        or required_entitlement not in entitlements
        or required_entitlement not in projection.profile.features
    ):
        return _denied(FinancialAccessCode.ENTITLEMENT_REQUIRED)

    try:
        scope = scope_provider.get_scope(session, evaluated_at)
    except Exception:
        scope = None
    if (
        scope is None
        or not validate_customer_financial_scope(
            scope, session, session_provider, evaluated_at
        )
        or required_surface not in scope.allowed_surfaces
    ):
        return _denied(FinancialAccessCode.ACCOUNT_SCOPE_UNAVAILABLE)
    if requested_account_ref is not None and requested_account_ref not in scope.account_refs:
        return _denied(FinancialAccessCode.ACCOUNT_SCOPE_UNAVAILABLE)
    if requested_portfolio_ref is not None and requested_portfolio_ref not in scope.portfolio_refs:
        return _denied(FinancialAccessCode.PORTFOLIO_UNAVAILABLE)
    return FinancialAccessDecision(True, FinancialAccessCode.ALLOWED, scope)
