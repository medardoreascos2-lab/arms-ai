"""Specialized MEDAR agent contracts with explicit authority ceilings."""

from dataclasses import dataclass
from typing import Protocol

from backend.medar.capabilities import MemoryPermission
from backend.medar.model_policy import ModelAccessPolicy
from backend.medar.request import CognitiveDomain, RiskClass


@dataclass(frozen=True)
class AgentContract:
    agent_id: str
    domain: CognitiveDomain
    capabilities: tuple[str, ...]
    allowed_tools: tuple[str, ...]
    memory_scope: tuple[MemoryPermission, ...]
    risk_ceiling: RiskClass
    model_policy: ModelAccessPolicy
    real_world_action_authority: bool = False

    def __post_init__(self) -> None:
        if not self.agent_id.strip() or not self.capabilities:
            raise ValueError("agent identity and capabilities are required")
        for name in ("capabilities", "allowed_tools", "memory_scope"):
            values = getattr(self, name)
            if len(set(values)) != len(values):
                raise ValueError(f"{name} must be unique")
        if self.real_world_action_authority:
            raise ValueError("Phase 7 agents cannot have real-world action authority")


@dataclass(frozen=True)
class AgentInput:
    request_id: str
    task_id: str
    goal: str
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True)
class AgentOutput:
    agent_id: str
    task_id: str
    summary: str
    evidence: tuple[str, ...]
    warnings: tuple[str, ...]
    confidence: float
    action_performed: bool = False

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("agent confidence must be between zero and one")
        if self.action_performed:
            raise ValueError("Phase 7 agent output cannot report a real-world action")


class SpecializedAgent(Protocol):
    contract: AgentContract

    def analyze(self, input_data: AgentInput) -> AgentOutput: ...
