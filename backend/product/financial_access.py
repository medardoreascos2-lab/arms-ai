"""Trusted, read-only Product financial identity scope.

Financial references are resolved server-side and are never accepted as caller
authority. This module grants no account, portfolio, PAPER, LIVE, or broker mutation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import re

from backend.product.customer_session import CustomerSessionProvider, TrustedCustomerSession


_OPAQUE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


def _opaque(value: str, name: str) -> None:
    if not isinstance(value, str) or _OPAQUE_ID.fullmatch(value) is None:
        raise ValueError(f"{name} must be a safe opaque identifier")


def _utc(value: datetime, name: str) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{name} must be UTC")


class ProductFinancialSurface(str, Enum):
    OVERVIEW = "OVERVIEW"
    TRADING = "TRADING"
    PORTFOLIO = "PORTFOLIO"
    COACH = "COACH"
    SHADOW_MEDAR = "SHADOW_MEDAR"


@dataclass(frozen=True)
class CustomerFinancialAccessScope:
    user_id: str
    tenant_id: str
    customer_session_id: str
    financial_profile_id: str
    account_refs: tuple[str, ...]
    portfolio_refs: tuple[str, ...]
    allowed_surfaces: frozenset[ProductFinancialSurface]
    issued_at: datetime
    expires_at: datetime
    source: str
    broker_authorized: bool = field(default=False, init=False)
    portfolio_mutation_authorized: bool = field(default=False, init=False)
    paper_authorized: bool = field(default=False, init=False)
    live_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        for name in ("user_id", "tenant_id", "customer_session_id", "financial_profile_id", "source"):
            _opaque(getattr(self, name), name)
        for name in ("account_refs", "portfolio_refs"):
            values = getattr(self, name)
            if not isinstance(values, tuple) or not values or len(values) != len(set(values)):
                raise ValueError(f"{name} must be a nonempty unique tuple")
            for value in values:
                _opaque(value, name)
        if not isinstance(self.allowed_surfaces, frozenset) or not self.allowed_surfaces:
            raise ValueError("allowed_surfaces must be a nonempty immutable set")
        if any(not isinstance(item, ProductFinancialSurface) for item in self.allowed_surfaces):
            raise ValueError("invalid financial surface")
        _utc(self.issued_at, "issued_at")
        _utc(self.expires_at, "expires_at")
        if self.expires_at <= self.issued_at:
            raise ValueError("financial scope expiry must follow issuance")


def validate_customer_financial_scope(
    scope: CustomerFinancialAccessScope,
    session: TrustedCustomerSession,
    session_provider: CustomerSessionProvider,
    evaluated_at: datetime,
) -> bool:
    """Validate server-resolved scope against the current trusted session."""
    if not isinstance(scope, CustomerFinancialAccessScope):
        return False
    _utc(evaluated_at, "evaluated_at")
    try:
        if session_provider.validate_session(session.session_id, evaluated_at) is not session:
            return False
        identity = session_provider.resolve_identity(session, evaluated_at)
        tenant_id = session_provider.resolve_tenant(session, evaluated_at)
    except Exception:
        return False
    return (
        scope.user_id == identity.user_id == session.user_id
        and scope.tenant_id == tenant_id == identity.tenant_id == session.tenant_id
        and scope.customer_session_id == session.session_id
        and scope.issued_at <= evaluated_at < scope.expires_at
        and scope.issued_at >= session.issued_at
        and scope.expires_at <= session.expires_at
    )
