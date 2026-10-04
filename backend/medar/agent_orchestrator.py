"""Deterministic MEDAR agent selection, handoff and result aggregation."""

from dataclasses import dataclass

from backend.medar.agent_contract import AgentInput, AgentOutput, SpecializedAgent
from backend.medar.dependency_graph import TaskDependencyGraph
from backend.medar.task_model import CognitiveTask


@dataclass(frozen=True)
class AgentHandoff:
    from_agent_id: str
    to_agent_id: str
    from_task_id: str
    to_task_id: str
    evidence_summary: str


@dataclass(frozen=True)
class OrchestrationResult:
    outputs: tuple[AgentOutput, ...]
    handoffs: tuple[AgentHandoff, ...]
    unassigned_tasks: tuple[str, ...]
    conflict_detected: bool
    action_performed: bool = False


class AgentOrchestrator:
    def __init__(self, agents: tuple[SpecializedAgent, ...]):
        ids = tuple(agent.contract.agent_id for agent in agents)
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate agent id")
        self._agents = agents

    def select_agent(self, task: CognitiveTask) -> SpecializedAgent | None:
        candidates = tuple(
            agent for agent in self._agents if task.required_capability in agent.contract.capabilities
        )
        if not candidates:
            return None
        return sorted(candidates, key=lambda agent: agent.contract.agent_id)[0]

    def orchestrate(self, request_id: str, tasks: tuple[CognitiveTask, ...]) -> OrchestrationResult:
        graph = TaskDependencyGraph(tasks)
        task_map = {task.task_id: task for task in tasks}
        output_map: dict[str, AgentOutput] = {}
        handoffs: list[AgentHandoff] = []
        unassigned: list[str] = []
        for group in graph.parallel_groups():
            for task_id in group:
                task = task_map[task_id]
                agent = self.select_agent(task)
                if agent is None:
                    unassigned.append(task_id)
                    continue
                dependency_outputs = tuple(
                    output_map[item].summary for item in task.dependencies if item in output_map
                )
                for dependency in task.dependencies:
                    if dependency in output_map:
                        source = output_map[dependency]
                        handoffs.append(
                            AgentHandoff(
                                source.agent_id,
                                agent.contract.agent_id,
                                dependency,
                                task_id,
                                source.summary,
                            )
                        )
                output_map[task_id] = agent.analyze(
                    AgentInput(request_id, task_id, task.goal, dependency_outputs)
                )
        return OrchestrationResult(
            tuple(output_map[item] for item in task_map if item in output_map),
            tuple(handoffs),
            tuple(unassigned),
            conflict_detected=False,
        )
