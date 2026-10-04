"""R85A MEDAR specialized agent contract tests."""

import pytest

from backend.medar.agent_contract import AgentContract, AgentOutput
from backend.medar.capabilities import MemoryPermission
from backend.medar.model_policy import ModelAccessPolicy
from backend.medar.request import CognitiveDomain, RiskClass


def _contract(**overrides):
    values = {
        "agent_id": "coding-agent",
        "domain": CognitiveDomain.CODING,
        "capabilities": ("code_analysis",),
        "allowed_tools": ("code_analysis_stub",),
        "memory_scope": (MemoryPermission.READ,),
        "risk_ceiling": RiskClass.MODERATE,
        "model_policy": ModelAccessPolicy.LOCAL_FIRST,
    }
    values.update(overrides)
    return AgentContract(**values)


def test_agent_contract_records_bounded_tools_memory_risk_and_model_policy():
    contract = _contract()

    assert contract.allowed_tools == ("code_analysis_stub",)
    assert contract.memory_scope == (MemoryPermission.READ,)
    assert contract.real_world_action_authority is False


def test_agent_cannot_receive_real_world_action_authority():
    with pytest.raises(ValueError, match="cannot have"):
        _contract(real_world_action_authority=True)


def test_agent_output_cannot_claim_action_performed():
    with pytest.raises(ValueError, match="cannot report"):
        AgentOutput("agent", "task", "summary", (), (), 0.5, action_performed=True)
