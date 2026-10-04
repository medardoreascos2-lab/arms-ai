from datetime import datetime, timezone
import json

import pytest

from backend.multimodal.observability import (
    ContentFreeMultimodalMetrics,
    MetricEvent,
    MultimodalMetric,
)

NOW = datetime(2026, 10, 4, 12, tzinfo=timezone.utc)


def test_all_required_metrics_are_content_free_and_counted():
    metrics = ContentFreeMultimodalMetrics()
    for metric in MultimodalMetric:
        metrics.record(MetricEvent(metric=metric, observed_at=NOW, duration_ms=2.5, status="SYNTHETIC"))
    assert {item.value for item in MultimodalMetric} == {
        "voice_requests", "vision_requests", "camera_sessions", "avatar_sessions",
        "notification_presentations", "permission_denials", "degraded_states", "latency", "errors",
    }
    assert all(metrics.count(metric) == 1 for metric in MultimodalMetric)
    serialized = json.dumps(metrics.payloads())
    for forbidden in ("raw_media", "transcript", "prompt", "image_bytes", "audio_bytes", "content_reference"):
        assert forbidden not in serialized


def test_metric_schema_cannot_accept_raw_content_fields():
    with pytest.raises(TypeError):
        MetricEvent(metric=MultimodalMetric.VOICE_REQUESTS, observed_at=NOW, raw_media=b"secret")
    with pytest.raises(TypeError):
        MetricEvent(metric=MultimodalMetric.VISION_REQUESTS, observed_at=NOW, transcript="secret")


@pytest.mark.parametrize("changes", [
    {"count": 0}, {"duration_ms": -1}, {"status": "contains free form text"},
])
def test_invalid_metric_values_fail_closed(changes):
    values = dict(metric=MultimodalMetric.ERRORS, observed_at=NOW)
    values.update(changes)
    with pytest.raises(ValueError):
        MetricEvent(**values)