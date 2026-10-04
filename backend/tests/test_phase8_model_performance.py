"""R116A model evaluation tracks bounded metadata without prompt content."""

from datetime import datetime, timezone

import pytest

from backend.medar.model_performance import (
    ModelEvaluationEvent, ModelFailureClass, ModelPerformanceTracker,
)
from backend.medar.model_profiles import CostClass


NOW = datetime(2026, 10, 4, 18, tzinfo=timezone.utc)


def _event(event_id, successful, valid, latency, quality, failure, *, owner="owner-a"):
    return ModelEvaluationEvent(
        event_id, "tenant-a", owner, "local-test-model", "structured coding",
        successful, valid, latency, quality, failure, CostClass.FREE, NOW,
    )


def test_tracker_measures_model_task_validity_latency_quality_failure_and_cost():
    tracker = ModelPerformanceTracker()
    tracker.record(_event("e1", True, True, 10.0, 0.9, ModelFailureClass.NONE))
    tracker.record(_event("e2", False, False, 30.0, 0.1, ModelFailureClass.STRUCTURED_INVALID))
    tracker.record(_event("e3", True, True, 999.0, 1.0, ModelFailureClass.NONE, owner="other"))
    summary = tracker.summarize(
        tenant_id="tenant-a", owner_id="owner-a",
        model_id="local-test-model", task_type="structured coding",
    )
    assert summary.attempts == 2 and summary.successes == 1
    assert summary.structured_valid_rate == 0.5
    assert summary.average_latency_ms == 20.0
    assert summary.average_quality_score == 0.5
    assert dict(summary.failure_counts) == {ModelFailureClass.STRUCTURED_INVALID: 1}
    assert summary.observed_cost_classes == (CostClass.FREE,)
    assert not summary.routing_authority


def test_invalid_model_evaluation_invariants_are_rejected():
    with pytest.raises(ValueError):
        _event("e1", True, True, 1.0, 1.0, ModelFailureClass.TIMEOUT)
    with pytest.raises(ValueError):
        _event("e1", False, True, 1.0, 0.0, ModelFailureClass.NONE)
    with pytest.raises(ValueError):
        _event("e1", True, False, 1.0, 1.0, ModelFailureClass.NONE)
    with pytest.raises(ValueError):
        _event("e1", True, True, float("nan"), 1.0, ModelFailureClass.NONE)
    with pytest.raises(ValueError):
        _event("e1", True, True, 1.0, 1.1, ModelFailureClass.NONE)


def test_duplicate_observation_is_rejected_and_empty_summary_is_zero():
    tracker = ModelPerformanceTracker()
    event = _event("e1", True, True, 1.0, 1.0, ModelFailureClass.NONE)
    tracker.record(event)
    with pytest.raises(ValueError):
        tracker.record(event)
    empty = tracker.summarize(
        tenant_id="tenant-a", owner_id="owner-a", model_id="other", task_type="coding",
    )
    assert empty.attempts == 0
    assert empty.average_quality_score == 0.0
    assert empty.failure_counts == ()
