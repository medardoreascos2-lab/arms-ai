"""R100D/E local HTTP model adapters; all tests use injected offline transport."""

import pytest

from backend.medar.local_http_models import LlamaCppModelProvider, OllamaModelProvider
from backend.medar.local_http_transport import LoopbackJsonTransport
from backend.medar.local_model_provider import ModelReadiness
from backend.medar.model_provider import ModelInvocation, ModelKind


class FakeTransport:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def request(self, method, path, payload=None):
        self.calls.append((method, path, payload))
        value = self.responses[path]
        if isinstance(value, Exception):
            raise value
        return value


def _invocation(schema=None):
    return ModelInvocation("request-1", "installed-model", ModelKind.LOCAL_LLM, "Reply OK", schema)


def test_ollama_health_requires_model_listing_and_successful_generation():
    fake = FakeTransport({
        "/api/tags": {"models": [{"name": "installed-model"}]},
        "/api/generate": {"response": "OK", "done": True, "prompt_eval_count": 2, "eval_count": 1},
    })
    provider = OllamaModelProvider("installed-model", transport=fake)
    assert provider.health().readiness is ModelReadiness.READY
    assert [call[1] for call in fake.calls] == ["/api/tags", "/api/generate"]
    result = provider.invoke(_invocation({"answer": "string"}))
    assert result.output == "OK" and result.external_call_performed is False
    assert fake.calls[-1][2]["format"] == "json"
    assert fake.calls[-1][2]["think"] is False
    assert fake.calls[-1][2]["options"] == {"num_ctx": 4096, "num_predict": 1024, "temperature": 0, "seed": 42}
    assert fake.calls[-1][2]["stream"] is False


def test_ollama_listed_model_that_cannot_answer_is_not_ready():
    fake = FakeTransport({
        "/api/tags": {"models": [{"name": "installed-model"}]},
        "/api/generate": {"response": "", "done": True},
    })
    assert OllamaModelProvider("installed-model", transport=fake).health().readiness is ModelReadiness.UNAVAILABLE


def test_ollama_unlisted_model_does_not_get_invoked():
    fake = FakeTransport({"/api/tags": {"models": []}})
    assert OllamaModelProvider("installed-model", transport=fake).is_available() is False
    assert len(fake.calls) == 1


def test_llama_cpp_health_requires_successful_inference():
    fake = FakeTransport({
        "/health": {"status": "ok"},
        "/v1/chat/completions": {"choices": [{"message": {"content": "OK"}}], "usage": {"prompt_tokens": 2, "completion_tokens": 1}},
    })
    provider = LlamaCppModelProvider("installed-model", transport=fake)
    assert provider.health().readiness is ModelReadiness.READY
    result = provider.invoke(_invocation({"answer": "string"}))
    assert result.output == "OK" and result.input_tokens == 2
    assert result.external_call_performed is False
    assert fake.calls[-1][2]["response_format"] == {"type": "json_object"}


def test_llama_cpp_health_does_not_trust_health_endpoint_alone():
    fake = FakeTransport({
        "/health": {"status": "ok"},
        "/v1/chat/completions": {"choices": []},
    })
    assert LlamaCppModelProvider("installed-model", transport=fake).health().readiness is ModelReadiness.UNAVAILABLE


def test_llama_cpp_tool_calls_are_rejected():
    fake = FakeTransport({
        "/v1/chat/completions": {"choices": [{"message": {"content": "OK", "tool_calls": [{"name": "trade"}]}}]},
    })
    with pytest.raises(ValueError, match="unsupported"):
        LlamaCppModelProvider("installed-model", transport=fake).invoke(_invocation())


@pytest.mark.parametrize("provider", [OllamaModelProvider, LlamaCppModelProvider])
def test_network_is_disabled_by_default(provider):
    instance = provider("installed-model")
    assert instance.health().readiness is ModelReadiness.PRIVACY_BLOCKED
    assert instance.is_available() is False
    with pytest.raises(PermissionError):
        instance.invoke(_invocation())


@pytest.mark.parametrize("url", [
    "https://127.0.0.1:11434",
    "http://example.com:11434",
    "http://localhost:11434",
    "http://127.0.0.1:11434/other",
    "http://user:secret@127.0.0.1:11434",
    "http://127.0.0.1:11434?next=remote",
])
def test_transport_rejects_non_loopback_or_ambiguous_endpoints(url):
    with pytest.raises(ValueError):
        LoopbackJsonTransport(url, network_enabled=True)


def test_transport_never_dispatches_when_network_disabled():
    with pytest.raises(PermissionError):
        LoopbackJsonTransport("http://127.0.0.1:11434").request("GET", "/api/tags")
