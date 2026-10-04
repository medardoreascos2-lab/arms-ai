"""R119D evaluation candidates are allowed while weight training is denied."""

from backend.medar.model_self_improvement_boundary import (
    ModelImprovementAction, ModelImprovementDisposition,
    evaluate_model_improvement_action,
)


def test_evaluation_candidate_collection_is_metadata_only():
    decision = evaluate_model_improvement_action(
        ModelImprovementAction.COLLECT_EVALUATION_CANDIDATE,
    )
    assert decision.disposition is ModelImprovementDisposition.CANDIDATE_COLLECTION_ALLOWED
    assert not decision.training_authority
    assert not decision.weight_mutation_performed
    assert not decision.external_job_started


def test_fine_tune_retrain_and_weight_updates_require_separate_phase():
    denied = (
        ModelImprovementAction.FINE_TUNE,
        ModelImprovementAction.RETRAIN,
        ModelImprovementAction.UPDATE_WEIGHTS,
    )
    for action in denied:
        decision = evaluate_model_improvement_action(action)
        assert decision.disposition is ModelImprovementDisposition.REQUIRES_SEPARATE_PHASE
        assert "AUTONOMOUS_TRAINING_PROHIBITED" in decision.reason_codes
        assert not decision.training_authority
        assert not decision.weight_mutation_performed
        assert not decision.external_job_started
