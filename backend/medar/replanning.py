"""Controlled MEDAR replanning with immutable revision history."""

from dataclasses import dataclass
from enum import Enum

from backend.medar.execution_plan import ExecutionPlan, build_execution_plan
from backend.medar.task_model import CognitiveTask


class ReplanTrigger(str, Enum):
    TOOL_FAILED = "TOOL_FAILED"
    EVIDENCE_INSUFFICIENT = "EVIDENCE_INSUFFICIENT"
    WEB_UNAVAILABLE = "WEB_UNAVAILABLE"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    TASK_BLOCKED = "TASK_BLOCKED"


@dataclass(frozen=True)
class PlanRevision:
    plan: ExecutionPlan
    trigger: ReplanTrigger
    reason: str
    supersedes_digest: str


@dataclass(frozen=True)
class PlanHistory:
    original: ExecutionPlan
    revisions: tuple[PlanRevision, ...] = ()

    @property
    def current(self) -> ExecutionPlan:
        return self.revisions[-1].plan if self.revisions else self.original


def replan(
    history: PlanHistory,
    tasks: tuple[CognitiveTask, ...],
    *,
    trigger: ReplanTrigger,
    reason: str,
    created_at: str,
) -> PlanHistory:
    if not reason.strip():
        raise ValueError("replan reason is required")
    current = history.current
    revised = build_execution_plan(
        current.plan_id,
        current.request_id,
        tasks,
        created_at=created_at,
        revision=current.revision + 1,
    )
    revision = PlanRevision(revised, trigger, reason, current.snapshot_digest)
    return PlanHistory(history.original, history.revisions + (revision,))
