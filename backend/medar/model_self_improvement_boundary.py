"""Explicit Phase 8 boundary against autonomous model weight training."""

from dataclasses import dataclass
from enum import Enum


class ModelImprovementAction(str, Enum):
    COLLECT_EVALUATION_CANDIDATE = "COLLECT_EVALUATION_CANDIDATE"
    FINE_TUNE = "FINE_TUNE"
    RETRAIN = "RETRAIN"
    UPDATE_WEIGHTS = "UPDATE_WEIGHTS"


class ModelImprovementDisposition(str, Enum):
    CANDIDATE_COLLECTION_ALLOWED = "CANDIDATE_COLLECTION_ALLOWED"
    REQUIRES_SEPARATE_PHASE = "REQUIRES_SEPARATE_PHASE"


@dataclass(frozen=True)
class ModelImprovementBoundaryDecision:
    action: ModelImprovementAction
    disposition: ModelImprovementDisposition
    reason_codes: tuple[str, ...]
    training_authority: bool = False
    weight_mutation_performed: bool = False
    external_job_started: bool = False

    def __post_init__(self) -> None:
        if self.training_authority or self.weight_mutation_performed or self.external_job_started:
            raise ValueError("Phase 8 cannot authorize or perform model training")


def evaluate_model_improvement_action(
    action: ModelImprovementAction,
) -> ModelImprovementBoundaryDecision:
    if not isinstance(action, ModelImprovementAction):
        raise TypeError("model improvement action must be typed")
    if action is ModelImprovementAction.COLLECT_EVALUATION_CANDIDATE:
        return ModelImprovementBoundaryDecision(
            action, ModelImprovementDisposition.CANDIDATE_COLLECTION_ALLOWED,
            ("EVALUATION_METADATA_ONLY", "NO_WEIGHT_MUTATION"),
        )
    return ModelImprovementBoundaryDecision(
        action, ModelImprovementDisposition.REQUIRES_SEPARATE_PHASE,
        ("AUTONOMOUS_TRAINING_PROHIBITED", "SEPARATE_AUTHORIZATION_REQUIRED"),
    )
