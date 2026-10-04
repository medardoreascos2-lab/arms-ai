"""R92B MEDAR computer action contract tests."""

import pytest

from backend.medar.computer_action import ComputerActionProposal
from backend.medar.computer_permissions import ComputerPermissionLevel
from backend.medar.request import RiskClass


def test_action_contract_captures_required_schema_without_os_authority():
    action = ComputerActionProposal(
        "action-1", "editor", "open", "readme.md", {"line": 1}, RiskClass.LOW,
        ComputerPermissionLevel.LEVEL_1_SAFE_ACTIONS, False, "file displayed",
    )
    assert action.app == "editor"
    assert action.arguments == {"line": 1}
    assert action.expected_result == "file displayed"
    assert action.execution_authorized is False


def test_sensitive_level_requires_confirmation_and_never_execution_authority():
    with pytest.raises(ValueError, match="require confirmation"):
        ComputerActionProposal(
            "a", "app", "act", "target", {}, RiskClass.HIGH,
            ComputerPermissionLevel.LEVEL_4_SENSITIVE_CONFIRM, False, "result",
        )
    with pytest.raises(ValueError, match="cannot authorize"):
        ComputerActionProposal(
            "a", "app", "act", "target", {}, RiskClass.LOW,
            ComputerPermissionLevel.LEVEL_1_SAFE_ACTIONS, False, "result", True,
        )
