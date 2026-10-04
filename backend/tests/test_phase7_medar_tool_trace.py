"""R84D redacted MEDAR tool trace tests."""

import pytest

from backend.medar.tool_contract import ToolCall, ToolResult, ToolResultStatus
from backend.medar.tool_trace import ToolTraceStore, build_tool_trace


def test_trace_hashes_inputs_results_and_identity_scope():
    call = ToolCall(
        "call-1",
        "req-1",
        "memory_lookup_stub",
        "tenant-secret",
        "user-private",
        {"query": "sensitive medical phrase"},
    )
    result = ToolResult(
        "call-1",
        "memory_lookup_stub",
        ToolResultStatus.SUCCESS,
        {"answer": "private result"},
    )

    trace = build_tool_trace(call, result, started_at="t1", finished_at="t2")

    assert len(trace.input_hash) == 64
    assert len(trace.result_hash) == 64
    assert trace.tenant_scope_hash != "tenant-secret"
    assert trace.user_scope_hash != "user-private"
    assert trace.raw_content_stored is False
    assert "sensitive" not in repr(trace)
    assert "private result" not in repr(trace)


def test_trace_store_is_append_only_by_call_id():
    call = ToolCall("call-1", "req-1", "calculator", "tenant", "user", {"expression": "2+2"})
    result = ToolResult("call-1", "calculator", ToolResultStatus.SUCCESS, {"value": 4})
    trace = build_tool_trace(call, result, started_at="t1", finished_at="t2")
    store = ToolTraceStore()
    store.append(trace)

    with pytest.raises(ValueError, match="duplicate"):
        store.append(trace)
    assert store.records["call-1"] is trace
