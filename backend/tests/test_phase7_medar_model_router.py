"""R82C MEDAR model routing tests."""

from backend.medar.model_profiles import (
    CapabilityStrength,
    CostClass,
    LatencyClass,
    ModelCapabilityProfile,
    ModelLocality,
    ModelProfileRegistry,
)
from backend.medar.model_provider import ModelKind
from backend.medar.model_router import (
    ModelRouteStatus,
    ModelRouter,
    ModelRoutingRequirement,
    TaskComplexity,
)
from backend.medar.request import CognitiveDomain


def _profile(model_id, locality, cost, reasoning=CapabilityStrength.STRONG, available=True):
    return ModelCapabilityProfile(
        model_id,
        ModelKind.LOCAL_LLM if locality is ModelLocality.LOCAL else ModelKind.REMOTE_LLM,
        16_384,
        reasoning,
        CapabilityStrength.STRONG,
        LatencyClass.LOW,
        cost,
        locality,
        True,
        False,
        True,
        available,
    )


def _requirement(**overrides):
    values = {
        "domain": CognitiveDomain.GENERAL,
        "complexity": TaskComplexity.MODERATE,
        "minimum_context_window": 4096,
        "minimum_reasoning": CapabilityStrength.BASIC,
        "remote_allowed": True,
        "maximum_cost": CostClass.MEDIUM,
    }
    values.update(overrides)
    return ModelRoutingRequirement(**values)


def test_local_adequate_model_is_preferred_over_remote():
    registry = ModelProfileRegistry(
        (
            _profile("remote", ModelLocality.REMOTE, CostClass.LOW),
            _profile("local", ModelLocality.LOCAL, CostClass.FREE),
        )
    )

    route = ModelRouter(registry).route(_requirement())

    assert route.status is ModelRouteStatus.SELECTED
    assert route.selected.model_id == "local"
    assert route.external_call_authorized is False


def test_remote_fallback_requires_explicit_policy():
    registry = ModelProfileRegistry((_profile("remote", ModelLocality.REMOTE, CostClass.LOW),))

    denied = ModelRouter(registry).route(_requirement(remote_allowed=False))
    allowed = ModelRouter(registry).route(_requirement(remote_allowed=True))

    assert denied.status is ModelRouteStatus.BLOCKED
    assert allowed.selected.model_id == "remote"
    assert allowed.external_call_authorized is False


def test_unmet_capability_fails_closed():
    registry = ModelProfileRegistry(
        (_profile("local", ModelLocality.LOCAL, CostClass.FREE, CapabilityStrength.BASIC),)
    )

    route = ModelRouter(registry).route(
        _requirement(minimum_reasoning=CapabilityStrength.ADVANCED, local_only=True)
    )

    assert route.status is ModelRouteStatus.BLOCKED
    assert route.selected is None
    assert route.rejection_reasons == ("local:REASONING_TOO_WEAK",)
