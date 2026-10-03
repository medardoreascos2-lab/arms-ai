"""R60A local application rollback rehearsal tests."""

import pytest

from backend.phase5 import (
    AppRollbackStatus,
    StagingAppRollbackRehearsal,
    StagingReleaseArtifact,
    StagingRuntimeSnapshot,
)


VERSION_N = StagingReleaseArtifact(
    version="phase5.60.0",
    minimum_schema_version=1,
    maximum_schema_version=2,
    feature_flags=("api_reads", "metrics_export"),
    compatible_worker_protocols=("worker.v1", "worker.v2"),
)
VERSION_N_PLUS_1 = StagingRuntimeSnapshot(
    application_version="phase5.60.1",
    schema_version=2,
    feature_flags=("api_reads", "metrics_export", "research_queue"),
    worker_protocols=("worker.v2",),
    dependencies_healthy=True,
)


def test_compatible_n_plus_1_to_n_rollback_preserves_schema_and_restores_flags():
    report = StagingAppRollbackRehearsal().rehearse(VERSION_N_PLUS_1, VERSION_N)

    assert report.status is AppRollbackStatus.REHEARSED_HEALTHY
    assert report.application_rollback_completed is True
    assert report.before.application_version == "phase5.60.1"
    assert report.after.application_version == "phase5.60.0"
    assert report.after.schema_version == report.before.schema_version == 2
    assert report.after.feature_flags == VERSION_N.feature_flags
    assert report.after.worker_protocols == ("worker.v2",)
    assert report.health.healthy is True
    assert report.health.ready is True
    assert report.health.blocking_reasons == ()
    assert report.reverse_database_migration_attempted is False
    assert report.database_restore_attempted is False
    assert report.database_restore_escalation_required is False
    assert report.external_deployment_authorized is False
    assert report.execution_authorized is False
    assert report.production_mutation_authorized is False
    assert report.live_trading_authorized is False


def test_schema_incompatibility_blocks_app_switch_without_reverse_migration():
    current = StagingRuntimeSnapshot(
        application_version="phase5.60.1",
        schema_version=3,
        feature_flags=VERSION_N_PLUS_1.feature_flags,
        worker_protocols=("worker.v2",),
        dependencies_healthy=True,
    )

    report = StagingAppRollbackRehearsal().rehearse(current, VERSION_N)

    assert report.status is AppRollbackStatus.BLOCKED_SCHEMA
    assert report.application_rollback_completed is False
    assert report.after == current
    assert report.health.blocking_reasons == ("SCHEMA_INCOMPATIBLE",)
    assert report.database_restore_escalation_required is True
    assert report.reverse_database_migration_attempted is False
    assert report.database_restore_attempted is False


def test_worker_incompatibility_blocks_switch_and_preserves_runtime_state():
    current = StagingRuntimeSnapshot(
        application_version="phase5.60.1",
        schema_version=2,
        feature_flags=VERSION_N_PLUS_1.feature_flags,
        worker_protocols=("worker.v3",),
        dependencies_healthy=True,
    )

    report = StagingAppRollbackRehearsal().rehearse(current, VERSION_N)

    assert report.status is AppRollbackStatus.BLOCKED_WORKER
    assert report.application_rollback_completed is False
    assert report.after == current
    assert report.health.healthy is False
    assert report.health.ready is False
    assert report.health.blocking_reasons == ("WORKER_PROTOCOL_INCOMPATIBLE",)
    assert report.database_restore_escalation_required is False


def test_unhealthy_dependency_is_reported_truthfully_after_compatible_switch():
    current = StagingRuntimeSnapshot(
        application_version="phase5.60.1",
        schema_version=2,
        feature_flags=VERSION_N_PLUS_1.feature_flags,
        worker_protocols=("worker.v2",),
        dependencies_healthy=False,
    )

    report = StagingAppRollbackRehearsal().rehearse(current, VERSION_N)

    assert report.status is AppRollbackStatus.REHEARSED_HEALTH_BLOCKED
    assert report.application_rollback_completed is True
    assert report.after.application_version == VERSION_N.version
    assert report.health.healthy is False
    assert report.health.ready is False
    assert report.health.blocking_reasons == ("DEPENDENCY_UNHEALTHY",)
    assert report.execution_authorized is False
    assert report.production_mutation_authorized is False


@pytest.mark.parametrize(
    "flag",
    ["live_trading", "broker_execution", "production_mutation", "disable_risk_controls"],
)
def test_candidate_artifact_rejects_flags_that_could_expand_authority(flag):
    with pytest.raises(ValueError, match="unsafe authority"):
        StagingReleaseArtifact(
            version="phase5.unsafe",
            minimum_schema_version=1,
            maximum_schema_version=2,
            feature_flags=(flag,),
            compatible_worker_protocols=("worker.v2",),
        )
