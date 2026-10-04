"""R100B local model provider metadata and readiness contract."""

import pytest

from backend.medar.local_model_provider import (
    LocalModelCapabilities,
    LocalModelDescriptor,
    LocalModelHealth,
    LocalModelProvider,
    LocalProviderKind,
    ModelReadiness,
)
from backend.medar.model_policy import PrivacyClass
from backend.medar.model_provider import ModelInvocation, ModelKind, ModelResult


def _capabilities(**changes):
    fields = dict(
        supported_kinds=(ModelKind.LOCAL_LLM,),
        context_length=4096,
        structured_output=True,
        tool_support=False,
        privacy_class=PrivacyClass.RESTRICTED,
    )
    fields.update(changes)
    return LocalModelCapabilities(**fields)


class _Provider:
    provider_id = "test"
    supported_kinds = (ModelKind.LOCAL_LLM,)
    is_local = True

    @property
    def descriptor(self):
        return LocalModelDescriptor("test", "test-model", LocalProviderKind.IN_PROCESS, _capabilities())

    def health(self):
        return LocalModelHealth(ModelReadiness.READY, "deterministic test provider")

    def is_available(self):
        return self.health().available

    def invoke(self, invocation):
        return ModelResult(invocation.invocation_id, invocation.model_id, "test", "Test response", 0, 1, (), False)


def test_local_provider_implements_phase7_invocation_and_phase8_metadata():
    provider: LocalModelProvider = _Provider()
    assert provider.descriptor.provider_id == provider.provider_id
    assert provider.descriptor.capabilities.context_length == 4096
    assert provider.descriptor.capabilities.structured_output is True
    assert provider.descriptor.capabilities.tool_support is False
    assert provider.descriptor.capabilities.privacy_class is PrivacyClass.RESTRICTED
    assert provider.is_available() is True
    result = provider.invoke(ModelInvocation("request", "test-model", ModelKind.LOCAL_LLM, "hello"))
    assert result.external_call_performed is False


@pytest.mark.parametrize("state", [
    ModelReadiness.DEGRADED,
    ModelReadiness.UNAVAILABLE,
    ModelReadiness.MISCONFIGURED,
    ModelReadiness.PRIVACY_BLOCKED,
])
def test_only_ready_provider_is_available(state):
    assert LocalModelHealth(state, "not ready").available is False


@pytest.mark.parametrize("changes", [
    {"supported_kinds": ()},
    {"supported_kinds": (ModelKind.REMOTE_LLM,)},
    {"context_length": 0},
    {"context_length": True},
    {"privacy_class": "RESTRICTED"},
])
def test_invalid_or_remote_capability_claims_rejected(changes):
    with pytest.raises((ValueError, TypeError)):
        _capabilities(**changes)
