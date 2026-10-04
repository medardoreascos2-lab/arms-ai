"""R116A model evaluation tracks local synthetic metadata without authority."""

from datetime import datetime, timezone

import pytest

from backend.medar.model_performance import (
    ModelEvaluationEvent, ModelEvidenceOrigin, ModelFailureClass,
    ModelPerformanceTracker,
)
from backend.medar.model_profiles import CostClass, ModelLocality


NOW = datetime(2026, 10, 4, 18, tzinfo=timezone.utc)


def _event(
    event_id, successful, valid, latency, quality, failure,
    *, owner="owner-a", tenant="tenant-a", **overrides,
):
    values = {
        "event_id": event_id,
        "tenant_id": tenant,
        "owner_id": owner,
        "provider_id": "deterministic-local",
        "model_id": "local-test-model",
        "task_type": "structured coding",
        "successful": successful,
        "structured_valid": valid,
        "latency_ms": latency,
        "quality_score": quality,
        "failure_class": failure,
        "cost_class": CostClass.FREE,
        "locality": ModelLocality.LOCAL,
        "source_reference": f"synthetic-test:{event_id}",
        "evidence_origin": ModelEvidenceOrigin.SYNTHETIC_LOCAL,
        "observed_at": NOW,
    }
    values.update(overrides)
    return ModelEvaluationEvent(**values)


def test_tracker_measures_model_provider_task_validity_latency_quality_failure_cost_and_provenance():
    tracker = ModelPerformanceTracker()
    tracker.record(_event("e1", True, True, 10.0, 0.9, ModelFailureClass.NONE))
    tracker.record(_event("e2", False, False, 30.0, 0.1, ModelFailureClass.STRUCTURED_INVALID))
    tracker.record(_event("e3", True, True, 999.0, 1.0, ModelFailureClass.NONE, owner="other"))
    summary = tracker.summarize(
        tenant_id="tenant-a", owner_id="owner-a", provider_id="deterministic-local",
        model_id="local-test-model", task_type="structured coding",
    )
    assert summary.attempts == 2 and summary.successes == 1
    assert summary.structured_valid_rate == 0.5
    assert summary.average_latency_ms == 20.0
    assert summary.average_quality_score == 0.5
    assert dict(summary.failure_counts) == {ModelFailureClass.STRUCTURED_INVALID: 1}
    assert summary.observed_cost_classes == (CostClass.FREE,)
    assert summary.evidence_references == ("synthetic-test:e1", "synthetic-test:e2")
    assert not summary.routing_authority and not summary.external_call_authority


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
        tenant_id="tenant-a", owner_id="owner-a", provider_id="deterministic-local",
        model_id="other", task_type="coding",
    )
    assert empty.attempts == 0
    assert empty.average_quality_score == 0.0
    assert empty.failure_counts == ()


def test_only_synthetic_local_free_evidence_is_accepted():
    base = ("e1", True, True, 1.0, 1.0, ModelFailureClass.NONE)
    with pytest.raises(PermissionError):
        _event(*base, locality=ModelLocality.REMOTE)
    with pytest.raises(PermissionError):
        _event(*base, cost_class=CostClass.LOW)
    with pytest.raises(PermissionError):
        _event(*base, source_reference="external:e1")
    with pytest.raises(PermissionError):
        _event(*base, source_reference="synthetic-test:api_key: value")
    with pytest.raises(PermissionError):
        _event(*base, network_accessed=True)
    with pytest.raises(PermissionError):
        _event(*base, external_model_invoked=True)
    with pytest.raises(PermissionError):
        _event(*base, paid_api_used=True)


@pytest.mark.parametrize("field", (
    "provider_authority", "routing_authority", "external_call_authority",
    "tool_authority", "computer_authority", "broker_authority",
    "paper_authority", "live_authority", "scope_mutation_authority",
    "hidden_chain_of_thought_included",
))
def test_model_performance_evidence_cannot_grant_authority(field):
    with pytest.raises(ValueError):
        _event("e1", True, True, 1.0, 1.0, ModelFailureClass.NONE, **{field: True})


def test_cross_owner_tenant_and_provider_evidence_are_isolated():
    tracker = ModelPerformanceTracker()
    tracker.record(_event("a", True, True, 1.0, 1.0, ModelFailureClass.NONE))
    tracker.record(_event("b", True, True, 2.0, 1.0, ModelFailureClass.NONE, owner="other"))
    tracker.record(_event("c", True, True, 3.0, 1.0, ModelFailureClass.NONE, tenant="other"))
    tracker.record(_event(
        "d", True, True, 4.0, 1.0, ModelFailureClass.NONE,
        provider_id="other-provider",
    ))
    summary = tracker.summarize(
        tenant_id="tenant-a", owner_id="owner-a", provider_id="deterministic-local",
        model_id="local-test-model", task_type="structured coding",
    )
    assert summary.attempts == 1
    assert summary.evidence_references == ("synthetic-test:a",)
