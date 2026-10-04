"""Deterministic task and plan primitives for MEDAR."""

from dataclasses import dataclass, replace
from enum import Enum

from backend.medar.request import RiskClass


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    READY = "READY"
    RUNNING = "RUNNING"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


_ALLOWED_TRANSITIONS = {
    TaskStatus.PENDING: {TaskStatus.READY, TaskStatus.BLOCKED, TaskStatus.CANCELLED},
    TaskStatus.READY: {TaskStatus.RUNNING, TaskStatus.BLOCKED, TaskStatus.CANCELLED},
    TaskStatus.RUNNING: {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.BLOCKED},
    TaskStatus.BLOCKED: {TaskStatus.READY, TaskStatus.CANCELLED},
    TaskStatus.FAILED: set(),
    TaskStatus.COMPLETED: set(),
    TaskStatus.CANCELLED: set(),
}


@dataclass(frozen=True)
class CognitiveTask:
    task_id: str
    parent_task_id: str | None
    goal: str
    dependencies: tuple[str, ...]
    status: TaskStatus
    required_capability: str
    risk_class: RiskClass
    tool_requirement: str | None = None
    completion_evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("task_id", "goal", "required_capability"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be non-empty text")
        if self.parent_task_id is not None and not self.parent_task_id.strip():
            raise ValueError("parent_task_id must be non-empty when present")
        if self.task_id in self.dependencies:
            raise ValueError("task cannot depend on itself")
        if len(set(self.dependencies)) != len(self.dependencies):
            raise ValueError("task dependencies must be unique")
        if not isinstance(self.status, TaskStatus):
            raise TypeError("status must be TaskStatus")
        if not isinstance(self.risk_class, RiskClass):
            raise TypeError("risk_class must be RiskClass")
        if self.status is TaskStatus.COMPLETED and not self.completion_evidence:
            raise ValueError("completed task requires completion evidence")


def transition_task(
    task: CognitiveTask,
    status: TaskStatus,
    *,
    completion_evidence: tuple[str, ...] = (),
) -> CognitiveTask:
    """Return a new task after an allowed state transition."""

    if status not in _ALLOWED_TRANSITIONS[task.status]:
        raise ValueError(f"invalid task transition: {task.status.value}->{status.value}")
    evidence = completion_evidence if status is TaskStatus.COMPLETED else task.completion_evidence
    return replace(task, status=status, completion_evidence=evidence)
