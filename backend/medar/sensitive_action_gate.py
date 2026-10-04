"""Explicit confirmation gate for sensitive future computer actions."""

from dataclasses import dataclass
from enum import Enum

from backend.medar.computer_action import ComputerActionProposal


class SensitiveActionKind(str, Enum):
    DELETION = "DELETION"
    INSTALL = "INSTALL"
    CREDENTIAL_ACCESS = "CREDENTIAL_ACCESS"
    FINANCIAL_ACTION = "FINANCIAL_ACTION"
    NETWORK_CONFIGURATION = "NETWORK_CONFIGURATION"
    ADMIN_CHANGE = "ADMIN_CHANGE"


@dataclass(frozen=True)
class ExplicitConfirmation:
    action_id: str
    user_id: str
    approved: bool


@dataclass(frozen=True)
class SensitiveActionDecision:
    confirmation_valid: bool
    blocking_reasons: tuple[str, ...]
    execution_authorized: bool = False


def evaluate_sensitive_action(
    proposal: ComputerActionProposal,
    kind: SensitiveActionKind,
    confirmation: ExplicitConfirmation | None,
    *,
    expected_user_id: str,
) -> SensitiveActionDecision:
    if not isinstance(kind, SensitiveActionKind):
        return SensitiveActionDecision(False, ("UNKNOWN_SENSITIVE_ACTION",))
    if confirmation is None:
        return SensitiveActionDecision(False, ("EXPLICIT_CONFIRMATION_REQUIRED",))
    if confirmation.action_id != proposal.action_id or confirmation.user_id != expected_user_id:
        return SensitiveActionDecision(False, ("CONFIRMATION_SCOPE_MISMATCH",))
    if not confirmation.approved:
        return SensitiveActionDecision(False, ("CONFIRMATION_DECLINED",))
    return SensitiveActionDecision(True, ())
