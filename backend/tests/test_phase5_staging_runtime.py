"""R62A full isolated local staging composition tests."""

from dataclasses import replace
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from backend.phase3 import (
    AccountIdentity,
    Phase3DurableStateStore,
    Phase3ReadOnlyRuntime,
    ReadAuthorizationBoundary,
)
from backend.phase4 import (
    OperationalAlertPolicy,
    RequestReplayProtector,
    WorkerState,
    compose_phase4_staging_runtime,
)
from backend.phase5 import (
    REQUIRED_PHASE5_STAGING_COMPONENTS,
    EncryptedRestoreEscalation,
    EphemeralStagingBackupKey,
    LocalEphemeralBackupCipher,
    Phase5LocalStagingDependencies,
    Phase5StagingCompositionError,
    compose_phase5_local_staging_runtime,
)
from backend.prop_firms import canonical_profile_registry
from backend.tests.test_phase4_staging_runtime import _dependencies


def _composition(tmp_path, *, database_outside_root=False):
    phase4_dependencies, counters = _dependencies(tmp_path)
    phase4_dependencies.application_runtime.store.close()
    runtime_root = phase4_dependencies.config.runtime_root
    runtime_root.mkdir(parents=True)
    database_path = (
        tmp_path / "outside.sqlite3"
        if database_outside_root
        else runtime_root / "phase5.sqlite3"
    )
    store = Phase3DurableStateStore.create(database_path)
    application_runtime = Phase3ReadOnlyRuntime(
        store,
        authorization=ReadAuthorizationBoundary(frozenset({
            AccountIdentity("tenant-a", "account-1"),
        })),
        registry=canonical_profile_registry(),
    )
    phase4_dependencies = replace(
        phase4_dependencies,
        application_runtime=application_runtime,
    )
    phase4 = compose_phase4_staging_runtime(phase4_dependencies)
    key = EphemeralStagingBackupKey.generate(local_test_enabled=True)
    cipher = LocalEphemeralBackupCipher(key, local_test_enabled=True)
    dependencies = Phase5LocalStagingDependencies(
        runtime_root=runtime_root,
        api_runtime=phase4,
        local_database=store,
        replay_protector=RequestReplayProtector(),
        alert_policy=OperationalAlertPolicy(),
        backup_cipher=cipher,
        restore_escalation=EncryptedRestoreEscalation(),
    )
    return dependencies, counters, key


def test_composes_every_required_service_without_startup_or_external_authority(tmp_path):
    dependencies, counters, key = _composition(tmp_path)
    try:
        runtime = compose_phase5_local_staging_runtime(dependencies)

        assert runtime.composed is True
        assert runtime.started is False
        assert runtime.staging_status == "HOLD"
        assert runtime.components == REQUIRED_PHASE5_STAGING_COMPONENTS
        assert {item.value for item in runtime.components} == {
            "API",
            "DATABASE_ABSTRACTION",
            "AUTH",
            "SECRETS",
            "WORKERS",
            "SCHEDULER",
            "METRICS",
            "ALERTS",
            "BACKUPS",
            "RESEARCH_ENGINE",
        }
        assert all(
            getattr(runtime, attribute) is False
            for attribute in (
                "external_traffic_authorized",
                "external_delivery_authorized",
                "execution_authorized",
                "broker_authorized",
                "paper_trading_authorized",
                "live_trading_authorized",
                "production_mutation_authorized",
                "deployment_authorized",
            )
        )
        assert counters.calls == 0
        assert dependencies.api_runtime.dependencies.worker_supervisor.status().state is (
            WorkerState.STOPPED
        )
        assert dependencies.api_runtime.dependencies.research_queue.list() == ()
    finally:
        dependencies.local_database.close()
        key.close()


def test_composed_api_is_authenticated_and_read_only(tmp_path):
    dependencies, _, key = _composition(tmp_path)
    try:
        runtime = compose_phase5_local_staging_runtime(dependencies)
        with TestClient(runtime.api) as client:
            assert client.get("/api/phase3/status").status_code == 200
            assert client.get("/api/phase3/research/challengers").status_code == 200
            assert client.post("/api/phase3/status", json={}).status_code == 405
    finally:
        dependencies.local_database.close()
        key.close()


def test_database_outside_runtime_root_fails_before_startup(tmp_path):
    dependencies, counters, key = _composition(
        tmp_path,
        database_outside_root=True,
    )
    try:
        with pytest.raises(Phase5StagingCompositionError, match="runtime_root"):
            compose_phase5_local_staging_runtime(dependencies)

        assert counters.calls == 0
        assert dependencies.api_runtime.dependencies.worker_supervisor.status().state is (
            WorkerState.STOPPED
        )
    finally:
        dependencies.local_database.close()
        key.close()


def test_authorizing_component_fails_closed(tmp_path):
    dependencies, counters, key = _composition(tmp_path)
    dependencies.alert_policy.execution_authorized = True
    try:
        with pytest.raises(
            Phase5StagingCompositionError,
            match="execution_authorized",
        ):
            compose_phase5_local_staging_runtime(dependencies)
        assert counters.calls == 0
    finally:
        dependencies.local_database.close()
        key.close()


def test_phase5_composition_source_contains_no_order_or_broker_integration():
    import backend.phase5.staging_runtime as module

    source = Path(module.__file__).read_text(encoding="utf-8")
    assert "EnterLong" not in source
    assert "EnterShort" not in source
    assert "SubmitOrder" not in source
    assert "broker_connector" not in source
