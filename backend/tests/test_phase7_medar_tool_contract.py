"""R84A canonical MEDAR tool contract tests."""

import pytest

from backend.medar.request import CognitiveDomain, RiskClass
from backend.medar.tool_contract import SideEffectLevel, ToolContract, ToolResultStatus


def test_tool_contract_exposes_required_authority_metadata():
    contract = ToolContract(
        "web_search_stub",
        "Web search stub",
        CognitiveDomain.WEB_RESEARCH,
        RiskClass.MODERATE,
        {"query": "string"},
        {"results": "array"},
        False,
        False,
        SideEffectLevel.NONE,
    )

    assert contract.input_schema == {"query": "string"}
    assert contract.network_required is False
    assert contract.execution_authority is False


def test_sensitive_tool_requires_confirmation():
    with pytest.raises(ValueError, match="requires confirmation"):
        ToolContract(
            "sensitive",
            "Sensitive",
            CognitiveDomain.COMPUTER_ACTION,
            RiskClass.CRITICAL,
            {},
            {},
            False,
            False,
            SideEffectLevel.SENSITIVE,
        )


def test_result_status_has_explicit_blocked_state():
    assert {item.value for item in ToolResultStatus} == {"SUCCESS", "BLOCKED", "FAILED"}
