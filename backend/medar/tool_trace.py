"""Redacted, append-only MEDAR tool execution trace."""

from dataclasses import dataclass
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Any, Mapping

from backend.medar.tool_contract import ToolCall, ToolResult, ToolResultStatus


def _digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return sha256(payload).hexdigest()


@dataclass(frozen=True)
class ToolExecutionTrace:
    call_id: str
    request_id: str
    tool_id: str
    tenant_scope_hash: str
    user_scope_hash: str
    input_hash: str
    started_at: str
    finished_at: str
    status: ToolResultStatus
    result_hash: str
    error_category: str | None
    raw_content_stored: bool = False


def build_tool_trace(
    call: ToolCall,
    result: ToolResult,
    *,
    started_at: str,
    finished_at: str,
) -> ToolExecutionTrace:
    if call.call_id != result.call_id or call.tool_id != result.tool_id:
        raise ValueError("tool trace identity mismatch")
    if not started_at.strip() or not finished_at.strip():
        raise ValueError("tool trace timestamps are required")
    return ToolExecutionTrace(
        call.call_id,
        call.request_id,
        call.tool_id,
        _digest(call.tenant_id),
        _digest(call.user_id),
        _digest(call.arguments),
        started_at,
        finished_at,
        result.status,
        _digest(result.output),
        result.error_category,
    )


class ToolTraceStore:
    def __init__(self):
        self._records: dict[str, ToolExecutionTrace] = {}

    def append(self, trace: ToolExecutionTrace) -> None:
        if trace.call_id in self._records:
            raise ValueError("duplicate tool trace")
        self._records[trace.call_id] = trace

    @property
    def records(self) -> Mapping[str, ToolExecutionTrace]:
        return MappingProxyType(dict(self._records))
