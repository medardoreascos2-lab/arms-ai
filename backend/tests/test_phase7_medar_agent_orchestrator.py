"""R85C MEDAR agent orchestrator tests."""

from backend.medar.agent_orchestrator import AgentOrchestrator
from backend.medar.agents import initial_agents
from backend.medar.request import RiskClass
from backend.medar.task_model import CognitiveTask, TaskStatus


def _task(task_id, capability, dependencies=(), risk=RiskClass.MODERATE):
    return CognitiveTask(
        task_id,
        None,
        f"perform {capability}",
        dependencies,
        TaskStatus.PENDING,
        capability,
        risk,
    )


def test_orchestrator_selects_agents_runs_multi_agent_plan_and_handoffs():
    tasks = (
        _task("web", "web_search"),
        _task("finance", "financial_analysis", risk=RiskClass.HIGH),
        _task("synthesis", "general_analysis", ("web", "finance")),
    )

    result = AgentOrchestrator(initial_agents()).orchestrate("req-1", tasks)

    assert tuple(output.agent_id for output in result.outputs) == (
        "web-research",
        "financial-research",
        "general-assistant",
    )
    assert len(result.handoffs) == 2
    assert all(item.to_task_id == "synthesis" for item in result.handoffs)
    assert result.unassigned_tasks == ()
    assert result.action_performed is False


def test_unregistered_capability_is_reported_without_execution():
    result = AgentOrchestrator(initial_agents()).orchestrate(
        "req-1", (_task("unknown", "broker_execution", risk=RiskClass.CRITICAL),)
    )

    assert result.outputs == ()
    assert result.unassigned_tasks == ("unknown",)
    assert result.action_performed is False
