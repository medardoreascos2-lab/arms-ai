"""Composed, local deterministic MEDAR cognitive core."""

from dataclasses import dataclass

from backend.medar.agent_orchestrator import AgentOrchestrator, OrchestrationResult
from backend.medar.agents import initial_agents
from backend.medar.capabilities import default_capability_registry
from backend.medar.decomposer import TaskDecomposer
from backend.medar.domain_router import DomainRoute, DomainRouter
from backend.medar.evidence import aggregate_evidence
from backend.medar.intent import IntentClassification, RuleAssistedIntentClassifier
from backend.medar.memory_read import MemoryQuery, MemoryReadResult, MemoryReader
from backend.medar.model_profiles import ModelProfileRegistry
from backend.medar.model_router import ModelRouter
from backend.medar.request import CognitiveRequest
from backend.medar.response import CognitiveResponse
from backend.medar.response_synthesis import synthesize_response
from backend.medar.task_model import CognitiveTask
from backend.medar.tool_registry import ToolRegistry, default_tool_registry


@dataclass(frozen=True)
class CognitiveRun:
    request: CognitiveRequest
    intent: IntentClassification
    route: DomainRoute
    tasks: tuple[CognitiveTask, ...]
    orchestration: OrchestrationResult
    memory_results: tuple[MemoryReadResult, ...]
    response: CognitiveResponse
    external_model_used: bool = False
    action_performed: bool = False


class MedarCognitiveCore:
    def __init__(
        self,
        *,
        memory_reader: MemoryReader | None = None,
        model_profiles: ModelProfileRegistry | None = None,
        tool_registry: ToolRegistry | None = None,
    ):
        capabilities = default_capability_registry()
        self.intent_classifier = RuleAssistedIntentClassifier()
        self.domain_router = DomainRouter(capabilities)
        self.model_router = ModelRouter(model_profiles or ModelProfileRegistry(()))
        self.planner = TaskDecomposer()
        self.agent_orchestrator = AgentOrchestrator(initial_agents())
        self.tool_registry = tool_registry or default_tool_registry()
        self.memory_reader = memory_reader

    def process(
        self,
        request: CognitiveRequest,
        *,
        memory_query: MemoryQuery | None = None,
    ) -> CognitiveRun:
        intent = self.intent_classifier.classify(request.normalized_input)
        route = self.domain_router.route(intent)
        tasks = self.planner.decompose(request, route)
        orchestration = self.agent_orchestrator.orchestrate(request.request_id, tasks)
        memory_results: tuple[MemoryReadResult, ...] = ()
        if memory_query is not None:
            if self.memory_reader is None:
                raise ValueError("memory query requires an injected memory reader")
            memory_results = tuple(
                item for item in self.memory_reader.retrieve(memory_query) if item.is_visible_to(memory_query)
            )
        evidence = aggregate_evidence(
            agent_outputs=orchestration.outputs,
            memory_results=memory_results,
            warnings=tuple(route.reasons) + tuple(
                f"UNASSIGNED_TASK:{task_id}" for task_id in orchestration.unassigned_tasks
            ),
        )
        supported_summary = "\n".join(output.summary for output in orchestration.outputs)
        response = synthesize_response(
            response_id=f"{request.request_id}:response",
            request_id=request.request_id,
            answer=supported_summary or "No supported result was produced.",
            evidence=evidence,
        )
        return CognitiveRun(request, intent, route, tasks, orchestration, memory_results, response)


def default_cognitive_core() -> MedarCognitiveCore:
    return MedarCognitiveCore()
