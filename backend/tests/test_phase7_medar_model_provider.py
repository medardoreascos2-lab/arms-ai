"""R82A provider-neutral model abstraction tests."""

from backend.medar.model_provider import ModelInvocation, ModelKind, ModelProvider, ModelResult


class LocalTestProvider:
    provider_id = "local-test"
    supported_kinds = (ModelKind.LOCAL_LLM, ModelKind.CODE_MODEL)
    is_local = True

    def is_available(self) -> bool:
        return True

    def invoke(self, invocation: ModelInvocation) -> ModelResult:
        return ModelResult(
            invocation.invocation_id,
            invocation.model_id,
            "bounded output",
            "Processed locally with the requested model kind.",
            4,
            2,
            ("provider:local-test",),
            external_call_performed=False,
        )


def _use_provider(provider: ModelProvider) -> ModelResult:
    return provider.invoke(
        ModelInvocation("inv-1", "model-1", ModelKind.LOCAL_LLM, "Summarize evidence")
    )


def test_local_test_double_satisfies_provider_contract_without_external_call():
    result = _use_provider(LocalTestProvider())

    assert result.output == "bounded output"
    assert result.external_call_performed is False
    assert result.reasoning_summary


def test_model_kinds_cover_future_provider_classes():
    assert {item.value for item in ModelKind} == {
        "LOCAL_LLM",
        "REMOTE_LLM",
        "CODE_MODEL",
        "REASONING_MODEL",
        "VISION_MODEL",
        "EMBEDDING_MODEL",
    }
