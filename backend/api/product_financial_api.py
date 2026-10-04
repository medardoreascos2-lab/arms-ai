"""Explicit local-test Product financial GET API.

The default ARMS application does not mount this router. It exposes read projections
only and derives all identity, entitlement, account, and portfolio scope server-side.
"""

from __future__ import annotations

from datetime import datetime, timezone
from ipaddress import ip_address
from typing import Callable

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.entitlements import FeatureEntitlement
from backend.memberships import MembershipReadAdapter
from backend.product.customer_session import CustomerSessionProvider
from backend.product.financial_access import ProductFinancialSurface
from backend.product.financial_authorization import (
    CustomerFinancialScopeProvider,
    FinancialAccessCode,
    authorize_financial_read,
)
from backend.product.financial_provider import ProductFinancialReadProvider
from backend.product.financial_models import (
    FinancialReadStatus,
    ProductFinancialDegradedResponse,
)



_ROUTE_POLICY = {
    "overview": (
        ProductFinancialSurface.OVERVIEW,
        FeatureEntitlement.FINANCIAL_OVERVIEW,
        "get_daily_financial_snapshot",
    ),
    "trading": (
        ProductFinancialSurface.TRADING,
        FeatureEntitlement.TRADING_WORKSPACE,
        "get_trading_summary",
    ),
    "portfolio": (
        ProductFinancialSurface.PORTFOLIO,
        FeatureEntitlement.PORTFOLIO_GUARDIAN,
        "get_portfolio_summary",
    ),
    "coach": (
        ProductFinancialSurface.COACH,
        FeatureEntitlement.TRADING_COACH,
        "get_trading_coach_summary",
    ),
    "shadow": (
        ProductFinancialSurface.SHADOW_MEDAR,
        FeatureEntitlement.SHADOW_MEDAR,
        "get_shadow_medar_summary",
    ),
}


def _degraded(status: FinancialReadStatus) -> JSONResponse:
    body = ProductFinancialDegradedResponse(status=status)
    return JSONResponse(body.model_dump(mode="json"))

_ACCESS_STATUS = {
    FinancialAccessCode.SESSION_INVALID: FinancialReadStatus.SESSION_INVALID,
    FinancialAccessCode.ENTITLEMENT_REQUIRED: FinancialReadStatus.ENTITLEMENT_REQUIRED,
    FinancialAccessCode.ACCOUNT_SCOPE_UNAVAILABLE: FinancialReadStatus.ACCOUNT_SCOPE_UNAVAILABLE,
    FinancialAccessCode.PORTFOLIO_UNAVAILABLE: FinancialReadStatus.PORTFOLIO_UNAVAILABLE,
}


def create_local_test_product_financial_router(
    *,
    session_provider: CustomerSessionProvider,
    membership_adapter: MembershipReadAdapter,
    scope_provider: CustomerFinancialScopeProvider,
    financial_provider: ProductFinancialReadProvider,
    maximum_freshness_seconds: int = 300,
    clock: Callable[[], datetime] | None = None,
) -> APIRouter:
    if any(item is None for item in (
        session_provider, membership_adapter, scope_provider, financial_provider
    )):
        raise TypeError("all Product financial read dependencies are required")
    if type(maximum_freshness_seconds) is not int or maximum_freshness_seconds < 0:
        raise ValueError("maximum freshness must be a nonnegative integer")
    now = clock or (lambda: datetime.now(timezone.utc))
    router = APIRouter(prefix="/product/financial", tags=["product-financial-local-test"])

    def read(
        route_name: str,
        request: Request,
        session_id: str | None,
    ) -> BaseModel | JSONResponse:
        try:
            peer = ip_address(request.client.host if request.client else "")
        except ValueError:
            return _degraded(FinancialReadStatus.SESSION_INVALID)
        if not peer.is_loopback:
            return _degraded(FinancialReadStatus.SESSION_INVALID)
        surface, entitlement, method_name = _ROUTE_POLICY[route_name]
        evaluated_at = now()
        decision = authorize_financial_read(
            session_id=session_id,
            session_provider=session_provider,
            membership_adapter=membership_adapter,
            scope_provider=scope_provider,
            required_surface=surface,
            required_entitlement=entitlement,
            evaluated_at=evaluated_at,
        )
        if not decision.allowed:
            return _degraded(_ACCESS_STATUS[decision.code])
        try:
            projection = getattr(financial_provider, method_name)(decision.scope)
            freshness = projection.provenance.freshness_seconds
            observed_at = projection.provenance.observed_at
            observed_age = (
                None if observed_at is None
                else max(0, int((evaluated_at - observed_at).total_seconds()))
            )
            if (freshness is None or observed_age is None
                    or max(freshness, observed_age) > maximum_freshness_seconds):
                return _degraded(FinancialReadStatus.STALE_DATA)
            return projection
        except Exception:
            return _degraded(FinancialReadStatus.FINANCIAL_DATA_UNAVAILABLE)

    @router.get("/overview")
    def overview(
        request: Request,
        session_id: str | None = Header(default=None, alias="X-ARMS-Local-Test-Session"),
    ):
        return read("overview", request, session_id)

    @router.get("/trading")
    def trading(
        request: Request,
        session_id: str | None = Header(default=None, alias="X-ARMS-Local-Test-Session"),
    ):
        return read("trading", request, session_id)

    @router.get("/portfolio")
    def portfolio(
        request: Request,
        session_id: str | None = Header(default=None, alias="X-ARMS-Local-Test-Session"),
    ):
        return read("portfolio", request, session_id)

    @router.get("/coach")
    def coach(
        request: Request,
        session_id: str | None = Header(default=None, alias="X-ARMS-Local-Test-Session"),
    ):
        return read("coach", request, session_id)

    @router.get("/shadow")
    def shadow(
        request: Request,
        session_id: str | None = Header(default=None, alias="X-ARMS-Local-Test-Session"),
    ):
        return read("shadow", request, session_id)

    return router
