"""R100C deterministic model behavior and failure injection."""

import json

import pytest

from backend.medar.deterministic_model import DeterministicModelProvider, FakeResponseMode
from backend.medar.local_model_provider import LocalProviderKind
from backend.medar.model_provider import ModelInvocation, ModelKind


def _invocation(schema=None):
    return ModelInvocation("inv-1", "deterministic-test-model", ModelKind.LOCAL_LLM, "Summarize local evidence", schema)


def test_text_completion_is_repeatable_and_offline():
    model = DeterministicModelProvider()
    first = model.invoke(_invocation())
    second = model.invoke(_invocation())
    assert first == second
    assert first.output == "TEST_COMPLETION: Summarize local evidence"
    assert first.external_call_performed is False
    assert model.descriptor.provider_kind is LocalProviderKind.DETERMINISTIC_TEST


def test_structured_output_is_repeatable_and_schema_shaped():
    result = DeterministicModelProvider().invoke(_invocation({"answer": "string", "count": "integer", "ok": "boolean"}))
    assert json.loads(result.output) == {"answer": "test-value", "count": 1, "ok": True}
    assert result.external_call_performed is False


@pytest.mark.parametrize("mode,error", [
    (FakeResponseMode.FAILURE, RuntimeError),
    (FakeResponseMode.TIMEOUT, TimeoutError),
])
def test_failure_modes_raise_without_network_or_execution(mode, error):
    with pytest.raises(error):
        DeterministicModelProvider(mode=mode).invoke(_invocation())


def test_malformed_response_can_exercise_output_validator():
    result = DeterministicModelProvider(mode=FakeResponseMode.MALFORMED).invoke(_invocation({"answer": "string"}))
    with pytest.raises(json.JSONDecodeError):
        json.loads(result.output)
    assert result.external_call_performed is False


def test_model_identity_and_schema_are_fail_closed():
    model = DeterministicModelProvider()
    with pytest.raises(ValueError, match="model_id"):
        model.invoke(ModelInvocation("inv-1", "other-model", ModelKind.LOCAL_LLM, "hello"))
    with pytest.raises(ValueError, match="schema"):
        model.invoke(_invocation({"answer": "object"}))
