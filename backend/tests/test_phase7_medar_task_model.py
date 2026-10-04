"""R80C MEDAR task planning model tests."""

import pytest

from backend.medar.request import RiskClass
from backend.medar.task_model import CognitiveTask, TaskStatus, transition_task


def _task(**overrides):
    values = {
        "task_id": "task-1",
        "parent_task_id": None,
        "goal": "Collect bounded evidence",
        "dependencies": (),
        "status": TaskStatus.PENDING,
        "required_capability": "web_search",
        "risk_class": RiskClass.LOW,
        "tool_requirement": "web_search_stub",
    }
    values.update(overrides)
    return CognitiveTask(**values)


def test_task_moves_through_valid_immutable_lifecycle():
    pending = _task()
    ready = transition_task(pending, TaskStatus.READY)
    running = transition_task(ready, TaskStatus.RUNNING)
    completed = transition_task(running, TaskStatus.COMPLETED, completion_evidence=("source:1",))

    assert pending.status is TaskStatus.PENDING
    assert completed.status is TaskStatus.COMPLETED
    assert completed.completion_evidence == ("source:1",)


def test_completed_task_requires_evidence():
    running = _task(status=TaskStatus.RUNNING)

    with pytest.raises(ValueError, match="completion evidence"):
        transition_task(running, TaskStatus.COMPLETED)


@pytest.mark.parametrize(
    "task",
    [
        lambda: _task(dependencies=("task-1",)),
        lambda: _task(dependencies=("task-2", "task-2")),
        lambda: _task(status=TaskStatus.COMPLETED),
    ],
)
def test_invalid_task_definition_fails_closed(task):
    with pytest.raises(ValueError):
        task()


def test_terminal_task_cannot_restart():
    task = _task(status=TaskStatus.COMPLETED, completion_evidence=("done",))

    with pytest.raises(ValueError, match="invalid task transition"):
        transition_task(task, TaskStatus.READY)
