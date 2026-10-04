"""Ready-only local runtime routing with validated fallback.

No provider selection or model response grants tool, broker, PAPER, or LIVE authority.
"""

from dataclasses import dataclass, replace

from backend.medar.local_model_provider import LocalModelProvider, ModelReadiness
from backend.medar.model_output_validation import ValidatedModelOutput, validate_model_output
from backend.medar.model_profiles import ModelCapabilityProfile, ModelLocality, ModelProfileRegistry
from backend.medar.model_provider import ModelInvocation, ModelKind
from backend.medar.model_router import ModelRouter, ModelRoutingRequirement


@dataclass(frozen=True)
class RuntimeModelRoute:
    candidates: tuple[ModelCapabilityProfile, ...]
    rejection_reasons: tuple[str, ...]
    external_call_authorized: bool = False

    def __post_init__(self) -> None:
        if self.external_call_authorized:
            raise ValueError("runtime model routing cannot authorize external calls")


@dataclass(frozen=True)
class RuntimeModelResponse:
    output: ValidatedModelOutput
    attempted_models: tuple[str, ...]
    external_call_performed: bool = False

    def __post_init__(self) -> None:
        if self.external_call_performed:
            raise ValueError("runtime model response cannot report external calls")


class RuntimeModelRouter:
    def __init__(self, profiles: ModelProfileRegistry, providers: tuple[LocalModelProvider, ...]):
        self._profiles = profiles
        entries: dict[str, LocalModelProvider] = {}
        for provider in providers:
            descriptor = provider.descriptor
            if not provider.is_local or descriptor.model_id in entries or descriptor.provider_id != provider.provider_id:
                raise ValueError("invalid or duplicate local provider")
            entries[descriptor.model_id] = provider
        self._providers = entries

    def route(self, requirement: ModelRoutingRequirement) -> RuntimeModelRoute:
        ready: list[ModelCapabilityProfile] = []
        rejected: list[str] = []
        for profile in self._profiles.profiles:
            provider = self._providers.get(profile.model_id)
            if profile.locality is not ModelLocality.LOCAL or profile.kind is ModelKind.REMOTE_LLM:
                rejected.append(f"{profile.model_id}:REMOTE_DISABLED")
                continue
            if provider is None:
                rejected.append(f"{profile.model_id}:PROVIDER_MISSING")
                continue
            caps = provider.descriptor.capabilities
            if (
                profile.kind not in caps.supported_kinds
                or profile.context_window > caps.context_length
                or (profile.structured_output_support and not caps.structured_output)
                or (profile.tool_call_support and not caps.tool_support)
            ):
                rejected.append(f"{profile.model_id}:PROFILE_MISMATCH")
                continue
            try:
                provider_ready = provider.health().readiness is ModelReadiness.READY
            except Exception:
                provider_ready = False
            if not profile.available or not provider_ready:
                rejected.append(f"{profile.model_id}:NOT_READY")
                continue
            ready.append(replace(profile, available=True))
        candidates: list[ModelCapabilityProfile] = []
        while ready:
            selected = ModelRouter(ModelProfileRegistry(tuple(ready))).route(
                replace(requirement, local_only=True, remote_allowed=False)
            )
            if selected.selected is None:
                rejected.extend(selected.rejection_reasons)
                break
            candidates.append(selected.selected)
            ready = [item for item in ready if item.model_id != selected.selected.model_id]
        return RuntimeModelRoute(tuple(candidates), tuple(rejected))

    def invoke(self, requirement: ModelRoutingRequirement, invocation: ModelInvocation) -> RuntimeModelResponse:
        if invocation.model_kind is ModelKind.REMOTE_LLM:
            raise ValueError("remote invocation is disabled")
        effective = replace(
            requirement,
            required_kind=invocation.model_kind,
            structured_output_required=requirement.structured_output_required or invocation.structured_output_schema is not None,
        )
        route = self.route(effective)
        attempted: list[str] = []
        for profile in route.candidates:
            attempted.append(profile.model_id)
            candidate = ModelInvocation(
                invocation.invocation_id,
                profile.model_id,
                profile.kind,
                invocation.prompt,
                invocation.structured_output_schema,
            )
            try:
                result = self._providers[profile.model_id].invoke(candidate)
                validated = validate_model_output(candidate, result)
            except Exception:
                continue
            return RuntimeModelResponse(validated, tuple(attempted))
        raise RuntimeError("no ready local model returned valid output")
