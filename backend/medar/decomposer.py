"""Deterministic request decomposition into bounded MEDAR tasks."""

from backend.medar.domain_router import DomainRoute, DomainRouteStatus
from backend.medar.request import CognitiveRequest, RiskClass
from backend.medar.task_model import CognitiveTask, TaskStatus


class TaskDecomposer:
    def decompose(self, request: CognitiveRequest, route: DomainRoute) -> tuple[CognitiveTask, ...]:
        if route.status in {DomainRouteStatus.AMBIGUOUS, DomainRouteStatus.UNSUPPORTED}:
            return ()
        tasks: list[CognitiveTask] = []
        for index, capability in enumerate(route.capabilities, start=1):
            tasks.append(
                CognitiveTask(
                    task_id=f"{request.request_id}:task:{index}",
                    parent_task_id=request.request_id,
                    goal=capability.description,
                    dependencies=(),
                    status=TaskStatus.READY,
                    required_capability=capability.capability_id,
                    risk_class=capability.risk_class,
                    tool_requirement=(capability.tool_requirements[0] if capability.tool_requirements else None),
                )
            )
        if len(tasks) > 1:
            tasks.append(
                CognitiveTask(
                    task_id=f"{request.request_id}:task:synthesis",
                    parent_task_id=request.request_id,
                    goal="Synthesize domain results while preserving boundaries and uncertainty",
                    dependencies=tuple(task.task_id for task in tasks),
                    status=TaskStatus.PENDING,
                    required_capability="general_analysis",
                    risk_class=max((task.risk_class for task in tasks), key=lambda item: list(RiskClass).index(item)),
                    completion_evidence=(),
                )
            )
        return tuple(tasks)
