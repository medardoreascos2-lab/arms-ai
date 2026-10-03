"""Inert local Phase 5 staging composition with explicit zero authority."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from fastapi import FastAPI

from backend.phase3 import Phase3DurableStateStore
from backend.phase4 import (
    OperationalAlertPolicy,
    Phase4StagingRuntime,
    RequestReplayProtector,
)

from .encrypted_backup import StagingBackupCipher
from .restore_escalation import EncryptedRestoreEscalation


class Phase5StagingCompositionError(RuntimeError):
    pass


class Phase5StagingComponent(str, Enum):
    API = "API"
    DATABASE_ABSTRACTION = "DATABASE_ABSTRACTION"
    AUTH = "AUTH"
    SECRETS = "SECRETS"
    WORKERS = "WORKERS"
    SCHEDULER = "SCHEDULER"
    METRICS = "METRICS"
    ALERTS = "ALERTS"
    BACKUPS = "BACKUPS"
    RESEARCH_ENGINE = "RESEARCH_ENGINE"


REQUIRED_PHASE5_STAGING_COMPONENTS = tuple(Phase5StagingComponent)


@dataclass(frozen=True)
class Phase5LocalStagingDependencies:
    runtime_root: Path
    api_runtime: Phase4StagingRuntime
    local_database: Phase3DurableStateStore
    replay_protector: RequestReplayProtector
    alert_policy: OperationalAlertPolicy
    backup_cipher: StagingBackupCipher
    restore_escalation: EncryptedRestoreEscalation

    def __post_init__(self) -> None:
        expected = (
            (self.api_runtime, Phase4StagingRuntime, "api_runtime"),
            (self.local_database, Phase3DurableStateStore, "local_database"),
            (self.replay_protector, RequestReplayProtector, "replay_protector"),
            (self.alert_policy, OperationalAlertPolicy, "alert_policy"),
            (self.backup_cipher, StagingBackupCipher, "backup_cipher"),
            (
                self.restore_escalation,
                EncryptedRestoreEscalation,
                "restore_escalation",
            ),
        )
        for value, kind, name in expected:
            if not isinstance(value, kind):
                raise ValueError(f"{name} has an invalid type")
        if not isinstance(self.runtime_root, Path) or not self.runtime_root.is_absolute():
            raise ValueError("runtime_root must be an absolute Path")


@dataclass(frozen=True)
class Phase5LocalStagingRuntime:
    dependencies: Phase5LocalStagingDependencies
    api: FastAPI
    components: tuple[Phase5StagingComponent, ...]
    staging_status: str = field(default="HOLD", init=False)
    composed: bool = field(default=True, init=False)
    started: bool = field(default=False, init=False)
    external_traffic_authorized: bool = field(default=False, init=False)
    external_delivery_authorized: bool = field(default=False, init=False)
    execution_authorized: bool = field(default=False, init=False)
    broker_authorized: bool = field(default=False, init=False)
    paper_trading_authorized: bool = field(default=False, init=False)
    live_trading_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)
    deployment_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.dependencies, Phase5LocalStagingDependencies):
            raise ValueError("dependencies must be Phase5LocalStagingDependencies")
        if not isinstance(self.api, FastAPI):
            raise ValueError("api must be a FastAPI application")
        if self.components != REQUIRED_PHASE5_STAGING_COMPONENTS:
            raise ValueError("runtime must contain every Phase 5 staging component")


def _require_no_authority(name: str, component: object) -> None:
    for attribute in (
        "execution_authorized",
        "production_mutation_authorized",
        "external_delivery_authorized",
        "external_export_authorized",
        "external_storage_authorized",
        "cloud_upload_authorized",
        "live_store_overwrite_authorized",
        "live_trading_authorized",
        "deployment_authorized",
    ):
        if getattr(component, attribute, False) is not False:
            raise Phase5StagingCompositionError(
                f"{name} cannot carry {attribute}"
            )


def compose_phase5_local_staging_runtime(
    dependencies: Phase5LocalStagingDependencies,
) -> Phase5LocalStagingRuntime:
    """Compose local services without starting processes or contacting providers."""

    if not isinstance(dependencies, Phase5LocalStagingDependencies):
        raise ValueError("dependencies must be Phase5LocalStagingDependencies")
    root_input = dependencies.runtime_root
    if root_input.is_symlink():
        raise Phase5StagingCompositionError("runtime_root cannot be a symbolic link")
    try:
        root = root_input.resolve(strict=True)
        database = dependencies.local_database.path.resolve(strict=True)
        database.relative_to(root)
    except (OSError, ValueError):
        raise Phase5StagingCompositionError(
            "local database must remain inside the existing runtime_root"
        ) from None
    if not root.is_dir() or dependencies.local_database.path.is_symlink():
        raise Phase5StagingCompositionError(
            "runtime root and local database must be regular local resources"
        )
    if dependencies.local_database.read_only:
        raise Phase5StagingCompositionError(
            "local staging composition requires a writable isolated database"
        )

    phase4 = dependencies.api_runtime
    if phase4.started or phase4.dependencies.application_runtime.store is not (
        dependencies.local_database
    ):
        raise Phase5StagingCompositionError(
            "API runtime must use the same inert local staging database"
        )

    phase4_dependencies = phase4.dependencies
    components = {
        "api_runtime": phase4,
        "database": dependencies.local_database,
        "authorization": phase4_dependencies.authorization,
        "replay_protector": dependencies.replay_protector,
        "secret_provider": phase4_dependencies.secret_provider,
        "worker_supervisor": phase4_dependencies.worker_supervisor,
        "scheduler_supervisor": phase4_dependencies.scheduler_supervisor,
        "metrics_exporter": phase4_dependencies.metrics_exporter,
        "alert_policy": dependencies.alert_policy,
        "backup_runner": phase4_dependencies.backup_runner,
        "backup_cipher": dependencies.backup_cipher,
        "restore_validator": phase4_dependencies.restore_validator,
        "restore_escalation": dependencies.restore_escalation,
        "research_queue": phase4_dependencies.research_queue,
    }
    for name, component in components.items():
        _require_no_authority(name, component)
    if dependencies.backup_cipher.local_test_only is not True:
        raise Phase5StagingCompositionError(
            "local composition requires an explicitly local-test backup cipher"
        )

    api = FastAPI(title="ARMS AI Phase 5 isolated local staging")
    api.include_router(phase4.status_router)
    api.include_router(phase4.research_router)
    return Phase5LocalStagingRuntime(
        dependencies=dependencies,
        api=api,
        components=REQUIRED_PHASE5_STAGING_COMPONENTS,
    )
