"""R83D controlled replanning tests."""

from backend.medar.execution_plan import build_execution_plan
from backend.medar.replanning import PlanHistory, ReplanTrigger, replan
from backend.medar.request import RiskClass
from backend.medar.task_model import CognitiveTask, TaskStatus


def _task(task_id, tool=None):
    return CognitiveTask(
        task_id,
        None,
        f"goal {task_id}",
        (),
        TaskStatus.READY,
        "general_analysis",
        RiskClass.LOW,
        tool,
    )


def test_replan_preserves_original_and_every_revision():
    original = build_execution_plan(
        "plan-1", "req-1", (_task("web", "web_search_stub"),), created_at="t1"
    )
    history = PlanHistory(original)

    second = replan(
        history,
        (_task("memory", "memory_lookup_stub"),),
        trigger=ReplanTrigger.WEB_UNAVAILABLE,
        reason="web provider unavailable",
        created_at="t2",
    )
    third = replan(
        second,
        (_task("clarify"),),
        trigger=ReplanTrigger.EVIDENCE_INSUFFICIENT,
        reason="memory evidence was insufficient",
        created_at="t3",
    )

    assert third.original is original
    assert tuple(item.plan.revision for item in third.revisions) == (2, 3)
    assert third.revisions[0].supersedes_digest == original.snapshot_digest
    assert third.current.tasks[0].task_id == "clarify"
    assert third.current.execution_authorized is False


def test_replan_requires_explicit_reason():
    original = build_execution_plan("plan-1", "req-1", (_task("one"),), created_at="t1")

    try:
        replan(
            PlanHistory(original),
            (_task("two"),),
            trigger=ReplanTrigger.TASK_BLOCKED,
            reason=" ",
            created_at="t2",
        )
    except ValueError as error:
        assert "reason" in str(error)
    else:
        raise AssertionError("blank replan reason was accepted")
