"""Non-executable schema for future computer action proposals."""

from dataclasses import dataclass
from typing import Any, Mapping

from backend.medar.computer_permissions import ComputerPermissionLevel
from backend.medar.request import RiskClass


@dataclass(frozen=True)
class ComputerActionProposal:
    action_id: str
    app: str
    action: str
    target: str
    arguments: Mapping[str, Any]
    risk: RiskClass
    required_permission: ComputerPermissionLevel
    confirmation_required: bool
    expected_result: str
    execution_authorized: bool = False

    def __post_init__(self) -> None:
        for name in ("action_id", "app", "action", "target", "expected_result"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be non-empty text")
        if not isinstance(self.risk, RiskClass):
            raise TypeError("risk must be RiskClass")
        if not isinstance(self.required_permission, ComputerPermissionLevel):
            raise TypeError("required_permission must be typed")
        if self.required_permission >= ComputerPermissionLevel.LEVEL_4_SENSITIVE_CONFIRM:
            if not self.confirmation_required:
                raise ValueError("sensitive computer actions must require confirmation")
        if self.execution_authorized:
            raise ValueError("Phase 7 computer action proposals cannot authorize execution")
