"""R82B MEDAR model capability profile tests."""

import pytest

from backend.medar.model_profiles import (
    CapabilityStrength,
    CostClass,
    LatencyClass,
    ModelCapabilityProfile,
    ModelLocality,
    ModelProfileRegistry,
)
from backend.medar.model_provider import ModelKind


def _profile(model_id="local-general", **overrides):
    values = {
        "model_id": model_id,
        "kind": ModelKind.LOCAL_LLM,
        "context_window": 8192,
        "reasoning_strength": CapabilityStrength.STRONG,
        "coding_strength": CapabilityStrength.BASIC,
        "latency_class": LatencyClass.LOW,
        "cost_class": CostClass.FREE,
        "locality": ModelLocality.LOCAL,
        "tool_call_support": True,
        "vision_support": False,
        "structured_output_support": True,
    }
    values.update(overrides)
    return ModelCapabilityProfile(**values)


def test_profile_records_routing_capabilities_without_vendor_assumptions():
    profile = _profile()

    assert profile.context_window == 8192
    assert profile.locality is ModelLocality.LOCAL
    assert profile.tool_call_support is True
    assert profile.vision_support is False


def test_registry_is_unique_and_queryable():
    local = _profile()
    remote = _profile(
        "remote-reasoning",
        kind=ModelKind.REMOTE_LLM,
        locality=ModelLocality.REMOTE,
        cost_class=CostClass.MEDIUM,
    )
    registry = ModelProfileRegistry((local, remote))

    assert registry.get("remote-reasoning") is remote
    with pytest.raises(ValueError, match="duplicate"):
        ModelProfileRegistry((local, local))


def test_inconsistent_locality_fails_closed():
    with pytest.raises(ValueError, match="cannot claim local"):
        _profile(kind=ModelKind.REMOTE_LLM)
