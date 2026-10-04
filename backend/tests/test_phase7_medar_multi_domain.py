"""R95C MEDAR multi-domain planning regression."""

from backend.medar.core import default_cognitive_core
from backend.medar.domain_router import DomainRouteStatus
from backend.medar.request import (
    CognitiveDomain, CognitiveRequest, RiskClass, TimeSensitivity, normalize_user_input,
)


def test_multi_domain_request_preserves_separate_capabilities_and_authorities():
    text = (
        "Research NVIDIA, compare portfolio risk, summarize latest web evidence, "
        "and create a marketing-style report."
    )
    request = CognitiveRequest(
        "multi-1", "conversation", "multi-domain analysis", text, normalize_user_input(text),
        CognitiveDomain.UNKNOWN, RiskClass.HIGH, (), TimeSensitivity.CURRENT,
        requires_web=True,
    )
    run = default_cognitive_core().process(request)

    assert run.route.status is DomainRouteStatus.MULTI_DOMAIN
    assert run.route.domains == (
        CognitiveDomain.PORTFOLIO, CognitiveDomain.WEB_RESEARCH, CognitiveDomain.MARKETING,
    )
    capability_domains = {item.capability_id: item.domain for item in run.route.capabilities}
    assert capability_domains == {
        "portfolio_analysis": CognitiveDomain.PORTFOLIO,
        "web_search": CognitiveDomain.WEB_RESEARCH,
        "marketing_analysis": CognitiveDomain.MARKETING,
    }
    assert next(
        item for item in run.route.capabilities if item.capability_id == "portfolio_analysis"
    ).confirmation_required is True
    assert all(item.execution_authority is False for item in run.route.capabilities)
    assert run.tasks[-1].dependencies == tuple(item.task_id for item in run.tasks[:-1])
    assert run.action_performed is False
    assert all(output.action_performed is False for output in run.orchestration.outputs)
