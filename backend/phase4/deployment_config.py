"""Secret-free, environment-specific Phase 4 application configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import re
from types import MappingProxyType
from typing import Mapping

from .database_abstraction import DatabaseBackend, DatabaseTarget
from .request_replay import ReplayProtectionPolicy
from .secret_providers import SecretReference
from .worker_supervisor import WorkerSupervisorConfig


_SERVICE_NAME = re.compile(r"^[a-z][a-z0-9-]{0,62}$")


class DeploymentEnvironment(str, Enum):
    DEVELOPMENT = "development"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


class SecretProviderMode(str, Enum):
    DISABLED = "disabled"
    ENVIRONMENT = "environment"
    LOCAL_TEST_FILE = "local_test_file"


class Phase4Feature(str, Enum):
    API_READS = "api_reads"
    LOCAL_BACKUP = "local_backup"
    METRICS_EXPORT = "metrics_export"
    RESTORE_VALIDATION = "restore_validation"
    RETRY_OPERATIONS = "retry_operations"
    SCHEDULER_SUPERVISION = "scheduler_supervision"
    WORKER_SUPERVISION = "worker_supervision"


def _absolute(path: Path, name: str) -> Path:
    if not isinstance(path, Path) or not path.is_absolute():
        raise ValueError(f"{name} must be an absolute Path")
    return path.resolve(strict=False)


def _require_within(path: Path, root: Path, name: str) -> None:
    try:
        path.relative_to(root)
    except ValueError:
        raise ValueError(f"{name} must remain within runtime_root") from None


@dataclass(frozen=True)
class Phase4DeploymentConfig:
    environment: DeploymentEnvironment
    service_name: str
    runtime_root: Path
    backup_root: Path
    database: DatabaseTarget
    secret_provider: SecretProviderMode
    database_secret_reference: SecretReference | None
    worker: WorkerSupervisorConfig
    replay_protection: ReplayProtectionPolicy
    enabled_features: frozenset[Phase4Feature]
    debug: bool
    authentication_required: bool = field(default=True, init=False)
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)
    live_trading_enabled: bool = field(default=False, init=False)
    deployment_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.environment, DeploymentEnvironment):
            raise ValueError("environment must be a DeploymentEnvironment")
        if not isinstance(self.service_name, str) or _SERVICE_NAME.fullmatch(
            self.service_name
        ) is None:
            raise ValueError("service_name must be a lowercase service identifier")
        runtime_root = _absolute(self.runtime_root, "runtime_root")
        backup_root = _absolute(self.backup_root, "backup_root")
        _require_within(backup_root, runtime_root, "backup_root")
        object.__setattr__(self, "runtime_root", runtime_root)
        object.__setattr__(self, "backup_root", backup_root)

        if not isinstance(self.database, DatabaseTarget):
            raise ValueError("database must be a DatabaseTarget")
        if not isinstance(self.secret_provider, SecretProviderMode):
            raise ValueError("secret_provider must be a SecretProviderMode")
        if self.database_secret_reference is not None and not isinstance(
            self.database_secret_reference, SecretReference
        ):
            raise ValueError("database_secret_reference must be a SecretReference")
        if not isinstance(self.worker, WorkerSupervisorConfig):
            raise ValueError("worker must be a WorkerSupervisorConfig")
        if not isinstance(self.replay_protection, ReplayProtectionPolicy):
            raise ValueError("replay_protection must be a ReplayProtectionPolicy")
        if not isinstance(self.enabled_features, frozenset) or any(
            not isinstance(item, Phase4Feature) for item in self.enabled_features
        ):
            raise ValueError("enabled_features must be an immutable Phase4Feature set")
        if type(self.debug) is not bool:
            raise ValueError("debug must be boolean")

        remote_environment = self.environment in {
            DeploymentEnvironment.STAGING,
            DeploymentEnvironment.PRODUCTION,
        }
        if remote_environment:
            if self.database.backend is not DatabaseBackend.POSTGRESQL:
                raise ValueError("staging and production require PostgreSQL")
            if self.secret_provider is not SecretProviderMode.ENVIRONMENT:
                raise ValueError(
                    "staging and production require the environment secret provider"
                )
            if self.debug:
                raise ValueError("staging and production cannot enable debug mode")

        if self.database.backend is DatabaseBackend.SQLITE:
            if self.database_secret_reference is not None:
                raise ValueError("SQLite cannot use a database secret reference")
            if self.secret_provider is not SecretProviderMode.DISABLED:
                raise ValueError("SQLite configuration must disable secret resolution")
            sqlite_path = self.database.sqlite_path.resolve(strict=False)
            _require_within(sqlite_path, runtime_root, "database.sqlite_path")
        else:
            if self.database_secret_reference is None:
                raise ValueError("PostgreSQL requires a database secret reference")
            if self.secret_provider is SecretProviderMode.DISABLED:
                raise ValueError("PostgreSQL requires an enabled secret provider")
            if (
                self.database.connection_reference
                != self.database_secret_reference.reference_id
            ):
                raise ValueError("database connection and secret references must match")

        if (
            not remote_environment
            and self.secret_provider is SecretProviderMode.ENVIRONMENT
            and self.database.backend is not DatabaseBackend.POSTGRESQL
        ):
            raise ValueError("environment secret provider requires PostgreSQL")

        if self.environment is DeploymentEnvironment.TEST and (
            self.database.backend is not DatabaseBackend.SQLITE
        ):
            raise ValueError("test environment requires isolated SQLite storage")

    def public_values(self) -> Mapping[str, object]:
        """Return immutable build metadata containing references, never secret material."""

        values: dict[str, object] = {
            "environment": self.environment.value,
            "service_name": self.service_name,
            "runtime_root": str(self.runtime_root),
            "backup_root": str(self.backup_root),
            "database_backend": self.database.backend.value,
            "database_name": self.database.database_name,
            "database_access_mode": self.database.access_mode.value,
            "database_connection_reference": (
                self.database_secret_reference.reference_id
                if self.database_secret_reference is not None
                else None
            ),
            "secret_provider": self.secret_provider.value,
            "enabled_features": tuple(sorted(item.value for item in self.enabled_features)),
            "debug": self.debug,
            "authentication_required": self.authentication_required,
            "live_trading_enabled": self.live_trading_enabled,
        }
        return MappingProxyType(values)
