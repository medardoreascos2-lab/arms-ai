"""R96B MEDAR cognitive metrics tests."""

from backend.medar.cognitive_metrics import CognitiveMetrics


def test_metrics_capture_all_required_aggregate_dimensions():
    metrics = CognitiveMetrics()
    metrics.record_request(
        domains=("GENERAL", "WEB_RESEARCH"), tool_successes=1, tool_attempts=2,
        agent_failures=1, replans=1, memory_hit=True,
        uncertainty="MEDIUM_CONFIDENCE", latency_ms=20.0,
    )
    metrics.record_request(
        domains=("GENERAL",), memory_hit=False,
        uncertainty="LOW_CONFIDENCE", latency_ms=40.0,
    )
    snapshot = metrics.snapshot()
    assert snapshot.requests == 2
    assert snapshot.domain_routing == {"GENERAL": 2, "WEB_RESEARCH": 1}
    assert snapshot.tool_success_rate == 0.5
    assert snapshot.agent_failures == 1
    assert snapshot.replan_count == 1
    assert snapshot.memory_retrieval_hit_rate == 0.5
    assert snapshot.uncertainty == {"MEDIUM_CONFIDENCE": 1, "LOW_CONFIDENCE": 1}
    assert snapshot.average_latency_ms == 30.0


def test_empty_metrics_have_safe_zero_rates():
    snapshot = CognitiveMetrics().snapshot()
    assert snapshot.tool_success_rate == 0.0
    assert snapshot.memory_retrieval_hit_rate == 0.0
    assert snapshot.average_latency_ms == 0.0
