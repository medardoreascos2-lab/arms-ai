"""R101A-D readiness, local-first fallback, and untrusted output validation."""

from dataclasses import replace

import pytest

from backend.medar.deterministic_model import DeterministicModelProvider, FakeResponseMode
from backend.medar.local_model_provider import ModelReadiness
from backend.medar.model_output_validation import validate_model_output
from backend.medar.model_profiles import (
    CapabilityStrength, CostClass, LatencyClass, ModelCapabilityProfile,
    ModelLocality, ModelProfileRegistry,
)
from backend.medar.model_provider import ModelInvocation, ModelKind, ModelResult
from backend.medar.model_router import ModelRoutingRequirement, TaskComplexity
from backend.medar.request import CognitiveDomain
from backend.medar.runtime_model_router import RuntimeModelRouter


def _profile(model_id, locality=ModelLocality.LOCAL):
    return ModelCapabilityProfile(
        model_id,
        ModelKind.LOCAL_LLM if locality is ModelLocality.LOCAL else ModelKind.REMOTE_LLM,
        4096,
        CapabilityStrength.BASIC,
        CapabilityStrength.BASIC,
        LatencyClass.LOW,
        CostClass.FREE,
        locality,
        False,
        False,
        True,
    )


def _requirement():
    return ModelRoutingRequirement(
        CognitiveDomain.GENERAL,
        TaskComplexity.SIMPLE,
        1024,
        CapabilityStrength.BASIC,
        remote_allowed=True,
    )


def _invocation(schema=None):
    return ModelInvocation("inv-1", "requested-model", ModelKind.LOCAL_LLM, "Answer safely", schema)


class _HealthFailProvider(DeterministicModelProvider):
    def health(self):
        raise TimeoutError("no health response")


def test_runtime_route_excludes_missing_remote_and_unhealthy_providers():
    profiles = ModelProfileRegistry((
        _profile("deterministic-test-model"),
        _profile("remote", ModelLocality.REMOTE),
        _profile("missing"),
    ))
    router = RuntimeModelRouter(profiles, (_HealthFailProvider(),))
    route = router.route(_requirement())
    assert route.candidates == ()
    assert "remote:REMOTE_DISABLED" in route.rejection_reasons
    assert "missing:PROVIDER_MISSING" in route.rejection_reasons
    assert route.external_call_authorized is False


def test_runtime_fallback_stays_local_and_returns_validated_result():
    first = DeterministicModelProvider("a-model", FakeResponseMode.TIMEOUT)
    second = DeterministicModelProvider("b-model")
    profiles = ModelProfileRegistry((_profile("a-model"), _profile("b-model"), _profile("remote", ModelLocality.REMOTE)))
    routed = RuntimeModelRouter(profiles, (first, second)).invoke(_requirement(), _invocation({"answer": "string"}))
    assert routed.attempted_models == ("a-model", "b-model")
    assert routed.output.structured == {"answer": "test-value"}
    assert routed.output.authorized_actions == ()
    assert routed.external_call_performed is False


def test_malformed_output_falls_back_then_exhaustion_fails_closed():
    malformed = DeterministicModelProvider("a-model", FakeResponseMode.MALFORMED)
    good = DeterministicModelProvider("b-model")
    profiles = ModelProfileRegistry((_profile("a-model"), _profile("b-model")))
    response = RuntimeModelRouter(profiles, (malformed, good)).invoke(_requirement(), _invocation({"answer": "string"}))
    assert response.attempted_models == ("a-model", "b-model")
    with pytest.raises(RuntimeError, match="no ready local model"):
        RuntimeModelRouter(ModelProfileRegistry((_profile("a-model"),)), (malformed,)).invoke(
            _requirement(), _invocation({"answer": "string"})
        )


@pytest.mark.parametrize("output", [
    '{"answer": "ok", "live_authority": true}',
    '{"answer": "ok", "nested": {"tool_calls": []}}',
    '{"answer": 5}',
    '{"answer":',
])
def test_schema_mismatch_malformed_or_authority_claim_rejected(output):
    invocation = _invocation({"answer": "string"})
    result = ModelResult(invocation.invocation_id, invocation.model_id, output, "No private reasoning", 1, 1, (), False)
    with pytest.raises(ValueError):
        validate_model_output(invocation, result)


def test_large_invalid_encoding_and_external_results_rejected():
    invocation = _invocation()
    base = ModelResult("inv-1", "requested-model", "safe", "No private reasoning", 1, 1, (), False)
    for result in (
        replace(base, output="x" * 16_385),
        replace(base, output="\ud800"),
        replace(base, external_call_performed=True),
        replace(base, model_id="other"),
    ):
        with pytest.raises(ValueError):
            validate_model_output(invocation, result)


def test_remote_invocation_cannot_route_to_local_provider():
    router = RuntimeModelRouter(
        ModelProfileRegistry((_profile("deterministic-test-model"),)),
        (DeterministicModelProvider(),),
    )
    with pytest.raises(ValueError, match="remote invocation"):
        router.invoke(_requirement(), ModelInvocation("inv-1", "remote", ModelKind.REMOTE_LLM, "hello"))
