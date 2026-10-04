"""R84B safe MEDAR tool registry tests."""

import pytest

from backend.medar.tool_contract import SideEffectLevel, ToolCall, ToolResultStatus
from backend.medar.tool_registry import default_tool_registry


def _call(tool_id, arguments):
    return ToolCall("call-1", "req-1", tool_id, "tenant-1", "user-1", arguments)


def test_registry_contains_only_expected_safe_local_tools():
    registry = default_tool_registry()

    assert {tool.contract.tool_id for tool in registry.tools} == {
        "calculator",
        "web_search_stub",
        "document_reader_stub",
        "code_analysis_stub",
        "financial_analysis_stub",
        "memory_lookup_stub",
    }
    assert all(tool.contract.network_required is False for tool in registry.tools)
    assert all(tool.contract.side_effect_level is SideEffectLevel.NONE for tool in registry.tools)
    assert all(tool.contract.execution_authority is False for tool in registry.tools)


def test_calculator_accepts_arithmetic_and_rejects_code_execution():
    calculator = default_tool_registry().get("calculator")

    success = calculator.execute(_call("calculator", {"expression": "2 + 5 * 3"}))
    rejected = calculator.execute(_call("calculator", {"expression": "__import__('os').system('x')"}))

    assert success.output == {"value": 17}
    assert success.status is ToolResultStatus.SUCCESS
    assert rejected.status is ToolResultStatus.FAILED
    assert rejected.external_side_effects is False


def test_stub_returns_explicit_stub_evidence():
    result = default_tool_registry().get("web_search_stub").execute(
        _call("web_search_stub", {"query": "current evidence"})
    )

    assert result.output == {"stub": True, "received_keys": ("query",)}
    assert result.external_side_effects is False


def test_unknown_tool_fails_closed():
    with pytest.raises(KeyError, match="unregistered"):
        default_tool_registry().get("terminal")
