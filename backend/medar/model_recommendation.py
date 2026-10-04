"""Advisory model recommendations from scoped synthetic performance evidence."""

from dataclasses import dataclass
from enum import Enum

from backend.medar.model_performance import ModelPerformanceSummary
from backend.medar.model_profiles import CostClass, ModelCapabilityProfile, ModelLocality


class ModelPrivacyClass(str, Enum):
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    SENSITIVE = "SENSITIVE"


@dataclass(frozen=True)
class ModelRecommendationCandidate:
    provider_id: str
    model_id: str
    attempts: int
    success_rate: float
    structured_valid_rate: float
    average_quality_score: float
    average_latency_ms: float
    failure_rate: float
    locality: ModelLocality
    cost_class: CostClass


@dataclass(frozen=True)
class ModelRecommendation:
    tenant_id: str
    owner_id: str
    task_type: str
    privacy_class: ModelPrivacyClass
    recommended: ModelRecommendationCandidate | None
    ranked_candidates: tuple[ModelRecommendationCandidate, ...]
    review_candidates: tuple[tuple[str, str], ...]
    reason_codes: tuple[str, ...]
    routing_authority: bool = False
    provider_authority: bool = False
    external_call_authority: bool = False
    paid_api_authority: bool = False

    def __post_init__(self) -> None:
        if any((
            self.routing_authority, self.provider_authority,
            self.external_call_authority, self.paid_api_authority,
        )):
            raise ValueError("model recommendation cannot authorize routing, providers, or cost")


def recommend_models(
    summaries: tuple[ModelPerformanceSummary, ...],
    profiles: tuple[ModelCapabilityProfile, ...],
    *,
    tenant_id: str,
    owner_id: str,
    task_type: str,
    privacy_class: ModelPrivacyClass,
    minimum_attempts: int = 2,
) -> ModelRecommendation:
    if not isinstance(summaries, tuple) or any(not isinstance(item, ModelPerformanceSummary) for item in summaries):
        raise TypeError("typed model performance summaries are required")
    if not isinstance(profiles, tuple) or any(not isinstance(item, ModelCapabilityProfile) for item in profiles):
        raise TypeError("typed model profiles are required")
    if not isinstance(privacy_class, ModelPrivacyClass):
        raise TypeError("model privacy class must be typed")
    if isinstance(minimum_attempts, bool) or not isinstance(minimum_attempts, int) or not 1 <= minimum_attempts <= 1000:
        raise ValueError("minimum attempts must be from 1 to 1000")
    for name, value in (("tenant_id", tenant_id), ("owner_id", owner_id), ("task_type", task_type)):
        if not isinstance(value, str) or not value.strip() or len(value) > 240:
            raise ValueError(f"{name} must be bounded non-empty text")
    if any(
        item.tenant_id != tenant_id or item.owner_id != owner_id
        or item.task_type != task_type
        for item in summaries
    ):
        raise PermissionError("model recommendation evidence scope mismatch")
    if len({(item.provider_id, item.model_id) for item in summaries}) != len(summaries):
        raise ValueError("model performance summaries must be unique by provider and model")
    profile_by_id = {profile.model_id: profile for profile in profiles}
    if len(profile_by_id) != len(profiles):
        raise ValueError("model recommendation profiles must have unique model IDs")

    eligible: list[ModelRecommendationCandidate] = []
    review: list[tuple[str, str]] = []
    for summary in summaries:
        profile = profile_by_id.get(summary.model_id)
        if profile is None or not profile.available or summary.attempts < minimum_attempts:
            continue
        if summary.observed_cost_classes not in ((), (CostClass.FREE,)):
            review.append((summary.model_id, "PAID_EVIDENCE_REQUIRES_EXPLICIT_POLICY"))
            continue
        if profile.locality is ModelLocality.REMOTE:
            review.append((summary.model_id, "REMOTE_REQUIRES_EXPLICIT_POLICY"))
            continue
        if profile.cost_class is not CostClass.FREE:
            review.append((summary.model_id, "PAID_REQUIRES_EXPLICIT_POLICY"))
            continue
        if privacy_class is ModelPrivacyClass.SENSITIVE and profile.locality is not ModelLocality.LOCAL:
            review.append((summary.model_id, "SENSITIVE_DATA_LOCAL_ONLY"))
            continue
        successes = summary.successes / summary.attempts
        failures = sum(count for _kind, count in summary.failure_counts) / summary.attempts
        eligible.append(ModelRecommendationCandidate(
            summary.provider_id, summary.model_id, summary.attempts, successes,
            summary.structured_valid_rate, summary.average_quality_score,
            summary.average_latency_ms, failures, profile.locality, profile.cost_class,
        ))
    ranked = tuple(sorted(
        eligible,
        key=lambda item: (
            -item.structured_valid_rate, -item.average_quality_score,
            -item.success_rate, item.failure_rate, item.average_latency_ms,
            -item.attempts, item.model_id,
        ),
    ))
    if not ranked:
        reasons = ("NO_ELIGIBLE_LOCAL_FREE_EVIDENCE",)
    else:
        reasons = (
            "OBSERVED_STRUCTURED_VALIDITY", "OBSERVED_QUALITY",
            "OBSERVED_SUCCESS_FAILURE", "OBSERVED_LATENCY",
        )
    return ModelRecommendation(
        tenant_id, owner_id, task_type, privacy_class,
        ranked[0] if ranked else None, ranked,
        tuple(sorted(review)), reasons,
    )
