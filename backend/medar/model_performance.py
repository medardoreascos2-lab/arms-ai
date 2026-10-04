"""Content-free, scoped observations of MEDAR model performance."""

import math
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from backend.medar.model_profiles import CostClass


class ModelFailureClass(str, Enum):
    NONE = "NONE"
    UNAVAILABLE = "UNAVAILABLE"
    TIMEOUT = "TIMEOUT"
    STRUCTURED_INVALID = "STRUCTURED_INVALID"
    QUALITY_REJECTED = "QUALITY_REJECTED"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ModelEvaluationEvent:
    event_id: str
    tenant_id: str
    owner_id: str
    model_id: str
    task_type: str
    successful: bool
    structured_valid: bool
    latency_ms: float
    quality_score: float
    failure_class: ModelFailureClass
    cost_class: CostClass
    observed_at: datetime
    routing_authority: bool = False
    external_call_authority: bool = False

    def __post_init__(self) -> None:
        for name in ("event_id", "tenant_id", "owner_id", "model_id", "task_type"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or len(value) > 240:
                raise ValueError(f"{name} must be bounded non-empty text")
        if not isinstance(self.successful, bool) or not isinstance(self.structured_valid, bool):
            raise TypeError("model validity flags must be boolean")
        if not isinstance(self.failure_class, ModelFailureClass) or not isinstance(self.cost_class, CostClass):
            raise TypeError("model failure and cost classes must be typed")
        if self.successful and self.failure_class is not ModelFailureClass.NONE:
            raise ValueError("successful model event cannot claim a failure")
        if not self.successful and self.failure_class is ModelFailureClass.NONE:
            raise ValueError("unsuccessful model event requires a failure class")
        if not self.structured_valid and self.successful:
            raise ValueError("invalid structured output cannot be successful")
        for name, value in (("latency_ms", self.latency_ms), ("quality_score", self.quality_score)):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"{name} must be finite")
        if self.latency_ms < 0 or not 0 <= self.quality_score <= 1:
            raise ValueError("model latency and quality score are outside bounds")
        if not isinstance(self.observed_at, datetime) or self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("model observation time must be timezone-aware")
        if self.routing_authority or self.external_call_authority:
            raise ValueError("model evaluation cannot grant routing or external call authority")


@dataclass(frozen=True)
class ModelPerformanceSummary:
    tenant_id: str
    owner_id: str
    model_id: str
    task_type: str
    attempts: int
    successes: int
    structured_valid_rate: float
    average_latency_ms: float
    average_quality_score: float
    failure_counts: tuple[tuple[ModelFailureClass, int], ...]
    observed_cost_classes: tuple[CostClass, ...]
    routing_authority: bool = False

    def __post_init__(self) -> None:
        for name in ("tenant_id", "owner_id", "model_id", "task_type"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or len(value) > 240:
                raise ValueError(f"{name} must be bounded non-empty text")
        if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in (self.attempts, self.successes)):
            raise ValueError("model counts must be nonnegative integers")
        if self.successes > self.attempts:
            raise ValueError("model successes cannot exceed attempts")
        for name in ("structured_valid_rate", "average_quality_score"):
            value = getattr(self, name)
            if not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError(f"{name} must be finite and between zero and one")
        if not math.isfinite(self.average_latency_ms) or self.average_latency_ms < 0:
            raise ValueError("model average latency must be finite and nonnegative")
        if any(
            not isinstance(kind, ModelFailureClass) or kind is ModelFailureClass.NONE
            or isinstance(count, bool) or not isinstance(count, int) or count < 1
            for kind, count in self.failure_counts
        ):
            raise ValueError("model failure counts must be typed positive observations")
        if any(not isinstance(cost, CostClass) for cost in self.observed_cost_classes):
            raise TypeError("observed model cost classes must be typed")
        if self.routing_authority:
            raise ValueError("model performance summary cannot authorize routing")


class ModelPerformanceTracker:
    def __init__(self) -> None:
        self._events: dict[str, ModelEvaluationEvent] = {}

    def record(self, event: ModelEvaluationEvent) -> None:
        if not isinstance(event, ModelEvaluationEvent):
            raise TypeError("model evaluation event is required")
        if event.event_id in self._events:
            raise ValueError("model evaluation event already exists")
        self._events[event.event_id] = event

    def summarize(self, *, tenant_id: str, owner_id: str, model_id: str, task_type: str) -> ModelPerformanceSummary:
        for name, value in (
            ("tenant_id", tenant_id), ("owner_id", owner_id),
            ("model_id", model_id), ("task_type", task_type),
        ):
            if not isinstance(value, str) or not value.strip() or len(value) > 240:
                raise ValueError(f"{name} must be bounded non-empty text")
        events = tuple(
            event for event in self._events.values()
            if event.tenant_id == tenant_id and event.owner_id == owner_id
            and event.model_id == model_id and event.task_type == task_type
        )
        attempts = len(events)
        failures = Counter(
            event.failure_class for event in events
            if event.failure_class is not ModelFailureClass.NONE
        )
        return ModelPerformanceSummary(
            tenant_id, owner_id, model_id, task_type, attempts,
            sum(event.successful for event in events),
            sum(event.structured_valid for event in events) / attempts if attempts else 0.0,
            sum(event.latency_ms for event in events) / attempts if attempts else 0.0,
            sum(event.quality_score for event in events) / attempts if attempts else 0.0,
            tuple(sorted(failures.items(), key=lambda item: item[0].value)),
            tuple(sorted({event.cost_class for event in events}, key=int)),
        )
