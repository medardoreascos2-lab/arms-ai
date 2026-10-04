"""Local-first model access policy independent from any provider."""

from dataclasses import dataclass
from enum import Enum


class ModelAccessPolicy(str, Enum):
    LOCAL_FIRST = "LOCAL_FIRST"
    REMOTE_ALLOWED = "REMOTE_ALLOWED"
    REMOTE_REQUIRED = "REMOTE_REQUIRED"
    LOCAL_ONLY = "LOCAL_ONLY"


class PrivacyClass(str, Enum):
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    SENSITIVE = "SENSITIVE"
    RESTRICTED = "RESTRICTED"


@dataclass(frozen=True)
class ModelAccessDecision:
    policy: ModelAccessPolicy
    privacy_class: PrivacyClass
    prefer_local: bool
    local_only: bool
    remote_allowed: bool
    remote_required: bool
    external_call_authorized: bool = False

    def __post_init__(self) -> None:
        if self.external_call_authorized:
            raise ValueError("Phase 7 model policy cannot authorize external calls")


def default_model_policy(privacy_class: PrivacyClass) -> ModelAccessPolicy:
    if privacy_class is PrivacyClass.RESTRICTED:
        return ModelAccessPolicy.LOCAL_ONLY
    if privacy_class is PrivacyClass.SENSITIVE:
        return ModelAccessPolicy.LOCAL_FIRST
    if privacy_class is PrivacyClass.INTERNAL:
        return ModelAccessPolicy.LOCAL_FIRST
    return ModelAccessPolicy.REMOTE_ALLOWED


def evaluate_model_access(
    privacy_class: PrivacyClass,
    policy: ModelAccessPolicy | None = None,
) -> ModelAccessDecision:
    selected = policy or default_model_policy(privacy_class)
    if privacy_class is PrivacyClass.RESTRICTED and selected is not ModelAccessPolicy.LOCAL_ONLY:
        raise ValueError("restricted data requires LOCAL_ONLY")
    return ModelAccessDecision(
        policy=selected,
        privacy_class=privacy_class,
        prefer_local=selected in {ModelAccessPolicy.LOCAL_FIRST, ModelAccessPolicy.LOCAL_ONLY},
        local_only=selected is ModelAccessPolicy.LOCAL_ONLY,
        remote_allowed=selected in {ModelAccessPolicy.REMOTE_ALLOWED, ModelAccessPolicy.REMOTE_REQUIRED},
        remote_required=selected is ModelAccessPolicy.REMOTE_REQUIRED,
    )
