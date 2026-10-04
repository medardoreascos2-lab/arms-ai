"""Fail-closed authorization evaluated before every MEDAR tool invocation."""

from dataclasses import dataclass
from enum import Enum

from backend.medar.request import RiskClass
from backend.medar.tool_contract import ToolCall, ToolContract, ToolResult, ToolResultStatus
from backend.medar.tool_registry import ToolRegistry


class ToolAuthorizationStatus(str, Enum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


_RISK_ORDER = {
    RiskClass.LOW: 0,
    RiskClass.MODERATE: 1,
    RiskClass.HIGH: 2,
    RiskClass.CRITICAL: 3,
}


@dataclass(frozen=True)
class ToolAuthorityContext:
    request_id: str
    tenant_id: str
    user_id: str
    allowed_tools: tuple[str, ...]
    maximum_risk: RiskClass
    confirmation_grants: tuple[str, ...] = ()
    network_allowed: bool = False


@dataclass(frozen=True)
class ToolAuthorizationResult:
    status: ToolAuthorizationStatus
    reasons: tuple[str, ...]
    invocation_allowed: bool


def authorize_tool_call(
    contract: ToolContract,
    call: ToolCall,
    authority: ToolAuthorityContext,
) -> ToolAuthorizationResult:
    reasons: list[str] = []
    if call.request_id != authority.request_id:
        reasons.append("REQUEST_SCOPE_MISMATCH")
    if call.tenant_id != authority.tenant_id:
        reasons.append("TENANT_SCOPE_MISMATCH")
    if call.user_id != authority.user_id:
        reasons.append("USER_SCOPE_MISMATCH")
    if call.tool_id != contract.tool_id:
        reasons.append("TOOL_ID_MISMATCH")
    if contract.tool_id not in authority.allowed_tools:
        reasons.append("TOOL_NOT_ALLOWED")
    if _RISK_ORDER[contract.risk_class] > _RISK_ORDER[authority.maximum_risk]:
        reasons.append("RISK_CEILING_EXCEEDED")
    if contract.requires_confirmation and call.call_id not in authority.confirmation_grants:
        reasons.append("CONFIRMATION_REQUIRED")
    if contract.network_required and not authority.network_allowed:
        reasons.append("NETWORK_NOT_ALLOWED")
    if reasons:
        return ToolAuthorizationResult(ToolAuthorizationStatus.REJECTED, tuple(reasons), False)
    return ToolAuthorizationResult(ToolAuthorizationStatus.ACCEPTED, ("AUTHORIZED_FOR_THIS_CALL",), True)


def execute_authorized(
    registry: ToolRegistry,
    call: ToolCall,
    authority: ToolAuthorityContext,
) -> tuple[ToolAuthorizationResult, ToolResult]:
    tool = registry.get(call.tool_id)
    authorization = authorize_tool_call(tool.contract, call, authority)
    if not authorization.invocation_allowed:
        return authorization, ToolResult(
            call.call_id,
            call.tool_id,
            ToolResultStatus.BLOCKED,
            {},
            "AUTHORIZATION_REJECTED",
            external_side_effects=False,
        )
    return authorization, tool.execute(call)
