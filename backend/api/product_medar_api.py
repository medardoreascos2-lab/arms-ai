"""Explicitly mounted, loopback-only Product MEDAR adapter for synthetic sessions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from ipaddress import ip_address
from typing import Callable, Protocol

from fastapi import APIRouter, Header, Request

from backend.api.schemas.product_medar import (
    ProductActionProposal,
    ProductEvidenceReference,
    ProductMedarPrompt,
    ProductMedarResponse,
    ProductMedarStatus,
    ProductSourceReference,
)
from backend.entitlements import FeatureEntitlement, UserIdentity
from backend.medar.request import (
    CognitiveDomain,
    CognitiveRequest,
    RiskClass,
    TimeSensitivity,
    normalize_user_input,
)
from backend.medar.response import CognitiveResponse
from backend.memberships import MembershipReadAdapter, resolve_membership_entitlements
from backend.product.customer_session import (
    LOCAL_TEST_ONLY,
    LocalSyntheticSessionProvider,
)
from backend.product.surface import (
    ProductDecisionCode,
    ProductSurface,
    resolve_product_access,
)


@dataclass(frozen=True)
class ProductMedarInvocation:
    """The only identity scope given to a MEDAR Product runtime."""

    request: CognitiveRequest
    user_id: str
    tenant_id: str
    session_id: str
    entitlements: frozenset[FeatureEntitlement]
    auth_source: str
    authentication_method: str


class ProductMedarRuntime(Protocol):
    def invoke(self, invocation: ProductMedarInvocation) -> CognitiveResponse: ...


def _degraded(request_id: str, status: ProductMedarStatus) -> ProductMedarResponse:
    return ProductMedarResponse(request_id=request_id, status=status)


def _project_response(response: CognitiveResponse, request_id: str) -> ProductMedarResponse:
    if not isinstance(response, CognitiveResponse) or response.request_id != request_id:
        raise ValueError("MEDAR response does not match request")
    return ProductMedarResponse(
        response_id=response.response_id,
        request_id=response.request_id,
        status=ProductMedarStatus(response.status.value),
        answer=response.answer,
        confidence=response.confidence,
        reasoning_summary=response.reasoning_summary,
        sources=tuple(ProductSourceReference(
            source_id=item.source_id, title=item.title, locator=item.locator
        ) for item in response.sources),
        tool_evidence=tuple(ProductEvidenceReference(
            evidence_id=item.evidence_id, summary=item.summary, digest=item.digest
        ) for item in response.tool_evidence),
        memory_evidence=tuple(ProductEvidenceReference(
            evidence_id=item.evidence_id, summary=item.summary, digest=item.digest
        ) for item in response.memory_evidence),
        warnings=response.warnings,
        follow_up_needed=response.follow_up_needed,
        action_proposals=tuple(ProductActionProposal(
            action_id=item.action_id, description=item.description,
            requires_confirmation=item.requires_confirmation,
        ) for item in response.action_proposals),
    )


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

        cognitive_request = CognitiveRequest(
            request_id=body.request_id,
            conversation_id=body.conversation_id,
            user_intent="PRODUCT_CONVERSATION",
            raw_input=body.message,
            normalized_input=normalize_user_input(body.message),
            domain=CognitiveDomain.GENERAL,
            risk_class=RiskClass.HIGH,
            required_capabilities=(),
            time_sensitivity=TimeSensitivity.STATIC,
            requires_web=False,
            requires_tools=False,
            requires_memory=False,
            requires_human_confirmation=True,
        )
        invocation = ProductMedarInvocation(
            request=cognitive_request,
            user_id=session.user_id,
            tenant_id=session.tenant_id,
            session_id=session.session_id,
            entitlements=entitlements,
            auth_source=session.auth_source,
            authentication_method=session.authentication_method,
        )
        try:
            return _project_response(runtime.invoke(invocation), body.request_id)
        except Exception:
            return _degraded(body.request_id, ProductMedarStatus.MEDAR_UNAVAILABLE)

    return router
