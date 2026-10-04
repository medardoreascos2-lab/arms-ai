"""Validated dependency graph for MEDAR cognitive tasks."""

from types import MappingProxyType
from typing import Mapping

from backend.medar.task_model import CognitiveTask, TaskStatus


class TaskGraphError(ValueError):
    pass


class TaskDependencyGraph:
    def __init__(self, tasks: tuple[CognitiveTask, ...]):
        entries: dict[str, CognitiveTask] = {}
        for task in tasks:
            if task.task_id in entries:
                raise TaskGraphError(f"duplicate task: {task.task_id}")
            entries[task.task_id] = task
        for task in tasks:
            missing = tuple(item for item in task.dependencies if item not in entries)
            if missing:
                raise TaskGraphError(f"missing dependencies for {task.task_id}: {missing}")
        self._tasks: Mapping[str, CognitiveTask] = MappingProxyType(entries)
        self._assert_acyclic()

    @property
    def tasks(self) -> tuple[CognitiveTask, ...]:
        return tuple(self._tasks.values())

    def ready_tasks(self) -> tuple[CognitiveTask, ...]:
        return tuple(
            task
            for task in self.tasks
            if task.status in {TaskStatus.PENDING, TaskStatus.READY}
            and all(self._tasks[item].status is TaskStatus.COMPLETED for item in task.dependencies)
        )

    def blocked_tasks(self) -> tuple[CognitiveTask, ...]:
        terminal_blockers = {TaskStatus.BLOCKED, TaskStatus.FAILED, TaskStatus.CANCELLED}
        return tuple(
            task
            for task in self.tasks
            if any(self._tasks[item].status in terminal_blockers for item in task.dependencies)
        )

    def parallel_groups(self) -> tuple[tuple[str, ...], ...]:
        remaining = set(self._tasks)
        completed: set[str] = set()
        groups: list[tuple[str, ...]] = []
        while remaining:
            group = tuple(sorted(item for item in remaining if set(self._tasks[item].dependencies) <= completed))
            if not group:
                raise TaskGraphError("dependency graph cannot make progress")
            groups.append(group)
            completed.update(group)
            remaining.difference_update(group)
        return tuple(groups)

    def _assert_acyclic(self) -> None:
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(task_id: str) -> None:
            if task_id in visiting:
                raise TaskGraphError("dependency cycle detected")
            if task_id in visited:
                return
            visiting.add(task_id)
            for dependency in self._tasks[task_id].dependencies:
                visit(dependency)
            visiting.remove(task_id)
            visited.add(task_id)

        for task_id in self._tasks:
            visit(task_id)
