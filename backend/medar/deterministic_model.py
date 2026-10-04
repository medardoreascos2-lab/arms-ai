"""Deterministic, in-process MEDAR model for tests only.

It performs no inference and must never be advertised as a real local model.
"""

import json
from enum import Enum

from backend.medar.local_model_provider import (
    LocalModelCapabilities,
    LocalModelDescriptor,
    LocalModelHealth,
    LocalProviderKind,
    ModelReadiness,
)
from backend.medar.model_policy import PrivacyClass
from backend.medar.model_provider import ModelInvocation, ModelKind, ModelResult


class FakeResponseMode(str, Enum):
    NORMAL = "NORMAL"
    FAILURE = "FAILURE"
    TIMEOUT = "TIMEOUT"
    MALFORMED = "MALFORMED"


class DeterministicModelProvider:
    provider_id = "deterministic-test"
    supported_kinds = (ModelKind.LOCAL_LLM, ModelKind.CODE_MODEL, ModelKind.REASONING_MODEL)
    is_local = True

    def __init__(self, model_id: str = "deterministic-test-model", mode: FakeResponseMode = FakeResponseMode.NORMAL):
        if not isinstance(model_id, str) or not model_id.strip():
            raise ValueError("model_id is required")
        if not isinstance(mode, FakeResponseMode):
            raise TypeError("mode must be FakeResponseMode")
        self._mode = mode
        self._descriptor = LocalModelDescriptor(
            self.provider_id,
            model_id,
            LocalProviderKind.DETERMINISTIC_TEST,
            LocalModelCapabilities(
                self.supported_kinds,
                4096,
                structured_output=True,
                tool_support=False,
                privacy_class=PrivacyClass.RESTRICTED,
            ),
        )

    @property
    def descriptor(self) -> LocalModelDescriptor:
        return self._descriptor

    def health(self) -> LocalModelHealth:
        return LocalModelHealth(ModelReadiness.READY, "deterministic test double; no inference")

    def is_available(self) -> bool:
        return self.health().available

    def invoke(self, invocation: ModelInvocation) -> ModelResult:
        if invocation.model_id != self.descriptor.model_id:
            raise ValueError("model_id does not match provider")
        if invocation.model_kind not in self.supported_kinds:
            raise ValueError("unsupported model kind")
        if self._mode is FakeResponseMode.FAILURE:
            raise RuntimeError("injected model failure")
        if self._mode is FakeResponseMode.TIMEOUT:
            raise TimeoutError("injected model timeout")
        if self._mode is FakeResponseMode.MALFORMED:
            output = '{"malformed":'
        elif invocation.structured_output_schema is not None:
            values = {}
            for key, kind in invocation.structured_output_schema.items():
                if not isinstance(key, str) or not key.strip():
                    raise ValueError("structured output keys must be non-empty")
                defaults = {"string": "test-value", "integer": 1, "number": 1.0, "boolean": True}
                if kind not in defaults:
                    raise ValueError("unsupported deterministic schema type")
                values[key] = defaults[kind]
            output = json.dumps(values, sort_keys=True)
        else:
            output = "TEST_COMPLETION: " + invocation.prompt.strip()
        return ModelResult(
            invocation.invocation_id,
            invocation.model_id,
            output,
            "Deterministic test response; no private reasoning stored.",
            len(invocation.prompt.split()),
            len(output.split()),
            ("provider:deterministic-test",),
            external_call_performed=False,
        )
