"""Content-free aggregate metrics across scoped synthetic local model evaluations."""

from collections import Counter
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from backend.medar.model_performance import ModelEvaluationEvent, ModelFailureClass
from backend.medar.sqlite_memory_store import MemoryScope


@dataclass(frozen=True)
class ModelMetricsSnapshot:
    tenant_id: str
    owner_id: str
    attempts: int
    successes: int
    structured_valid: int
    average_latency_ms: float
    average_quality_score: float
    by_provider: Mapping[str, int]
    by_model: Mapping[str, int]
    by_task_type: Mapping[str, int]
    failures: Mapping[str, int]
    external_calls: int = 0
    paid_api_calls: int = 0
    routing_authority: bool = False

    def __post_init__(self) -> None:
        if self.external_calls or self.paid_api_calls or self.routing_authority:
            raise ValueError("Phase 8 model metrics cannot report external, paid, or routing authority")

    @property
    def success_rate(self) -> float:
        return self.successes / self.attempts if self.attempts else 0.0

    @property
    def structured_valid_rate(self) -> float:
        return self.structured_valid / self.attempts if self.attempts else 0.0


def summarize_model_metrics(events: tuple[ModelEvaluationEvent, ...], scope: MemoryScope) -> ModelMetricsSnapshot:
    if not isinstance(events, tuple) or any(not isinstance(event, ModelEvaluationEvent) for event in events):
        raise TypeError("model metrics require typed events")
    if not isinstance(scope, MemoryScope):
        raise TypeError("model metrics require a typed scope")
    for event in events:
        if (event.tenant_id, event.owner_id) != (scope.tenant_id, scope.owner_id):
            raise PermissionError("model metric scope mismatch")
    attempts = len(events)
    providers = Counter(event.provider_id for event in events)
    models = Counter(event.model_id for event in events)
    tasks = Counter(event.task_type for event in events)
    failures = Counter(event.failure_class.value for event in events if event.failure_class is not ModelFailureClass.NONE)
    return ModelMetricsSnapshot(
        scope.tenant_id, scope.owner_id, attempts,
        sum(event.successful for event in events),
        sum(event.structured_valid for event in events),
        sum(event.latency_ms for event in events) / attempts if attempts else 0.0,
        sum(event.quality_score for event in events) / attempts if attempts else 0.0,
        MappingProxyType(dict(sorted(providers.items()))),
        MappingProxyType(dict(sorted(models.items()))),
        MappingProxyType(dict(sorted(tasks.items()))),
        MappingProxyType(dict(sorted(failures.items()))),
    )
