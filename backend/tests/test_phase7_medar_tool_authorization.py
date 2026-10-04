"""R84C MEDAR tool authorization tests."""

import pytest

from backend.medar.request import CognitiveDomain, RiskClass
from backend.medar.tool_authorization import (
    ToolAuthorizationStatus,
    ToolAuthorityContext,
    execute_authorized,
)
from backend.medar.tool_contract import (
    SideEffectLevel,
    ToolCall,
    ToolContract,
    ToolResult,
    ToolResultStatus,
)
from backend.medar.tool_registry import ToolRegistry, default_tool_registry


def _call(tool_id="calculator", **overrides):
    values = {
        "call_id": "call-1",
        "request_id": "req-1",
        "tool_id": tool_id,
        "tenant_id": "tenant-1",
        "user_id": "user-1",
        "arguments": {"expression": "2+2"},
    }
    values.update(overrides)
    return ToolCall(**values)


def _authority(**overrides):
    values = {
        "request_id": "req-1",
        "tenant_id": "tenant-1",
        "user_id": "user-1",
        "allowed_tools": ("calculator",),
        "maximum_risk": RiskClass.LOW,
    }
    values.update(overrides)
    return ToolAuthorityContext(**values)


def test_authorized_safe_tool_executes():
    authorization, result = execute_authorized(default_tool_registry(), _call(), _authority())

    assert authorization.status is ToolAuthorizationStatus.ACCEPTED
    assert result.status is ToolResultStatus.SUCCESS
    assert result.output == {"value": 4}


class CountingTool:
    contract = ToolContract(
        "sensitive",
        "Sensitive test tool",
        CognitiveDomain.COMPUTER_ACTION,
        RiskClass.CRITICAL,
        {},
        {},
        True,
        True,
        SideEffectLevel.SENSITIVE,
    )

    def __init__(self):
        self.calls = 0

    def execute(self, call):
        self.calls += 1
        return ToolResult(call.call_id, "sensitive", ToolResultStatus.SUCCESS, {}, external_side_effects=True)


@pytest.mark.parametrize(
    "authority",
    [
        _authority(allowed_tools=()),
        _authority(tenant_id="other"),
        _authority(user_id="other"),
        _authority(maximum_risk=RiskClass.MODERATE),
        _authority(allowed_tools=("sensitive",), maximum_risk=RiskClass.CRITICAL),
        _authority(allowed_tools=("sensitive",), maximum_risk=RiskClass.CRITICAL, confirmation_grants=("call-1",)),
    ],
)
def test_rejected_tool_call_has_zero_invocations_and_side_effects(authority):
    tool = CountingTool()
    registry = ToolRegistry((tool,))
    call = _call("sensitive", arguments={})

    authorization, result = execute_authorized(registry, call, authority)

    assert authorization.status is ToolAuthorizationStatus.REJECTED
    assert result.status is ToolResultStatus.BLOCKED
    assert result.external_side_effects is False
    assert tool.calls == 0
