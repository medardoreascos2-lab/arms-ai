"""Content-free multimodal metrics with no media or transcript fields."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
import re
from typing import Mapping


_SAFE_LABEL = re.compile(r"^[A-Z0-9_]{1,64}$")


class MultimodalMetric(str, Enum):
    VOICE_REQUESTS = "voice_requests"
    VISION_REQUESTS = "vision_requests"
    CAMERA_SESSIONS = "camera_sessions"
    AVATAR_SESSIONS = "avatar_sessions"
    NOTIFICATION_PRESENTATIONS = "notification_presentations"
    PERMISSION_DENIALS = "permission_denials"
    DEGRADED_STATES = "degraded_states"
    LATENCY = "latency"
    ERRORS = "errors"


@dataclass(frozen=True)
class MetricEvent:
    metric: MultimodalMetric
    observed_at: datetime
    count: int = 1
    duration_ms: float | None = None
    status: str = "OK"

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() != timedelta(0):
            raise ValueError("observed_at must be UTC")
        if self.count <= 0:
            raise ValueError("metric count must be positive")
        if self.duration_ms is not None and self.duration_ms < 0:
            raise ValueError("metric duration must be nonnegative")
        if not _SAFE_LABEL.fullmatch(self.status):
            raise ValueError("metric status must be a bounded categorical label")

    def content_free_payload(self) -> Mapping[str, str | int | float | None]:
        payload = asdict(self)
        payload["metric"] = self.metric.value
        payload["observed_at"] = self.observed_at.isoformat()
        return payload


class ContentFreeMultimodalMetrics:
    def __init__(self) -> None:
        self._counts = {metric: 0 for metric in MultimodalMetric}
        self._events: list[MetricEvent] = []

    def record(self, event: MetricEvent) -> None:
        self._counts[event.metric] += event.count
        self._events.append(event)

    def count(self, metric: MultimodalMetric) -> int:
        return self._counts[metric]

    def payloads(self) -> tuple[Mapping[str, str | int | float | None], ...]:
        return tuple(event.content_free_payload() for event in self._events)