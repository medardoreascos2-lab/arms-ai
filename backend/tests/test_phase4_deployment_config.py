"""R46A tests for secret-free environment configuration."""

from pathlib import Path

import pytest

from backend.phase4.database_abstraction import (
    DatabaseAccessMode,
    DatabaseBackend,
    DatabaseConfigurationError,
    DatabaseTarget,
)
from backend.phase4.deployment_config import (
    DeploymentEnvironment,
    Phase4DeploymentConfig,
    Phase4Feature,
    SecretProviderMode,
)
from backend.phase4.request_replay import ReplayProtectionPolicy
from backend.phase4.secret_providers import SecretReference
from backend.phase4.worker_supervisor import WorkerSupervisorConfig


FEATURES = frozenset({
    Phase4Feature.API_READS,
    Phase4Feature.METRICS_EXPORT,
})


def sqlite_target(root: Path) -> DatabaseTarget:
    return DatabaseTarget(
        DatabaseBackend.SQLITE,
        "arms_phase4",
        DatabaseAccessMode.READ_WRITE,
        sqlite_path=root / "state" / "phase4.db",
    )


def postgres_target(reference: str = "database/phase4/main") -> DatabaseTarget:
    return DatabaseTarget(
        DatabaseBackend.POSTGRESQL,
        "arms_phase4",
        DatabaseAccessMode.READ_WRITE,
        connection_reference=reference,
    )


def config(
    root: Path,
    environment: DeploymentEnvironment,
    *,
    database: DatabaseTarget | None = None,
    secret_provider: SecretProviderMode | None = None,
    reference: SecretReference | None = None,
    debug: bool | None = None,
) -> Phase4DeploymentConfig:
    remote = environment in {
        DeploymentEnvironment.STAGING,
        DeploymentEnvironment.PRODUCTION,
    }
    if database is None:
        database = postgres_target() if remote else sqlite_target(root)
    if secret_provider is None:
        secret_provider = (
            SecretProviderMode.ENVIRONMENT if remote else SecretProviderMode.DISABLED
        )
    if reference is None and database.backend is DatabaseBackend.POSTGRESQL:
        reference = SecretReference(database.connection_reference)
    return Phase4DeploymentConfig(
        environment=environment,
        service_name="arms-phase4",
        runtime_root=root,
        backup_root=root / "backups",
        database=database,
        secret_provider=secret_provider,
        database_secret_reference=reference,
        worker=WorkerSupervisorConfig(),
        replay_protection=ReplayProtectionPolicy(),
        enabled_features=FEATURES,
        debug=(environment is DeploymentEnvironment.DEVELOPMENT if debug is None else debug),
    )


@pytest.mark.parametrize("environment", tuple(DeploymentEnvironment))
def test_all_declared_environments_have_valid_explicit_configuration(
    tmp_path, environment
):
    result = config(tmp_path / environment.value, environment)
    assert result.environment is environment
    assert result.authentication_required is True
    assert result.execution_authorized is False
    assert result.production_mutation_authorized is False
    assert result.live_trading_enabled is False
    assert result.deployment_authorized is False


def test_staging_and_production_require_postgres_environment_secrets_and_no_debug(
    tmp_path,
):
    root = tmp_path / "production"
    with pytest.raises(ValueError, match="require PostgreSQL"):
        config(root, DeploymentEnvironment.PRODUCTION, database=sqlite_target(root))
    with pytest.raises(ValueError, match="environment secret provider"):
        config(
            root,
            DeploymentEnvironment.PRODUCTION,
            secret_provider=SecretProviderMode.LOCAL_TEST_FILE,
        )
    with pytest.raises(ValueError, match="cannot enable debug"):
        config(root, DeploymentEnvironment.STAGING, debug=True)


def test_test_environment_requires_isolated_sqlite(tmp_path):
    with pytest.raises(ValueError, match="test environment requires"):
        config(
            tmp_path,
            DeploymentEnvironment.TEST,
            database=postgres_target(),
            secret_provider=SecretProviderMode.ENVIRONMENT,
        )


def test_postgres_requires_matching_opaque_secret_reference(tmp_path):
    with pytest.raises(ValueError, match="requires a database secret reference"):
        Phase4DeploymentConfig(
            DeploymentEnvironment.DEVELOPMENT,
            "arms-phase4",
            tmp_path,
            tmp_path / "backups",
            postgres_target(),
            SecretProviderMode.ENVIRONMENT,
            None,
            WorkerSupervisorConfig(),
            ReplayProtectionPolicy(),
            FEATURES,
            False,
        )
    with pytest.raises(ValueError, match="references must match"):
        config(
            tmp_path,
            DeploymentEnvironment.DEVELOPMENT,
            database=postgres_target(),
            secret_provider=SecretProviderMode.ENVIRONMENT,
            reference=SecretReference("database/phase4/other"),
        )
    with pytest.raises(DatabaseConfigurationError, match="raw PostgreSQL"):
        postgres_target("postgresql://forbidden")


def test_sqlite_and_backup_paths_must_remain_inside_runtime_root(tmp_path):
    runtime_root = tmp_path / "runtime"
    with pytest.raises(ValueError, match="database.sqlite_path"):
        config(
            runtime_root,
            DeploymentEnvironment.DEVELOPMENT,
            database=sqlite_target(tmp_path / "outside"),
        )
    with pytest.raises(ValueError, match="backup_root"):
        Phase4DeploymentConfig(
            DeploymentEnvironment.DEVELOPMENT,
            "arms-phase4",
            runtime_root,
            tmp_path / "outside-backups",
            sqlite_target(runtime_root),
            SecretProviderMode.DISABLED,
            None,
            WorkerSupervisorConfig(),
            ReplayProtectionPolicy(),
            FEATURES,
            True,
        )


def test_public_values_are_immutable_and_contain_only_secret_reference(tmp_path):
    result = config(tmp_path, DeploymentEnvironment.PRODUCTION)
    public = result.public_values()
    assert public["database_connection_reference"] == "database/phase4/main"
    assert "password" not in repr(public).lower()
    assert public["live_trading_enabled"] is False
    with pytest.raises(TypeError):
        public["debug"] = True


def test_feature_flags_are_typed_immutable_and_exclude_live_trading(tmp_path):
    result = config(tmp_path, DeploymentEnvironment.DEVELOPMENT)
    assert isinstance(result.enabled_features, frozenset)
    assert all(isinstance(item, Phase4Feature) for item in result.enabled_features)
    assert all("live" not in item.value for item in Phase4Feature)
    with pytest.raises(ValueError, match="immutable Phase4Feature"):
        Phase4DeploymentConfig(
            DeploymentEnvironment.DEVELOPMENT,
            "arms-phase4",
            tmp_path,
            tmp_path / "backups",
            sqlite_target(tmp_path),
            SecretProviderMode.DISABLED,
            None,
            WorkerSupervisorConfig(),
            ReplayProtectionPolicy(),
            {Phase4Feature.API_READS},
            True,
        )
