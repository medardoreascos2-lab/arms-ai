"""Optional Ollama and llama.cpp adapters with explicit loopback access."""

from typing import Mapping

from backend.medar.local_http_transport import JsonTransport, LoopbackJsonTransport
from backend.medar.local_model_provider import (
    LocalModelCapabilities,
    LocalModelDescriptor,
    LocalModelHealth,
    LocalProviderKind,
    ModelReadiness,
)
from backend.medar.model_policy import PrivacyClass
from backend.medar.model_provider import ModelInvocation, ModelKind, ModelResult


def _count(value: object) -> int:
    return value if type(value) is int and value >= 0 else 0


def _text(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("local model returned empty or invalid text")
    return value


class _LocalHttpModel:
    supported_kinds = (ModelKind.LOCAL_LLM,)
    is_local = True

    def __init__(
        self,
        model_id: str,
        *,
        provider_id: str,
        provider_kind: LocalProviderKind,
        base_url: str,
        context_length: int,
        transport: JsonTransport | None,
        network_enabled: bool,
    ):
        self.provider_id = provider_id
        self._descriptor = LocalModelDescriptor(
            provider_id,
            model_id,
            provider_kind,
            LocalModelCapabilities(
                self.supported_kinds,
                context_length,
                structured_output=True,
                tool_support=False,
                privacy_class=PrivacyClass.RESTRICTED,
            ),
        )
        validated_transport = LoopbackJsonTransport(base_url, network_enabled=network_enabled)
        self._transport = transport if transport is not None else validated_transport

    @property
    def descriptor(self) -> LocalModelDescriptor:
        return self._descriptor

    def is_available(self) -> bool:
        return self.health().available

    def _check_invocation(self, invocation: ModelInvocation) -> None:
        if invocation.model_id != self.descriptor.model_id or invocation.model_kind not in self.supported_kinds:
            raise ValueError("local model identity or kind mismatch")

    def _result(self, invocation: ModelInvocation, output: object, input_tokens: object, output_tokens: object) -> ModelResult:
        return ModelResult(
            invocation.invocation_id,
            invocation.model_id,
            _text(output),
            "Local model output; internal reasoning was not retained.",
            _count(input_tokens),
            _count(output_tokens),
            (f"provider:{self.provider_id}",),
            external_call_performed=False,
        )

    def _probe(self) -> LocalModelHealth:
        try:
            self.invoke(ModelInvocation("health-probe", self.descriptor.model_id, ModelKind.LOCAL_LLM, "Reply with OK."))
        except PermissionError:
            return LocalModelHealth(ModelReadiness.PRIVACY_BLOCKED, "LOCAL_NETWORK_DISABLED")
        except (OSError, TimeoutError, ValueError, KeyError, TypeError, AttributeError):
            return LocalModelHealth(ModelReadiness.UNAVAILABLE, "LOCAL_INFERENCE_PROBE_FAILED")
        return LocalModelHealth(ModelReadiness.READY, "LOCAL_INFERENCE_PROBE_SUCCEEDED")


class OllamaModelProvider(_LocalHttpModel):
    def __init__(
        self,
        model_id: str,
        *,
        base_url: str = "http://127.0.0.1:11434",
        context_length: int = 4096,
        transport: JsonTransport | None = None,
        network_enabled: bool = False,
    ):
        super().__init__(
            model_id,
            provider_id="ollama",
            provider_kind=LocalProviderKind.OLLAMA,
            base_url=base_url,
            context_length=context_length,
            transport=transport,
            network_enabled=network_enabled,
        )

    def health(self) -> LocalModelHealth:
        try:
            models = self._transport.request("GET", "/api/tags").get("models")
            if not isinstance(models, list) or not any(
                isinstance(item, dict) and self.descriptor.model_id in (item.get("name"), item.get("model"))
                for item in models
            ):
                return LocalModelHealth(ModelReadiness.UNAVAILABLE, "MODEL_NOT_LISTED")
        except PermissionError:
            return LocalModelHealth(ModelReadiness.PRIVACY_BLOCKED, "LOCAL_NETWORK_DISABLED")
        except (OSError, TimeoutError, ValueError, KeyError, TypeError, AttributeError):
            return LocalModelHealth(ModelReadiness.UNAVAILABLE, "OLLAMA_HEALTH_FAILED")
        return self._probe()

    def invoke(self, invocation: ModelInvocation) -> ModelResult:
        self._check_invocation(invocation)
        payload: dict[str, object] = {
            "model": self.descriptor.model_id,
            "prompt": invocation.prompt,
            "stream": False,
            "think": False,
            "options": {"num_ctx": self.descriptor.capabilities.context_length, "num_predict": 1024, "temperature": 0, "seed": 42},
        }
        if invocation.structured_output_schema is not None:
            payload["format"] = "json"
        response = self._transport.request("POST", "/api/generate", payload)
        if response.get("done") is False:
            raise ValueError("incomplete Ollama response")
        return self._result(
            invocation,
            response.get("response"),
            response.get("prompt_eval_count"),
            response.get("eval_count"),
        )


class LlamaCppModelProvider(_LocalHttpModel):
    def __init__(
        self,
        model_id: str,
        *,
        base_url: str = "http://127.0.0.1:8080",
        context_length: int = 4096,
        transport: JsonTransport | None = None,
        network_enabled: bool = False,
    ):
        super().__init__(
            model_id,
            provider_id="llama-cpp",
            provider_kind=LocalProviderKind.LLAMA_CPP,
            base_url=base_url,
            context_length=context_length,
            transport=transport,
            network_enabled=network_enabled,
        )

    def health(self) -> LocalModelHealth:
        try:
            status = self._transport.request("GET", "/health").get("status")
            if status not in ("ok", "healthy"):
                return LocalModelHealth(ModelReadiness.UNAVAILABLE, "LLAMA_CPP_HEALTH_FAILED")
        except PermissionError:
            return LocalModelHealth(ModelReadiness.PRIVACY_BLOCKED, "LOCAL_NETWORK_DISABLED")
        except (OSError, TimeoutError, ValueError, KeyError, TypeError, AttributeError):
            return LocalModelHealth(ModelReadiness.UNAVAILABLE, "LLAMA_CPP_HEALTH_FAILED")
        return self._probe()

    def invoke(self, invocation: ModelInvocation) -> ModelResult:
        self._check_invocation(invocation)
        payload: dict[str, object] = {
            "model": self.descriptor.model_id,
            "messages": [{"role": "user", "content": invocation.prompt}],
            "temperature": 0,
            "max_tokens": 1024,
        }
        if invocation.structured_output_schema is not None:
            payload["response_format"] = {"type": "json_object"}
        response = self._transport.request("POST", "/v1/chat/completions", payload)
        choices = response.get("choices")
        if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], Mapping):
            raise ValueError("invalid llama.cpp choices")
        message = choices[0].get("message")
        if not isinstance(message, Mapping) or message.get("tool_calls"):
            raise ValueError("invalid or unsupported llama.cpp message")
        usage = response.get("usage")
        usage = usage if isinstance(usage, Mapping) else {}
        return self._result(invocation, message.get("content"), usage.get("prompt_tokens"), usage.get("completion_tokens"))
