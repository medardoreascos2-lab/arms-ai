"""R76C deterministic external staging provisioning gate tests."""

from pathlib import Path

import pytest

from backend.phase6.provisioning_gate import (
    ProvisioningGateStatus,
    collect_local_provisioning_evidence,
    evaluate_provisioning_gate,
    with_missing_evidence,
)


ROOT = Path(__file__).parents[2]


def _complete_evidence():
    return collect_local_provisioning_evidence(ROOT, prior_branches_unchanged=True)


def test_complete_local_evidence_is_ready_only_for_operator_provisioning():
    evidence = _complete_evidence()
    result = evaluate_provisioning_gate(evidence)

    assert all(vars(evidence).values())
    assert result.status is ProvisioningGateStatus.READY_FOR_OPERATOR_PROVISIONING
    assert result.missing_evidence == ()
    assert result.operator_action_required is True
    assert result.provisioning_authorized is False
    assert result.external_actions_performed is False


def test_gate_has_exactly_three_outcomes_and_never_production_or_live():
    values = {status.value for status in ProvisioningGateStatus}

    assert values == {"READY_FOR_OPERATOR_PROVISIONING", "HOLD", "BLOCKED"}
    assert "READY_FOR_PRODUCTION" not in values
    assert "LIVE_ALLOWED" not in values


@pytest.mark.parametrize(
    "missing",
    [
        "iac_validated",
        "security_review_green",
        "nq_mnq_semantics_green",
        "secret_strategy_present",
        "identity_strategy_present",
        "failure_rehearsal_green",
        "prior_branches_unchanged",
    ],
)
def test_missing_critical_evidence_is_blocked(missing):
    evidence = with_missing_evidence(_complete_evidence(), missing)
    result = evaluate_provisioning_gate(evidence)

    assert result.status is ProvisioningGateStatus.BLOCKED
    assert missing in result.missing_evidence
    assert result.provisioning_authorized is False
    assert result.live_authority is False
    assert result.production_deployment_authority is False


def test_missing_cost_model_holds_without_authorizing_external_action():
    evidence = with_missing_evidence(_complete_evidence(), "cost_model_present")
    result = evaluate_provisioning_gate(evidence)

    assert result.status is ProvisioningGateStatus.HOLD
    assert result.missing_evidence == ("cost_model_present",)
    assert result.provisioning_authorized is False
    assert result.external_actions_performed is False


def test_every_outcome_preserves_all_trading_and_production_authority_as_false():
    complete = _complete_evidence()
    results = (
        evaluate_provisioning_gate(complete),
        evaluate_provisioning_gate(with_missing_evidence(complete, "cost_model_present")),
        evaluate_provisioning_gate(with_missing_evidence(complete, "security_review_green")),
    )

    for result in results:
        assert result.broker_authority is False
        assert result.paper_authority is False
        assert result.live_authority is False
        assert result.production_deployment_authority is False
        assert result.provisioning_authorized is False
