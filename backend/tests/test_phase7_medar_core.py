"""R95A MEDAR cognitive core composition tests."""

from backend.medar.core import default_cognitive_core
from backend.medar.domain_router import DomainRouteStatus
from backend.medar.request import (
    CognitiveDomain, CognitiveRequest, RiskClass, TimeSensitivity, normalize_user_input,
)


def _request(text):
    return CognitiveRequest(
        "request-1", "conversation-1", "analyze", text, normalize_user_input(text),
        CognitiveDomain.GENERAL, RiskClass.LOW, (), TimeSensitivity.STATIC,
    )


def test_core_composes_all_required_runtime_components_without_external_model():
    core = default_cognitive_core()
    assert core.intent_classifier is not None
    assert core.domain_router is not None
    assert core.model_router is not None
    assert core.planner is not None
    assert core.agent_orchestrator is not None
    assert core.tool_registry is not None
    assert core.memory_reader is None

    run = core.process(_request("Explain this general question"))
    assert run.route.status is DomainRouteStatus.SINGLE_DOMAIN
    assert run.external_model_used is False
    assert run.action_performed is False
    assert run.orchestration.action_performed is False


def test_unknown_request_fails_closed_without_tasks_or_actions():
    run = default_cognitive_core().process(_request("xyzzy"))
    assert run.route.status is DomainRouteStatus.UNSUPPORTED
    assert run.tasks == ()
    assert run.action_performed is False
