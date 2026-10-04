"""R123B model metrics aggregate only scoped synthetic local evidence."""

from datetime import datetime, timezone

import pytest

from backend.medar.model_metrics import summarize_model_metrics
from backend.medar.model_performance import ModelEvaluationEvent, ModelEvidenceOrigin, ModelFailureClass
from backend.medar.model_profiles import CostClass, ModelLocality
from backend.medar.sqlite_memory_store import MemoryScope

NOW = datetime(2026, 10, 5, 0, 30, tzinfo=timezone.utc)
SCOPE = MemoryScope("tenant-a", "owner-a")


def _event(event_id, success, failure=ModelFailureClass.NONE, owner="owner-a"):
    return ModelEvaluationEvent(event_id, "tenant-a", owner, "deterministic-local", "local-test-model", "coding", success, success, 10.0 if success else 30.0, 0.9 if success else 0.1, failure, CostClass.FREE, ModelLocality.LOCAL, f"synthetic-test:{event_id}", ModelEvidenceOrigin.SYNTHETIC_LOCAL, NOW)


def test_model_metrics_compute_content_free_rates_latency_quality_and_failures():
    snapshot = summarize_model_metrics((_event("e1", True), _event("e2", False, ModelFailureClass.TIMEOUT)), SCOPE)
    assert snapshot.attempts == 2 and snapshot.successes == 1
    assert snapshot.success_rate == 0.5 and snapshot.structured_valid_rate == 0.5
    assert snapshot.average_latency_ms == 20.0 and snapshot.average_quality_score == 0.5
    assert snapshot.by_provider == {"deterministic-local": 2}
    assert snapshot.by_model == {"local-test-model": 2}
    assert snapshot.by_task_type == {"coding": 2}
    assert snapshot.failures == {"TIMEOUT": 1}
    assert not snapshot.external_calls and not snapshot.paid_api_calls and not snapshot.routing_authority
    assert "synthetic-test:e1" not in repr(snapshot)


def test_model_metrics_fail_closed_on_cross_owner_evidence_and_empty_rates_are_zero():
    with pytest.raises(PermissionError, match="scope"):
        summarize_model_metrics((_event("foreign", True, owner="other"),), SCOPE)
    empty = summarize_model_metrics((), SCOPE)
    assert empty.success_rate == 0.0 and empty.structured_valid_rate == 0.0
