"""Immutable, content-addressed MEDAR execution plans."""

from dataclasses import asdict, dataclass
from hashlib import sha256
import json

from backend.medar.dependency_graph import TaskDependencyGraph
from backend.medar.request import RiskClass
from backend.medar.task_model import CognitiveTask


@dataclass(frozen=True)
class TaskExpectation:
    task_id: str
    expected_evidence: tuple[str, ...]


@dataclass(frozen=True)
class ExecutionPlan:
    plan_id: str
    request_id: str
    revision: int
    created_at: str
    tasks: tuple[CognitiveTask, ...]
    required_tools: tuple[str, ...]
    risk_classes: tuple[RiskClass, ...]
    confirmation_gates: tuple[str, ...]
    expected_evidence: tuple[TaskExpectation, ...]
    snapshot_digest: str
    execution_authorized: bool = False

    def __post_init__(self) -> None:
        if not self.plan_id.strip() or not self.request_id.strip() or not self.created_at.strip():
            raise ValueError("plan identity and timestamp are required")
        if self.revision < 1:
            raise ValueError("plan revision must be positive")
        if self.execution_authorized:
            raise ValueError("plan snapshot cannot authorize execution")
        if self.snapshot_digest != _plan_digest(self):
            raise ValueError("plan snapshot digest mismatch")


def _payload(
    plan_id: str,
    request_id: str,
    revision: int,
    created_at: str,
    tasks: tuple[CognitiveTask, ...],
    required_tools: tuple[str, ...],
    risk_classes: tuple[RiskClass, ...],
    confirmation_gates: tuple[str, ...],
    expected_evidence: tuple[TaskExpectation, ...],
) -> bytes:
    value = {
        "plan_id": plan_id,
        "request_id": request_id,
        "revision": revision,
        "created_at": created_at,
        "tasks": [asdict(task) for task in tasks],
        "required_tools": required_tools,
        "risk_classes": [item.value for item in risk_classes],
        "confirmation_gates": confirmation_gates,
        "expected_evidence": [asdict(item) for item in expected_evidence],
    }
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def _plan_digest(plan: ExecutionPlan) -> str:
    return sha256(
        _payload(
            plan.plan_id,
            plan.request_id,
            plan.revision,
            plan.created_at,
            plan.tasks,
            plan.required_tools,
            plan.risk_classes,
            plan.confirmation_gates,
            plan.expected_evidence,
        )
    ).hexdigest()


def build_execution_plan(
    plan_id: str,
    request_id: str,
    tasks: tuple[CognitiveTask, ...],
    *,
    created_at: str,
    revision: int = 1,
) -> ExecutionPlan:
    TaskDependencyGraph(tasks)
    tools = tuple(dict.fromkeys(task.tool_requirement for task in tasks if task.tool_requirement))
    risks = tuple(dict.fromkeys(task.risk_class for task in tasks))
    gates = tuple(
        task.task_id for task in tasks if task.risk_class in {RiskClass.HIGH, RiskClass.CRITICAL}
    )
    evidence = tuple(
        TaskExpectation(task.task_id, ("status", "result_digest", "source_or_tool_provenance"))
        for task in tasks
    )
    digest = sha256(
        _payload(plan_id, request_id, revision, created_at, tasks, tools, risks, gates, evidence)
    ).hexdigest()
    return ExecutionPlan(
        plan_id,
        request_id,
        revision,
        created_at,
        tasks,
        tools,
        risks,
        gates,
        evidence,
        digest,
    )
