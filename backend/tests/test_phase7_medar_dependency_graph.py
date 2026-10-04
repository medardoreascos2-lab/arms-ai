"""R83B MEDAR dependency graph tests."""

import pytest

from backend.medar.dependency_graph import TaskDependencyGraph, TaskGraphError
from backend.medar.request import RiskClass
from backend.medar.task_model import CognitiveTask, TaskStatus


def _task(task_id, dependencies=(), status=TaskStatus.PENDING):
    evidence = ("done",) if status is TaskStatus.COMPLETED else ()
    return CognitiveTask(
        task_id,
        None,
        f"goal {task_id}",
        dependencies,
        status,
        "general_analysis",
        RiskClass.LOW,
        completion_evidence=evidence,
    )


def test_graph_identifies_parallel_work_and_dependency_order():
    graph = TaskDependencyGraph(
        (_task("a"), _task("b"), _task("c", ("a", "b")))
    )

    assert graph.parallel_groups() == (("a", "b"), ("c",))
    assert tuple(task.task_id for task in graph.ready_tasks()) == ("a", "b")


def test_completed_dependencies_make_pending_task_ready():
    graph = TaskDependencyGraph(
        (_task("a", status=TaskStatus.COMPLETED), _task("b", ("a",)))
    )

    assert tuple(task.task_id for task in graph.ready_tasks()) == ("b",)


def test_failed_dependency_blocks_dependent_task():
    graph = TaskDependencyGraph((_task("a", status=TaskStatus.FAILED), _task("b", ("a",))))

    assert tuple(task.task_id for task in graph.blocked_tasks()) == ("b",)


@pytest.mark.parametrize(
    "tasks",
    [
        (_task("a", ("missing",)),),
        (_task("a", ("b",)), _task("b", ("a",))),
        (_task("a"), _task("a")),
    ],
)
def test_invalid_graph_fails_closed(tasks):
    with pytest.raises(TaskGraphError):
        TaskDependencyGraph(tasks)
