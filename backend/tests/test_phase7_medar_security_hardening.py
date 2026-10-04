"""R97A Phase 7 authority-boundary hardening tests."""

import pytest

from backend.medar.capabilities import Capability, MemoryPermission
from backend.medar.domain_router import DomainRoute, DomainRouteStatus
from backend.medar.model_policy import ModelAccessDecision, ModelAccessPolicy, PrivacyClass
from backend.medar.request import CognitiveDomain, RiskClass
from backend.medar.response import ActionProposal
from backend.medar.sensitive_action_gate import SensitiveActionDecision
from backend.medar.tool_contract import SideEffectLevel, ToolContract, ToolResult, ToolResultStatus


def test_capability_domain_and_action_proposal_cannot_mint_execution_authority():
    with pytest.raises(ValueError, match="execution authority"):
        Capability(
            "cap", CognitiveDomain.GENERAL, "description", RiskClass.LOW, (),
            (MemoryPermission.NONE,), False, execution_authority=True,
        )
    with pytest.raises(ValueError, match="authorize action"):
        DomainRoute(DomainRouteStatus.SINGLE_DOMAIN, (CognitiveDomain.GENERAL,), (), (), True)
    with pytest.raises(ValueError, match="authorize execution"):
        ActionProposal("action", "description", True, True)


def test_tool_contract_and_result_cannot_claim_external_execution_or_side_effects():
    with pytest.raises(ValueError, match="execution authority"):
        ToolContract(
            "tool", "Tool", CognitiveDomain.GENERAL, RiskClass.LOW, {}, {}, False,
            False, SideEffectLevel.NONE, execution_authority=True,
        )
    with pytest.raises(ValueError, match="external side effects"):
        ToolResult("call", "tool", ToolResultStatus.SUCCESS, {}, external_side_effects=True)


def test_model_and_confirmation_decisions_cannot_mint_external_authority():
    with pytest.raises(ValueError, match="external calls"):
        ModelAccessDecision(
            ModelAccessPolicy.REMOTE_ALLOWED, PrivacyClass.PUBLIC, False, False, True, False, True,
        )
    with pytest.raises(ValueError, match="OS execution"):
        SensitiveActionDecision(True, (), True)
