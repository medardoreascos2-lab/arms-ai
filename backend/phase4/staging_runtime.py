"""Validated Phase 4 staging composition with no startup or execution authority."""

from __future__ import annotations

from dataclasses import dataclass, field

from fastapi import APIRouter

from backend.phase3.research_api import ResearchApiSources, create_phase3_research_router
from backend.phase3.runtime import Phase3ReadOnlyRuntime
from backend.phase3.status_api import Phase3StatusSources, create_phase3_status_router
from backend.research.research_scheduler import ResearchJobQueue

from .database_abstraction import DatabaseAdapterRegistry
from .deployment_config import (
    DeploymentEnvironment,
    Phase4DeploymentConfig,
    Phase4Feature,
)
from .local_backup import LocalBackupRunner
from .operational_health import OperationalHealthModel
from .operational_metrics import MetricsExporter
from .restore_validation import BackupRestoreValidator
from .scheduler_supervision import SchedulerSupervisor
from .secret_providers import SecretProvider
from .transport_authorization import Phase4TransportAuthorizationBoundary
from .worker_supervisor import WorkerSupervisor


REQUIRED_STAGING_FEATURES = frozenset(Phase4Feature)


class Phase4StagingCompositionError(RuntimeError):
    pass


@dataclass(frozen=True)
class Phase4StagingDependencies:
    config: Phase4DeploymentConfig
    database_registry: DatabaseAdapterRegistry
    secret_provider: SecretProvider
    application_runtime: Phase3ReadOnlyRuntime
    authorization: Phase4TransportAuthorizationBoundary
    worker_supervisor: WorkerSupervisor
    scheduler_supervisor: SchedulerSupervisor
    metrics_exporter: MetricsExporter
    health_model: OperationalHealthModel
    backup_runner: LocalBackupRunner
    restore_validator: BackupRestoreValidator
    research_queue: ResearchJobQueue
    status_sources: Phase3StatusSources
    research_sources: ResearchApiSources

    def __post_init__(self) -> None:
        expected = (
            (self.config, Phase4DeploymentConfig, "config"),
            (self.database_registry, DatabaseAdapterRegistry, "database_registry"),
            (self.secret_provider, SecretProvider, "secret_provider"),
            (self.application_runtime, Phase3ReadOnlyRuntime, "application_runtime"),
            (
                self.authorization,
                Phase4TransportAuthorizationBoundary,
                "authorization",
            ),
            (self.worker_supervisor, WorkerSupervisor, "worker_supervisor"),
            (self.scheduler_supervisor, SchedulerSupervisor, "scheduler_supervisor"),
            (self.metrics_exporter, MetricsExporter, "metrics_exporter"),
            (self.health_model, OperationalHealthModel, "health_model"),
            (self.backup_runner, LocalBackupRunner, "backup_runner"),
            (self.restore_validator, BackupRestoreValidator, "restore_validator"),
            (self.research_queue, ResearchJobQueue, "research_queue"),
            (self.status_sources, Phase3StatusSources, "status_sources"),
            (self.research_sources, ResearchApiSources, "research_sources"),
        )
        for value, kind, name in expected:
            if not isinstance(value, kind):
                raise ValueError(f"{name} has an invalid type")


@dataclass(frozen=True)
class Phase4StagingRuntime:
    dependencies: Phase4StagingDependencies
    status_router: APIRouter
    research_router: APIRouter
    component_names: tuple[str, ...]
    started: bool = field(default=False, init=False)
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)
    external_delivery_authorized: bool = field(default=False, init=False)
    live_trading_authorized: bool = field(default=False, init=False)
    deployment_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.dependencies, Phase4StagingDependencies):
            raise ValueError("dependencies must be Phase4StagingDependencies")
        if not isinstance(self.status_router, APIRouter):
            raise ValueError("status_router must be an APIRouter")
        if not isinstance(self.research_router, APIRouter):
            raise ValueError("research_router must be an APIRouter")
        if (
            not isinstance(self.component_names, tuple)
            or self.component_names != tuple(sorted(set(self.component_names)))
        ):
            raise ValueError("component_names must be sorted and unique")


def _require_no_authority(name: str, component: object) -> None:
    for attribute in ("execution_authorized", "production_mutation_authorized"):
        if getattr(component, attribute, False) is not False:
            raise Phase4StagingCompositionError(
                f"{name} cannot carry {attribute}"
            )


def compose_phase4_staging_runtime(
    dependencies: Phase4StagingDependencies,
) -> Phase4StagingRuntime:
    """Validate and compose inert staging services without starting any of them."""

    if not isinstance(dependencies, Phase4StagingDependencies):
        raise ValueError("dependencies must be Phase4StagingDependencies")
    config = dependencies.config
    if config.environment is not DeploymentEnvironment.STAGING:
        raise Phase4StagingCompositionError("composition requires STAGING environment")
    missing_features = REQUIRED_STAGING_FEATURES - config.enabled_features
    if missing_features:
        names = ",".join(sorted(item.value for item in missing_features))
        raise Phase4StagingCompositionError(
            f"staging configuration is missing required features: {names}"
        )
    if config.database.backend not in dependencies.database_registry.backends:
        raise Phase4StagingCompositionError(
            "configured database backend is not registered"
        )
    if dependencies.secret_provider.provider_id != config.secret_provider.value:
        raise Phase4StagingCompositionError(
            "secret provider does not match staging configuration"
        )
    if dependencies.worker_supervisor.config != config.worker:
        raise Phase4StagingCompositionError(
            "worker supervisor configuration does not match staging configuration"
        )

    components = {
        "application_runtime": dependencies.application_runtime,
        "authorization": dependencies.authorization,
        "backup_runner": dependencies.backup_runner,
        "database_registry": dependencies.database_registry,
        "health_model": dependencies.health_model,
        "metrics_exporter": dependencies.metrics_exporter,
        "research_queue": dependencies.research_queue,
        "restore_validator": dependencies.restore_validator,
        "scheduler_supervisor": dependencies.scheduler_supervisor,
        "secret_provider": dependencies.secret_provider,
        "worker_supervisor": dependencies.worker_supervisor,
    }
    for name, component in components.items():
        _require_no_authority(name, component)
    if dependencies.metrics_exporter.external_export_authorized is not False:
        raise Phase4StagingCompositionError(
            "metrics exporter cannot carry external export authority"
        )
    if dependencies.worker_supervisor.external_delivery_authorized is not False:
        raise Phase4StagingCompositionError(
            "worker supervisor cannot carry external delivery authority"
        )
    if dependencies.scheduler_supervisor.external_delivery_authorized is not False:
        raise Phase4StagingCompositionError(
            "scheduler supervisor cannot carry external delivery authority"
        )
    if dependencies.backup_runner.cloud_upload_authorized is not False:
        raise Phase4StagingCompositionError(
            "backup runner cannot carry cloud upload authority"
        )
    if dependencies.restore_validator.live_store_overwrite_authorized is not False:
        raise Phase4StagingCompositionError(
            "restore validator cannot overwrite a live store"
        )

    return Phase4StagingRuntime(
        dependencies=dependencies,
        status_router=create_phase3_status_router(dependencies.status_sources),
        research_router=create_phase3_research_router(dependencies.research_sources),
        component_names=tuple(sorted(components)),
    )
