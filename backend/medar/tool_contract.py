"""Canonical MEDAR tool contracts with explicit side-effect metadata."""

from dataclasses import dataclass
from enum import Enum, IntEnum
from typing import Any, Mapping, Protocol

from backend.medar.request import CognitiveDomain, RiskClass


class SideEffectLevel(IntEnum):
    NONE = 0
    READ_ONLY = 1
    REVERSIBLE = 2
    SENSITIVE = 3
    DESTRUCTIVE = 4


class ToolResultStatus(str, Enum):
    SUCCESS = "SUCCESS"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class ToolContract:
    tool_id: str
    name: str
    domain: CognitiveDomain
    risk_class: RiskClass
    input_schema: Mapping[str, str]
    output_schema: Mapping[str, str]
    requires_confirmation: bool
    network_required: bool
    side_effect_level: SideEffectLevel
    execution_authority: bool = False

    def __post_init__(self) -> None:
        if not self.tool_id.strip() or not self.name.strip():
            raise ValueError("tool identity and name are required")
        if self.side_effect_level >= SideEffectLevel.SENSITIVE and not self.requires_confirmation:
            raise ValueError("sensitive tool requires confirmation")
        if self.execution_authority:
            raise ValueError("Phase 7 tool contracts cannot grant execution authority")


@dataclass(frozen=True)
class ToolCall:
    call_id: str
    request_id: str
    tool_id: str
    tenant_id: str
    user_id: str
    arguments: Mapping[str, Any]


@dataclass(frozen=True)
class ToolResult:
    call_id: str
    tool_id: str
    status: ToolResultStatus
    output: Mapping[str, Any]
    error_category: str | None = None
    external_side_effects: bool = False

    def __post_init__(self) -> None:
        if self.external_side_effects:
            raise ValueError("Phase 7 tool results cannot report external side effects")


class CognitiveTool(Protocol):
    contract: ToolContract

    def execute(self, call: ToolCall) -> ToolResult: ...
