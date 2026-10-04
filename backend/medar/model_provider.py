"""Provider-neutral model contracts with no external implementation."""

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Protocol


class ModelKind(str, Enum):
    LOCAL_LLM = "LOCAL_LLM"
    REMOTE_LLM = "REMOTE_LLM"
    CODE_MODEL = "CODE_MODEL"
    REASONING_MODEL = "REASONING_MODEL"
    VISION_MODEL = "VISION_MODEL"
    EMBEDDING_MODEL = "EMBEDDING_MODEL"


@dataclass(frozen=True)
class ModelInvocation:
    invocation_id: str
    model_id: str
    model_kind: ModelKind
    prompt: str
    structured_output_schema: Mapping[str, str] | None = None

    def __post_init__(self) -> None:
        if not self.invocation_id.strip() or not self.model_id.strip() or not self.prompt.strip():
            raise ValueError("model invocation identity and prompt are required")


@dataclass(frozen=True)
class ModelResult:
    invocation_id: str
    model_id: str
    output: str
    reasoning_summary: str
    input_tokens: int
    output_tokens: int
    provider_evidence: tuple[str, ...]
    external_call_performed: bool

    def __post_init__(self) -> None:
        if self.input_tokens < 0 or self.output_tokens < 0:
            raise ValueError("token counts cannot be negative")
        if not self.output.strip():
            raise ValueError("model output must not be blank")


class ModelProvider(Protocol):
    provider_id: str
    supported_kinds: tuple[ModelKind, ...]
    is_local: bool

    def is_available(self) -> bool: ...

    def invoke(self, invocation: ModelInvocation) -> ModelResult: ...
