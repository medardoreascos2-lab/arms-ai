"""Explicitly mounted, loopback-only Product MEDAR route for synthetic sessions."""

from __future__ import annotations

from datetime import datetime, timezone
from ipaddress import ip_address
from typing import Callable

from fastapi import APIRouter, Header, Request

from backend.api.schemas.product_medar import (
    ProductMedarPrompt,
    ProductMedarResponse,
    ProductMedarStatus,
)
from backend.entitlements import UserIdentity
from backend.memberships import MembershipReadAdapter, resolve_membership_entitlements
from backend.product.customer_session import LOCAL_TEST_ONLY, LocalSyntheticSessionProvider
from backend.product.medar_adapter import (
    ProductMedarRuntime,
    make_invocation,
    project_cognitive_response,
)
from backend.product.surface import ProductDecisionCode, ProductSurface, resolve_product_access


def _degraded(request_id: str, status: ProductMedarStatus) -> ProductMedarResponse:
    return ProductMedarResponse(request_id=request_id, status=status)


def create_local_test_product_medar_router(
    *,
    session_provider: LocalSyntheticSessionProvider,
    membership_adapter: MembershipReadAdapter,
    runtime: ProductMedarRuntime | None = None,
    clock: Callable[[], datetime] | None = None,
) -> APIRouter:
    """Local test only. The application does not register this router by default."""
    if not isinstance(session_provider, LocalSyntheticSessionProvider):
        raise TypeError("Product MEDAR local route requires a synthetic local provider")
    if membership_adapter is None:
        raise TypeError("membership adapter is required")
    now = clock or (lambda: datetime.now(timezone.utc))
    router = APIRouter(prefix="/product/medar", tags=["product-medar-local-test"])

    @router.post("/conversations", response_model=ProductMedarResponse)
    def converse(
        body: ProductMedarPrompt,
        request: Request,
        session_id: str | None = Header(default=None, alias="X-ARMS-Local-Test-Session"),
    ) -> ProductMedarResponse:
        try:
            peer = ip_address(request.client.host if request.client else "")
        except ValueError:
            return _degraded(body.request_id, ProductMedarStatus.PERMISSION_DENIED)
        if not peer.is_loopback:
            return _degraded(body.request_id, ProductMedarStatus.PERMISSION_DENIED)
        at = now()
        try:
            session = session_provider.validate_session(session_id, at)
            if session is None or session.auth_source != LOCAL_TEST_ONLY:
                return _degraded(body.request_id, ProductMedarStatus.PERMISSION_DENIED)
            identity = session_provider.resolve_identity(session, at)
            roles = session_provider.resolve_roles(session, at)
            entitlements = session_provider.resolve_entitlements(session, at)
            if (
                not isinstance(identity, UserIdentity)
                or identity.user_id != session.user_id
                or identity.tenant_id != session.tenant_id
                or roles != session.roles
                or entitlements != session.entitlements
                or session_provider.resolve_tenant(session, at) != session.tenant_id
            ):
                return _degraded(body.request_id, ProductMedarStatus.PERMISSION_DENIED)
        except Exception:
            return _degraded(body.request_id, ProductMedarStatus.PERMISSION_DENIED)

        projection = resolve_membership_entitlements(
            membership_adapter, identity, roles, at
        )
        decision = resolve_product_access(
            projection, customer_session=session, session_provider=session_provider,
            evaluated_at=at, medar_runtime_available=runtime is not None,
        ).decisions[ProductSurface.MEDAR]
        if not decision.allowed:
            if decision.code == ProductDecisionCode.SESSION_INVALID:
                status = ProductMedarStatus.PERMISSION_DENIED
            elif decision.code == ProductDecisionCode.MEDAR_UNAVAILABLE:
                status = ProductMedarStatus.MEDAR_UNAVAILABLE
            else:
                status = ProductMedarStatus.ENTITLEMENT_REQUIRED
            return _degraded(body.request_id, status)

        try:
            invocation = make_invocation(body, session, entitlements)
            return project_cognitive_response(runtime.invoke(invocation), body.request_id)
        except Exception:
            return _degraded(body.request_id, ProductMedarStatus.MEDAR_UNAVAILABLE)

    return router
