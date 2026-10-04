"""P102A3 translates Product traffic through canonical MEDAR contracts only."""

from datetime import datetime, timedelta, timezone

from backend.api.schemas.product_medar import ProductMedarPrompt
from backend.entitlements import FeatureEntitlement
from backend.medar.core import MedarCognitiveCore
from backend.medar.response import CognitiveResponse
from backend.product.customer_session import synthetic_customer_session
from backend.product.medar_adapter import (
    CanonicalCoreProductRuntime,
    make_invocation,
    project_cognitive_response,
)


NOW = datetime(2026, 10, 4, 12, tzinfo=timezone.utc)


def test_thin_adapter_binds_scope_and_calls_canonical_core_without_memory_or_tools():
    session = synthetic_customer_session(
        issued_at=NOW - timedelta(minutes=1), expires_at=NOW + timedelta(minutes=15)
    )
    prompt = ProductMedarPrompt(
        request_id="request-1", conversation_id="conversation-1",
        message="Summarize the available context.",
    )
    invocation = make_invocation(
        prompt, session, frozenset({FeatureEntitlement.MEDAR_CONVERSATION})
    )
    assert invocation.user_id == session.user_id
    assert invocation.tenant_id == session.tenant_id
    assert invocation.session_id == session.session_id
    assert invocation.request.requires_memory is False
    assert invocation.request.requires_tools is False
    assert invocation.request.requires_web is False

    canonical = CanonicalCoreProductRuntime(MedarCognitiveCore()).invoke(invocation)
    assert isinstance(canonical, CognitiveResponse)
    projected = project_cognitive_response(canonical, prompt.request_id)
    assert projected.request_id == prompt.request_id
    assert projected.action_proposals == ()
    assert projected.memory_evidence == ()
    assert projected.tool_evidence == ()
