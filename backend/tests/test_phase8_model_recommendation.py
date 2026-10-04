"""R116B model recommendations are evidence based and never authorize escalation."""

from datetime import datetime, timezone

import pytest

from backend.medar.model_performance import (
    ModelEvaluationEvent, ModelEvidenceOrigin, ModelFailureClass,
    ModelPerformanceTracker,
)
from backend.medar.model_profiles import (
    CapabilityStrength, CostClass, LatencyClass, ModelCapabilityProfile,
    ModelLocality,
)
from backend.medar.model_provider import ModelKind
from backend.medar.model_recommendation import ModelPrivacyClass, recommend_models


NOW = datetime(2026, 10, 4, 19, tzinfo=timezone.utc)


def _profile(model_id, *, locality=ModelLocality.LOCAL, cost=CostClass.FREE):
    return ModelCapabilityProfile(
        model_id, ModelKind.LOCAL_LLM if locality is ModelLocality.LOCAL else ModelKind.REASONING_MODEL,
        4096, CapabilityStrength.STRONG, CapabilityStrength.BASIC,
        LatencyClass.LOW, cost, locality, False, False, True,
    )


def _summary(provider_id, model_id, observations, *, owner="owner-a"):
    tracker = ModelPerformanceTracker()
    for index, (successful, valid, latency, quality) in enumerate(observations):
        failure = ModelFailureClass.NONE if successful else ModelFailureClass.QUALITY_REJECTED
        tracker.record(ModelEvaluationEvent(
            f"{provider_id}-{model_id}-{index}", "tenant-a", owner, provider_id,
            model_id, "coding", successful, valid, latency, quality, failure,
            CostClass.FREE, ModelLocality.LOCAL,
            f"synthetic-test:{provider_id}:{model_id}:{index}",
            ModelEvidenceOrigin.SYNTHETIC_LOCAL, NOW,
        ))
    return tracker.summarize(
        tenant_id="tenant-a", owner_id=owner, provider_id=provider_id,
        model_id=model_id, task_type="coding",
    )


def test_local_free_models_are_ranked_by_observed_validity_quality_failure_and_latency():
    strong = _summary("local-provider", "strong", ((True, True, 20.0, 0.9), (True, True, 10.0, 0.8)))
    weak = _summary("local-provider", "weak", ((True, True, 1.0, 0.4), (False, False, 2.0, 0.1)))
    result = recommend_models(
        (weak, strong), (_profile("weak"), _profile("strong")),
        tenant_id="tenant-a", owner_id="owner-a", task_type="coding",
        privacy_class=ModelPrivacyClass.INTERNAL,
    )
    assert result.recommended is not None
    assert result.recommended.model_id == "strong"
    assert tuple(item.model_id for item in result.ranked_candidates) == ("strong", "weak")
    assert not result.routing_authority
    assert not result.provider_authority
    assert not result.external_call_authority
    assert not result.paid_api_authority


def test_remote_or_paid_profile_is_review_only_even_with_better_evidence():
    remote = _summary("synthetic-provider", "remote", ((True, True, 1.0, 1.0),) * 2)
    paid = _summary("synthetic-provider", "paid", ((True, True, 1.0, 1.0),) * 2)
    result = recommend_models(
        (remote, paid),
        (
            _profile("remote", locality=ModelLocality.REMOTE),
            _profile("paid", cost=CostClass.LOW),
        ),
        tenant_id="tenant-a", owner_id="owner-a", task_type="coding",
        privacy_class=ModelPrivacyClass.SENSITIVE,
    )
    assert result.recommended is None
    assert result.ranked_candidates == ()
    assert dict(result.review_candidates) == {
        "paid": "PAID_REQUIRES_EXPLICIT_POLICY",
        "remote": "REMOTE_REQUIRES_EXPLICIT_POLICY",
    }


def test_cross_owner_and_duplicate_evidence_are_rejected():
    summary = _summary("local-provider", "model", ((True, True, 1.0, 1.0),) * 2)
    other = _summary("local-provider", "other", ((True, True, 1.0, 1.0),) * 2, owner="other")
    with pytest.raises(PermissionError):
        recommend_models(
            (summary, other), (_profile("model"), _profile("other")),
            tenant_id="tenant-a", owner_id="owner-a", task_type="coding",
            privacy_class=ModelPrivacyClass.INTERNAL,
        )
    with pytest.raises(ValueError):
        recommend_models(
            (summary, summary), (_profile("model"),),
            tenant_id="tenant-a", owner_id="owner-a", task_type="coding",
            privacy_class=ModelPrivacyClass.INTERNAL,
        )
