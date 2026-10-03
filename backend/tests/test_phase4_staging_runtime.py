"""R48A tests for the inert Phase 4 staging composition."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from backend.entitlements import UserRole
from backend.phase3 import (
    Phase3DurableStateStore,
    Phase3ReadOnlyRuntime,
    ReadAuthorizationBoundary,
)
from backend.phase3.research_api import ResearchApiSources
from backend.phase3.status_api import Phase3StatusSources
from backend.phase4 import (
    BackupRestoreValidator,
    DatabaseAccessMode,
    DatabaseAdapterRegistry,
    DatabaseBackend,
    DatabaseTarget,
    DeploymentEnvironment,
    DisabledSecretProvider,
    EnvironmentSecretProvider,
    HealthEvaluationPolicy,
    InMemoryMetricsExporter,
    InMemorySchedulerLeaseStore,
    LocalBackupRunner,
    OperationalHealthModel,
    Phase4DeploymentConfig,
    Phase4Feature,
    Phase4StagingCompositionError,
    Phase4StagingDependencies,
    Phase4TransportAuthorizationBoundary,
    PostgresDatabaseAdapter,
    ReplayProtectionPolicy,
    RestoreDestinationMode,
    SchedulerSupervisor,
    SecretProviderMode,
    SecretReference,
    WorkerState,
    WorkerSupervisor,
    WorkerSupervisorConfig,
    compose_phase4_staging_runtime,
)
from backend.prop_firms import canonical_profile_registry
from backend.research.research_scheduler import ResearchJobQueue
from backend.tests.test_phase4_transport_authorization import user as transport_user


NOW = datetime(2026, 10, 4, 12, tzinfo=timezone.utc)


class CallCounter:
    def __init__(self):
        self.calls = 0

    def database(self, *_):
        self.calls += 1
        raise AssertionError("composition must not connect to PostgreSQL")

    def process(self, *_):
        self.calls += 1
        raise AssertionError("composition must not start a worker")


def _config(root, worker_config, features=frozenset(Phase4Feature)):
    reference = SecretReference("database/phase4/staging")
    return Phase4DeploymentConfig(
        environment=DeploymentEnvironment.STAGING,
        service_name="arms-phase4",
        runtime_root=root,
        backup_root=root / "backups",
        database=DatabaseTarget(
            DatabaseBackend.POSTGRESQL,
            "arms_phase4",
            DatabaseAccessMode.READ_WRITE,
            connection_reference=reference.reference_id,
        ),
        secret_provider=SecretProviderMode.ENVIRONMENT,
        database_secret_reference=reference,
        worker=worker_config,
        replay_protection=ReplayProtectionPolicy(),
        enabled_features=features,
        debug=False,
    )


def _status_sources():
    return Phase3StatusSources(*(
        (lambda name=name: {"component": name, "healthy": True})
        for name in Phase3StatusSources.__dataclass_fields__
    ))


def _research_sources():
    return ResearchApiSources(*(
        (lambda name=name: ({"kind": name},))
        for name in ResearchApiSources.__dataclass_fields__
    ))


def _dependencies(tmp_path, *, features=frozenset(Phase4Feature)):
    counters = CallCounter()
    worker_config = WorkerSupervisorConfig()
    config = _config(tmp_path / "runtime", worker_config, features)
    store = Phase3DurableStateStore.create(tmp_path / "phase3.sqlite3")
    application_runtime = Phase3ReadOnlyRuntime(
        store,
        authorization=ReadAuthorizationBoundary(frozenset()),
        registry=canonical_profile_registry(),
    )
    database_registry = DatabaseAdapterRegistry((
        PostgresDatabaseAdapter(counters.database),
    ))
    worker = WorkerSupervisor(
        worker_id="outbox_worker",
        process_factory=counters.process,
        clock=lambda: NOW,
        config=worker_config,
        token_factory=lambda: "staging-worker-token-0001",
    )
    scheduler = SchedulerSupervisor(
        scheduler_id="staging-scheduler",
        lease_store=InMemorySchedulerLeaseStore(
            token_factory=lambda: "staging-scheduler-token-0001"
        ),
        clock=lambda: NOW,
    )
    dependencies = Phase4StagingDependencies(
        config=config,
        database_registry=database_registry,
        secret_provider=EnvironmentSecretProvider(environment={}),
        application_runtime=application_runtime,
        authorization=Phase4TransportAuthorizationBoundary(frozenset()),
        worker_supervisor=worker,
        scheduler_supervisor=scheduler,
        metrics_exporter=InMemoryMetricsExporter(),
        health_model=OperationalHealthModel(HealthEvaluationPolicy(60)),
        backup_runner=LocalBackupRunner(
            config.backup_root,
            retention_policy="STAGING_7_DAYS",
            retention_period=timedelta(days=7),
            clock=lambda: NOW,
        ),
        restore_validator=BackupRestoreValidator(
            config.runtime_root / "isolated-restores",
            mode=RestoreDestinationMode.ISOLATED_TEST,
        ),
        research_queue=ResearchJobQueue(),
        status_sources=_status_sources(),
        research_sources=_research_sources(),
        principal_resolver=lambda request: transport_user(),
        clock=lambda: NOW,
    )
    return dependencies, counters


def test_composition_binds_every_service_without_startup_or_external_effects(tmp_path):
    dependencies, counters = _dependencies(tmp_path)
    try:
        runtime = compose_phase4_staging_runtime(dependencies)

        assert runtime.started is False
        assert runtime.execution_authorized is False
        assert runtime.production_mutation_authorized is False
        assert runtime.external_delivery_authorized is False
        assert runtime.live_trading_authorized is False
        assert runtime.deployment_authorized is False
        assert set(runtime.component_names) == {
            "application_runtime",
            "authorization",
            "backup_runner",
            "database_registry",
            "health_model",
            "metrics_exporter",
            "research_queue",
            "restore_validator",
            "scheduler_supervisor",
            "secret_provider",
            "worker_supervisor",
        }
        assert counters.calls == 0
        assert dependencies.worker_supervisor.status().state is WorkerState.STOPPED
        assert dependencies.research_queue.list() == ()
    finally:
        dependencies.application_runtime.store.close()


def test_composed_apis_are_read_only_and_return_detached_local_data(tmp_path):
    dependencies, _ = _dependencies(tmp_path)
    try:
        runtime = compose_phase4_staging_runtime(dependencies)
        app = FastAPI()
        app.include_router(runtime.status_router)
        app.include_router(runtime.research_router)
        client = TestClient(app)

        assert client.get("/api/phase3/status").status_code == 200
        research = client.get("/api/phase3/research/challengers")
        assert research.status_code == 200
        assert research.json()["read_only"] is True
        assert client.post("/api/phase3/status", json={}).status_code == 405
        assert client.post("/api/phase3/research/challengers", json={}).status_code == 405
    finally:
        dependencies.application_runtime.store.close()


def test_composed_apis_deny_missing_or_broken_authentication(tmp_path):
    dependencies, _ = _dependencies(tmp_path)
    try:
        for resolver in (lambda request: None, lambda request: 1 / 0):
            runtime = compose_phase4_staging_runtime(
                replace(dependencies, principal_resolver=resolver)
            )
            app = FastAPI()
            app.include_router(runtime.status_router)
            app.include_router(runtime.research_router)
            client = TestClient(app)
            assert client.get("/api/phase3/status").status_code == 401
            assert client.get("/api/phase3/research/challengers").status_code == 401
    finally:
        dependencies.application_runtime.store.close()


def test_composed_research_api_denies_authenticated_principal_without_permission(tmp_path):
    dependencies, _ = _dependencies(tmp_path)
    research_calls = []
    restricted = replace(
        dependencies,
        principal_resolver=lambda request: transport_user(role=UserRole.VIEWER),
        research_sources=ResearchApiSources(*(
            (lambda name=name: research_calls.append(name) or ())
            for name in ResearchApiSources.__dataclass_fields__
        )),
    )
    try:
        runtime = compose_phase4_staging_runtime(restricted)
        app = FastAPI()
        app.include_router(runtime.research_router)

        response = TestClient(app).get("/api/phase3/research/challengers")

        assert response.status_code == 403
        assert response.json() == {"detail": "AUTHORIZATION_DENIED"}
        assert research_calls == []
    finally:
        dependencies.application_runtime.store.close()


def test_missing_staging_feature_fails_closed_before_any_startup(tmp_path):
    dependencies, counters = _dependencies(
        tmp_path,
        features=frozenset(Phase4Feature) - {Phase4Feature.LOCAL_BACKUP},
    )
    try:
        with pytest.raises(Phase4StagingCompositionError, match="local_backup"):
            compose_phase4_staging_runtime(dependencies)
        assert counters.calls == 0
    finally:
        dependencies.application_runtime.store.close()


def test_non_staging_environment_and_unregistered_storage_fail_closed(tmp_path):
    dependencies, _ = _dependencies(tmp_path)
    try:
        development = replace(
            dependencies.config,
            environment=DeploymentEnvironment.DEVELOPMENT,
        )
        with pytest.raises(Phase4StagingCompositionError, match="STAGING"):
            compose_phase4_staging_runtime(
                replace(dependencies, config=development)
            )
        with pytest.raises(Phase4StagingCompositionError, match="not registered"):
            compose_phase4_staging_runtime(
                replace(dependencies, database_registry=DatabaseAdapterRegistry())
            )
    finally:
        dependencies.application_runtime.store.close()


def test_provider_mismatch_and_authorizing_component_are_rejected(tmp_path):
    dependencies, _ = _dependencies(tmp_path)
    try:
        with pytest.raises(Phase4StagingCompositionError, match="secret provider"):
            compose_phase4_staging_runtime(
                replace(dependencies, secret_provider=DisabledSecretProvider())
            )

        dependencies.worker_supervisor.execution_authorized = True
        with pytest.raises(Phase4StagingCompositionError, match="execution_authorized"):
            compose_phase4_staging_runtime(dependencies)
    finally:
        dependencies.application_runtime.store.close()


def test_composition_module_contains_no_broker_or_live_order_integration():
    import backend.phase4.staging_runtime as module

    source = Path(module.__file__).read_text(encoding="utf-8")
    assert "EnterLong" not in source
    assert "EnterShort" not in source
    assert "SubmitOrder" not in source
    assert "broker" not in source.lower()
