"""R92C MEDAR sensitive action gate tests."""

import pytest

from backend.medar.computer_action import ComputerActionProposal
from backend.medar.computer_permissions import ComputerPermissionLevel
from backend.medar.request import RiskClass
from backend.medar.sensitive_action_gate import (
    ExplicitConfirmation,
    SensitiveActionKind,
    evaluate_sensitive_action,
)


def _proposal():
    return ComputerActionProposal(
        "action-1", "system", "delete", "target", {}, RiskClass.HIGH,
        ComputerPermissionLevel.LEVEL_4_SENSITIVE_CONFIRM, True, "target deleted",
    )


@pytest.mark.parametrize("kind", tuple(SensitiveActionKind))
def test_every_sensitive_action_kind_requires_scoped_explicit_confirmation(kind):
    assert evaluate_sensitive_action(
        _proposal(), kind, None, expected_user_id="user-1",
    ).blocking_reasons == ("EXPLICIT_CONFIRMATION_REQUIRED",)
    decision = evaluate_sensitive_action(
        _proposal(), kind, ExplicitConfirmation("action-1", "user-1", True),
        expected_user_id="user-1",
    )
    assert decision.confirmation_valid is True
    assert decision.execution_authorized is False


def test_confirmation_for_another_user_or_action_is_rejected():
    decision = evaluate_sensitive_action(
        _proposal(), SensitiveActionKind.DELETION,
        ExplicitConfirmation("other", "user-2", True), expected_user_id="user-1",
    )
    assert decision.confirmation_valid is False
    assert decision.blocking_reasons == ("CONFIRMATION_SCOPE_MISMATCH",)
