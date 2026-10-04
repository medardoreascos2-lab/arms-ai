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


def _degraded(code: FinancialAccessCode) -> JSONResponse:
    return JSONResponse({
        "status": code.value,
        "data": None,
        "broker_authorized": False,
        "portfolio_mutation_authorized": False,
        "paper_authorized": False,
        "live_authorized": False,
    })


def create_local_test_product_financial_router(
    *,
    session_provider: CustomerSessionProvider,
    membership_adapter: MembershipReadAdapter,
    scope_provider: CustomerFinancialScopeProvider,
    financial_provider: ProductFinancialReadProvider,
    clock: Callable[[], datetime] | None = None,
) -> APIRouter:
    if any(item is None for item in (
        session_provider, membership_adapter, scope_provider, financial_provider
    )):
        raise TypeError("all Product financial read dependencies are required")
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
            return _degraded(FinancialAccessCode.SESSION_INVALID)
        if not peer.is_loopback:
            return _degraded(FinancialAccessCode.SESSION_INVALID)
        surface, entitlement, method_name = _ROUTE_POLICY[route_name]
        decision = authorize_financial_read(
            session_id=session_id,
            session_provider=session_provider,
            membership_adapter=membership_adapter,
            scope_provider=scope_provider,
            required_surface=surface,
            required_entitlement=entitlement,
            evaluated_at=now(),
        )
        if not decision.allowed:
            return _degraded(decision.code)
        try:
            method = getattr(financial_provider, method_name)
            return method(decision.scope)
        except Exception:
            return JSONResponse({
                "status": "FINANCIAL_DATA_UNAVAILABLE",
                "data": None,
                "broker_authorized": False,
                "portfolio_mutation_authorized": False,
                "paper_authorized": False,
                "live_authorized": False,
            })

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
