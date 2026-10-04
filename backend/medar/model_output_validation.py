"""Fail-closed validation for untrusted local model output."""

import json
import re
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from backend.medar.model_provider import ModelInvocation, ModelResult


_FORBIDDEN_KEYS = frozenset({
    "action", "actions", "authorized_actions", "broker_authority", "code_modification_authority",
    "computer_control", "credential_access", "deployment_authority", "exchange_authority", "execute",
    "execution_authority", "external_call", "function_call", "live_authority", "memory_mutation_authority",
    "model_update_authority", "order", "orders", "paper_authority", "permissions", "portfolio_mutation_authority",
    "production_autonomy", "routing_authority", "secret_access", "shell_command", "system_override", "tool_calls",
    "trading_authority",
})


def _normalized_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", key.casefold()).strip("_")


def _check_authority_fields(value: object) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if not isinstance(key, str) or _normalized_key(key) in _FORBIDDEN_KEYS:
                raise ValueError("model output contains unsupported authority or action field")
            _check_authority_fields(nested)
    elif isinstance(value, list):
        for nested in value:
            _check_authority_fields(nested)


@dataclass(frozen=True)
class ValidatedModelOutput:
    result: ModelResult
    structured: Mapping[str, object] | None
    authorized_actions: tuple[()] = ()

    def __post_init__(self) -> None:
        if self.authorized_actions:
            raise ValueError("model output cannot authorize actions")


def validate_model_output(
    invocation: ModelInvocation,
    result: ModelResult,
    *,
    max_output_bytes: int = 16_384,
) -> ValidatedModelOutput:
    if isinstance(max_output_bytes, bool) or not isinstance(max_output_bytes, int) or max_output_bytes <= 0:
        raise ValueError("max_output_bytes must be positive")
    if result.invocation_id != invocation.invocation_id or result.model_id != invocation.model_id:
        raise ValueError("model output identity mismatch")
    if result.external_call_performed:
        raise ValueError("unexpected external model call")
    try:
        encoded = result.output.encode("utf-8", errors="strict")
    except UnicodeError as exc:
        raise ValueError("model output has invalid encoding") from exc
    if not encoded or len(encoded) > max_output_bytes:
        raise ValueError("model output size is invalid")
    structured = None
    if invocation.structured_output_schema is not None or result.output.lstrip().startswith(("{", "[")):
        try:
            decoded = json.loads(result.output)
        except json.JSONDecodeError as exc:
            raise ValueError("malformed model JSON") from exc
        _check_authority_fields(decoded)
        if invocation.structured_output_schema is not None:
            if not isinstance(decoded, dict) or set(decoded) != set(invocation.structured_output_schema):
                raise ValueError("model output schema keys mismatch")
            type_checks = {
                "string": lambda x: isinstance(x, str),
                "integer": lambda x: type(x) is int,
                "number": lambda x: type(x) in (int, float),
                "boolean": lambda x: type(x) is bool,
            }
            for key, expected in invocation.structured_output_schema.items():
                if expected not in type_checks or not type_checks[expected](decoded[key]):
                    raise ValueError("model output schema type mismatch")
        if isinstance(decoded, dict):
            structured = MappingProxyType(decoded)
    elif invocation.structured_output_schema is not None:
        raise ValueError("structured model output is not JSON")
    return ValidatedModelOutput(result, structured)
