"""Thin Product-to-canonical-MEDAR translation with no planner or model logic."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from backend.api.schemas.product_medar import (
    ProductActionProposal,
    ProductEvidenceReference,
    ProductMedarPrompt,
    ProductMedarResponse,
    ProductMedarStatus,
    ProductSourceReference,
)
from backend.entitlements import FeatureEntitlement
from backend.medar.core import MedarCognitiveCore
from backend.medar.request import (
    CognitiveDomain,
    CognitiveRequest,
    RiskClass,
    TimeSensitivity,
    normalize_user_input,
)
from backend.medar.response import CognitiveResponse
from backend.product.customer_session import LOCAL_TEST_ONLY, TrustedCustomerSession


@dataclass(frozen=True)
class ProductMedarInvocation:
    request: CognitiveRequest
    user_id: str
    tenant_id: str
    session_id: str
    entitlements: frozenset[FeatureEntitlement]
    auth_source: str
    authentication_method: str


class ProductMedarRuntime(Protocol):
    def invoke(self, invocation: ProductMedarInvocation) -> CognitiveResponse: ...


class CanonicalCoreProductRuntime:
    """Calls only the existing canonical core with memory and tools disabled."""

    def __init__(self, core: MedarCognitiveCore) -> None:
        if not isinstance(core, MedarCognitiveCore):
            raise TypeError("canonical MEDAR core required")
        self._core = core

    def invoke(self, invocation: ProductMedarInvocation) -> CognitiveResponse:
        if (
            invocation.auth_source != LOCAL_TEST_ONLY
            or invocation.request.requires_tools
            or invocation.request.requires_memory
            or invocation.request.requires_web
        ):
            raise PermissionError("Product runtime requires local, tool-free invocation")
        run = self._core.process(invocation.request, memory_query=None)
        if (
            run.action_performed or run.external_model_used
            or run.memory_results or run.response.tool_evidence
            or run.response.memory_evidence
        ):
            raise RuntimeError("canonical MEDAR run exceeded local Product boundary")
        return run.response


def to_cognitive_request(prompt: ProductMedarPrompt) -> CognitiveRequest:
    return CognitiveRequest(
        request_id=prompt.request_id,
        conversation_id=prompt.conversation_id,
        user_intent="PRODUCT_CONVERSATION",
        raw_input=prompt.message,
        normalized_input=normalize_user_input(prompt.message),
        domain=CognitiveDomain.GENERAL,
        risk_class=RiskClass.HIGH,
        required_capabilities=(),
        time_sensitivity=TimeSensitivity.STATIC,
        requires_web=False,
        requires_tools=False,
        requires_memory=False,
        requires_human_confirmation=True,
    )


def make_invocation(
    prompt: ProductMedarPrompt,
    session: TrustedCustomerSession,
    entitlements: frozenset[FeatureEntitlement],
) -> ProductMedarInvocation:
    return ProductMedarInvocation(
        request=to_cognitive_request(prompt),
        user_id=session.user_id,
        tenant_id=session.tenant_id,
        session_id=session.session_id,
        entitlements=entitlements,
        auth_source=session.auth_source,
        authentication_method=session.authentication_method,
    )


def project_cognitive_response(
    response: CognitiveResponse, request_id: str,
) -> ProductMedarResponse:
    if not isinstance(response, CognitiveResponse) or response.request_id != request_id:
        raise ValueError("MEDAR response does not match Product request")
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
