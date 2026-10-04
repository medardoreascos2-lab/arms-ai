"""Scoped, content-free observations of MEDAR tool performance."""

import math
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from backend.medar.request import CognitiveDomain
from backend.medar.tool_contract import ToolResultStatus


class ToolFailureClass(str, Enum):
    NONE = "NONE"
    BLOCKED = "BLOCKED"
    VALIDATION = "VALIDATION"
    EXECUTION = "EXECUTION"
    UNAVAILABLE = "UNAVAILABLE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ToolPerformanceEvent:
    event_id: str
    tenant_id: str
    owner_id: str
    tool_id: str
    domain: CognitiveDomain
    task_type: str
    status: ToolResultStatus
    failure_class: ToolFailureClass
    latency_ms: float
    observed_at: datetime
    execution_authority: bool = False

    def __post_init__(self) -> None:
        for name in ("event_id", "tenant_id", "owner_id", "tool_id", "task_type"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or len(value) > 240:
                raise ValueError(f"{name} must be bounded non-empty text")
        if not isinstance(self.domain, CognitiveDomain) or not isinstance(self.status, ToolResultStatus):
            raise TypeError("tool domain and status must be typed")
        if not isinstance(self.failure_class, ToolFailureClass):
            raise TypeError("tool failure class must be typed")
        if self.status is ToolResultStatus.SUCCESS and self.failure_class is not ToolFailureClass.NONE:
            raise ValueError("successful tool event cannot claim a failure")
        if self.status is not ToolResultStatus.SUCCESS and self.failure_class is ToolFailureClass.NONE:
            raise ValueError("unsuccessful tool event requires a failure class")
        if isinstance(self.latency_ms, bool) or not isinstance(self.latency_ms, (int, float)) or not math.isfinite(self.latency_ms) or self.latency_ms < 0:
            raise ValueError("tool latency must be a finite nonnegative value")
        if not isinstance(self.observed_at, datetime) or self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("tool observation time must be timezone-aware")
        if self.execution_authority:
            raise ValueError("tool performance evidence cannot grant execution authority")


@dataclass(frozen=True)
class ToolPerformanceSummary:
    tenant_id: str
    owner_id: str
    tool_id: str
    domain: CognitiveDomain
    task_type: str
    attempts: int
    successes: int
    success_rate: float
    average_latency_ms: float
    failure_counts: tuple[tuple[ToolFailureClass, int], ...]
    recommendation_authority: bool = False

    def __post_init__(self) -> None:
        for name in ("tenant_id", "owner_id", "tool_id", "task_type"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or len(value) > 240:
                raise ValueError(f"{name} must be bounded non-empty text")
        if not isinstance(self.domain, CognitiveDomain):
            raise TypeError("tool summary domain must be typed")
        if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in (self.attempts, self.successes)):
            raise ValueError("tool attempt counts must be nonnegative integers")
        if self.successes > self.attempts:
            raise ValueError("tool successes cannot exceed attempts")
        expected_rate = self.successes / self.attempts if self.attempts else 0.0
        if not math.isclose(self.success_rate, expected_rate):
            raise ValueError("tool success rate must match observed counts")
        if not math.isfinite(self.average_latency_ms) or self.average_latency_ms < 0:
            raise ValueError("tool average latency must be finite and nonnegative")
        if any(
            not isinstance(kind, ToolFailureClass) or kind is ToolFailureClass.NONE
            or isinstance(count, bool) or not isinstance(count, int) or count < 1
            for kind, count in self.failure_counts
        ):
            raise ValueError("tool failure counts must be typed positive observations")
        if self.recommendation_authority:
            raise ValueError("performance summary cannot authorize tool selection")


class ToolPerformanceTracker:
    def __init__(self) -> None:
        self._events: dict[str, ToolPerformanceEvent] = {}

    def record(self, event: ToolPerformanceEvent) -> None:
        if not isinstance(event, ToolPerformanceEvent):
            raise TypeError("tool performance event is required")
        if event.event_id in self._events:
            raise ValueError("tool performance event already exists")
        self._events[event.event_id] = event

    def summarize(
        self,
        *,
        tenant_id: str,
        owner_id: str,
        tool_id: str,
        domain: CognitiveDomain,
        task_type: str,
    ) -> ToolPerformanceSummary:
        for name, value in (
            ("tenant_id", tenant_id), ("owner_id", owner_id),
            ("tool_id", tool_id), ("task_type", task_type),
        ):
            if not isinstance(value, str) or not value.strip() or len(value) > 240:
                raise ValueError(f"{name} must be bounded non-empty text")
        if not isinstance(domain, CognitiveDomain):
            raise TypeError("tool summary domain must be typed")
        events = tuple(
            event for event in self._events.values()
            if event.tenant_id == tenant_id and event.owner_id == owner_id
            and event.tool_id == tool_id and event.domain is domain
            and event.task_type == task_type
        )
        attempts = len(events)
        successes = sum(event.status is ToolResultStatus.SUCCESS for event in events)
        failures = Counter(
            event.failure_class for event in events
            if event.failure_class is not ToolFailureClass.NONE
        )
        return ToolPerformanceSummary(
            tenant_id, owner_id, tool_id, domain, task_type, attempts, successes,
            successes / attempts if attempts else 0.0,
            sum(event.latency_ms for event in events) / attempts if attempts else 0.0,
            tuple(sorted(failures.items(), key=lambda item: item[0].value)),
        )
