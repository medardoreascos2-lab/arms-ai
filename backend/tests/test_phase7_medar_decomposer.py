"""R83A MEDAR task decomposition tests."""

from backend.medar.capabilities import default_capability_registry
from backend.medar.decomposer import TaskDecomposer
from backend.medar.domain_router import DomainRouter
from backend.medar.intent import RuleAssistedIntentClassifier
from backend.medar.request import (
    CognitiveDomain,
    CognitiveRequest,
    RiskClass,
    TimeSensitivity,
)
from backend.medar.task_model import TaskStatus


def _request(text):
    return CognitiveRequest(
        "req-nvda",
        "conv-1",
        "research and compare",
        text,
        " ".join(text.split()),
        CognitiveDomain.FINANCIAL,
        RiskClass.HIGH,
        (),
        TimeSensitivity.CURRENT,
        requires_web=True,
        requires_tools=True,
    )


def test_complex_request_decomposes_into_parallel_domain_work_then_synthesis():
    text = "Research latest NVIDIA stock sources, compare portfolio risk, and summarize"
    classification = RuleAssistedIntentClassifier().classify(text)
    route = DomainRouter(default_capability_registry()).route(classification)

    tasks = TaskDecomposer().decompose(_request(text), route)

    assert tuple(task.required_capability for task in tasks[:-1]) == (
        "portfolio_analysis",
        "financial_analysis",
        "web_search",
    )
    assert all(task.status is TaskStatus.READY for task in tasks[:-1])
    assert tasks[-1].status is TaskStatus.PENDING
    assert tasks[-1].dependencies == tuple(task.task_id for task in tasks[:-1])


def test_unsupported_route_creates_no_tasks():
    classification = RuleAssistedIntentClassifier().classify("florp zibble")
    route = DomainRouter(default_capability_registry()).route(classification)

    assert TaskDecomposer().decompose(_request("florp zibble"), route) == ()
