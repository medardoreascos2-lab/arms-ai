"""Deterministic model selection across local and remote capability profiles."""

from dataclasses import dataclass
from enum import Enum, IntEnum

from backend.medar.model_profiles import (
    CapabilityStrength,
    CostClass,
    ModelCapabilityProfile,
    ModelLocality,
    ModelProfileRegistry,
)
from backend.medar.model_provider import ModelKind
from backend.medar.request import CognitiveDomain


class TaskComplexity(IntEnum):
    SIMPLE = 1
    MODERATE = 2
    COMPLEX = 3


class ModelRouteStatus(str, Enum):
    SELECTED = "SELECTED"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class ModelRoutingRequirement:
    domain: CognitiveDomain
    complexity: TaskComplexity
    minimum_context_window: int
    minimum_reasoning: CapabilityStrength
    minimum_coding: CapabilityStrength = CapabilityStrength.NONE
    required_kind: ModelKind | None = None
    tool_calls_required: bool = False
    vision_required: bool = False
    structured_output_required: bool = True
    local_only: bool = False
    remote_allowed: bool = False
    maximum_cost: CostClass = CostClass.LOW


@dataclass(frozen=True)
class ModelRoute:
    status: ModelRouteStatus
    selected: ModelCapabilityProfile | None
    considered: tuple[str, ...]
    rejection_reasons: tuple[str, ...]
    external_call_authorized: bool = False

    def __post_init__(self) -> None:
        if self.external_call_authorized:
            raise ValueError("Phase 7 model routing cannot authorize external calls")


class ModelRouter:
    def __init__(self, registry: ModelProfileRegistry):
        self._registry = registry

    def route(self, requirement: ModelRoutingRequirement) -> ModelRoute:
        accepted: list[ModelCapabilityProfile] = []
        rejected: list[str] = []
        for profile in self._registry.profiles:
            reason = self._rejection_reason(profile, requirement)
            if reason:
                rejected.append(f"{profile.model_id}:{reason}")
            else:
                accepted.append(profile)
        if not accepted:
            return ModelRoute(
                ModelRouteStatus.BLOCKED,
                None,
                tuple(item.model_id for item in self._registry.profiles),
                tuple(rejected) or ("NO_MODEL_PROFILES",),
            )
        accepted.sort(
            key=lambda item: (
                item.locality is ModelLocality.REMOTE,
                int(item.cost_class),
                -int(item.reasoning_strength),
                -int(item.coding_strength),
                item.model_id,
            )
        )
        selected = accepted[0]
        return ModelRoute(
            ModelRouteStatus.SELECTED,
            selected,
            tuple(item.model_id for item in self._registry.profiles),
            tuple(rejected),
            external_call_authorized=False,
        )

    @staticmethod
    def _rejection_reason(profile: ModelCapabilityProfile, requirement: ModelRoutingRequirement) -> str | None:
        if not profile.available:
            return "UNAVAILABLE"
        if requirement.required_kind is not None and profile.kind is not requirement.required_kind:
            return "MODEL_KIND_MISMATCH"
        if profile.context_window < requirement.minimum_context_window:
            return "CONTEXT_TOO_SMALL"
        if profile.reasoning_strength < requirement.minimum_reasoning:
            return "REASONING_TOO_WEAK"
        if profile.coding_strength < requirement.minimum_coding:
            return "CODING_TOO_WEAK"
        if requirement.tool_calls_required and not profile.tool_call_support:
            return "TOOL_CALLS_UNSUPPORTED"
        if requirement.vision_required and not profile.vision_support:
            return "VISION_UNSUPPORTED"
        if requirement.structured_output_required and not profile.structured_output_support:
            return "STRUCTURED_OUTPUT_UNSUPPORTED"
        if profile.cost_class > requirement.maximum_cost:
            return "COST_POLICY_EXCEEDED"
        if profile.locality is ModelLocality.REMOTE and (requirement.local_only or not requirement.remote_allowed):
            return "REMOTE_POLICY_DENIED"
        return None
