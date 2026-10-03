"""R44D synthetic disaster recovery sequence drills."""

from pathlib import Path

import pytest

from backend.phase4.disaster_recovery import (
    RECOVERY_SEQUENCES,
    DisasterScenario,
    RecoveryAction,
    RecoveryDrillStatus,
    SyntheticDisasterRecoveryDrill,
    SyntheticRecoveryIncident,
    render_synthetic_recovery_runbook,
)


@pytest.mark.parametrize("scenario", tuple(DisasterScenario))
def test_each_synthetic_disaster_accepts_only_its_documented_sequence(scenario):
    incident = SyntheticRecoveryIncident.for_scenario(scenario)
    result = SyntheticDisasterRecoveryDrill.evaluate(
        incident,
        RECOVERY_SEQUENCES[scenario],
    )
    assert result.status is RecoveryDrillStatus.PASSED
    assert result.sequence_verified is True
    assert result.first_mismatch_index is None
    assert result.operational_recovery_verified is False
    assert result.operator_release_granted is False
    assert result.execution_authorized is False


@pytest.mark.parametrize("scenario", tuple(DisasterScenario))
def test_missing_reordered_or_extra_action_fails_drill(scenario):
    expected = RECOVERY_SEQUENCES[scenario]
    incident = SyntheticRecoveryIncident.for_scenario(scenario)
    variants = (
        expected[:-1],
        tuple(reversed(expected)),
        expected + (RecoveryAction.ASSERT_SYNTHETIC_SCOPE,),
    )
    for observed in variants:
        result = SyntheticDisasterRecoveryDrill.evaluate(incident, observed)
        assert result.status is RecoveryDrillStatus.FAILED
        assert result.sequence_verified is False
        assert result.first_mismatch_index is not None
        assert result.operational_recovery_verified is False


def test_incident_rejects_multiple_or_mismatched_failures():
    with pytest.raises(ValueError, match="exactly"):
        SyntheticRecoveryIncident(
            DisasterScenario.DATABASE_CORRUPTION,
            False,
            False,
            True,
            True,
        )
    with pytest.raises(ValueError, match="exactly"):
        SyntheticRecoveryIncident(
            DisasterScenario.MISSING_WORKER,
            False,
            True,
            True,
            True,
        )


def test_every_sequence_blocks_execution_and_requires_operator_release():
    for sequence in RECOVERY_SEQUENCES.values():
        assert sequence[:3] == (
            RecoveryAction.ASSERT_SYNTHETIC_SCOPE,
            RecoveryAction.DECLARE_RECOVERY_REQUIRED,
            RecoveryAction.BLOCK_EXECUTION_AND_MUTATIONS,
        )
        assert sequence[-1] is RecoveryAction.REQUIRE_OPERATOR_RELEASE


def test_documented_runbook_exactly_matches_executable_sequence_contract():
    path = Path(__file__).parents[1] / "phase4" / "DISASTER_RECOVERY.md"
    assert path.read_text(encoding="utf-8") == render_synthetic_recovery_runbook()


def test_drill_has_no_recovery_or_execution_authority():
    drill = SyntheticDisasterRecoveryDrill()
    assert drill.operational_recovery_verified is False
    assert drill.production_mutation_authorized is False
    assert drill.execution_authorized is False
