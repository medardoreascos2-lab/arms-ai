"""Pure local application rollback rehearsal; it never mutates a database."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import re


_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_FORBIDDEN_FLAGS = frozenset({
    "live_trading",
    "broker_execution",
    "production_mutation",
    "disable_authorization",
    "disable_risk_controls",
})


class AppRollbackStatus(str, Enum):
    REHEARSED_HEALTHY = "REHEARSED_HEALTHY"
    REHEARSED_HEALTH_BLOCKED = "REHEARSED_HEALTH_BLOCKED"
    BLOCKED_SCHEMA = "BLOCKED_SCHEMA"
    BLOCKED_WORKER = "BLOCKED_WORKER"


@dataclass(frozen=True)
class StagingReleaseArtifact:
    version: str
    minimum_schema_version: int
    maximum_schema_version: int
    feature_flags: tuple[str, ...]
    compatible_worker_protocols: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.version, str) or _IDENTIFIER.fullmatch(self.version) is None:
            raise ValueError("version is invalid")
        for name in ("minimum_schema_version", "maximum_schema_version"):
            value = getattr(self, name)
            if type(value) is not int or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        if self.minimum_schema_version > self.maximum_schema_version:
            raise ValueError("schema compatibility range is invalid")
        for name in ("feature_flags", "compatible_worker_protocols"):
            values = getattr(self, name)
            if (
                not isinstance(values, tuple)
                or not values
                or values != tuple(sorted(set(values)))
                or any(_IDENTIFIER.fullmatch(item) is None for item in values)
            ):
                raise ValueError(f"{name} must be a sorted unique identifier tuple")
        if _FORBIDDEN_FLAGS.intersection(self.feature_flags):
            raise ValueError("feature_flags contain unsafe authority")

    def supports_schema(self, schema_version: int) -> bool:
        return self.minimum_schema_version <= schema_version <= self.maximum_schema_version


@dataclass(frozen=True)
class StagingRuntimeSnapshot:
    application_version: str
    schema_version: int
    feature_flags: tuple[str, ...]
    worker_protocols: tuple[str, ...]
    dependencies_healthy: bool

    def __post_init__(self) -> None:
        if (
            not isinstance(self.application_version, str)
            or _IDENTIFIER.fullmatch(self.application_version) is None
        ):
            raise ValueError("application_version is invalid")
        if type(self.schema_version) is not int or self.schema_version < 1:
            raise ValueError("schema_version must be a positive integer")
        for name in ("feature_flags", "worker_protocols"):
            values = getattr(self, name)
            if (
                not isinstance(values, tuple)
                or not values
                or values != tuple(sorted(set(values)))
                or any(_IDENTIFIER.fullmatch(item) is None for item in values)
            ):
                raise ValueError(f"{name} must be a sorted unique identifier tuple")
        if type(self.dependencies_healthy) is not bool:
            raise ValueError("dependencies_healthy must be bool")


@dataclass(frozen=True)
class StagingRollbackHealth:
    healthy: bool
    ready: bool
    blocking_reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.ready and not self.healthy:
            raise ValueError("an unhealthy rollback cannot be ready")
        if self.healthy == bool(self.blocking_reasons):
            raise ValueError("health must reconcile with blocking_reasons")


@dataclass(frozen=True)
class StagingAppRollbackReport:
    status: AppRollbackStatus
    before: StagingRuntimeSnapshot
    after: StagingRuntimeSnapshot
    health: StagingRollbackHealth
    application_rollback_completed: bool
    database_restore_escalation_required: bool
    reverse_database_migration_attempted: bool = field(default=False, init=False)
    database_restore_attempted: bool = field(default=False, init=False)
    external_deployment_authorized: bool = field(default=False, init=False)
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)
    live_trading_authorized: bool = field(default=False, init=False)


class StagingAppRollbackRehearsal:
    """Rehearses artifact selection while preserving the observed schema."""

    external_deployment_authorized = False
    execution_authorized = False
    production_mutation_authorized = False
    live_trading_authorized = False

    def rehearse(
        self,
        current: StagingRuntimeSnapshot,
        candidate: StagingReleaseArtifact,
    ) -> StagingAppRollbackReport:
        if not isinstance(current, StagingRuntimeSnapshot):
            raise ValueError("current must be StagingRuntimeSnapshot")
        if not isinstance(candidate, StagingReleaseArtifact):
            raise ValueError("candidate must be StagingReleaseArtifact")
        if not candidate.supports_schema(current.schema_version):
            return self._blocked(
                AppRollbackStatus.BLOCKED_SCHEMA,
                current,
                "SCHEMA_INCOMPATIBLE",
                restore_required=True,
            )
        if any(
            protocol not in candidate.compatible_worker_protocols
            for protocol in current.worker_protocols
        ):
            return self._blocked(
                AppRollbackStatus.BLOCKED_WORKER,
                current,
                "WORKER_PROTOCOL_INCOMPATIBLE",
                restore_required=False,
            )

        after = StagingRuntimeSnapshot(
            application_version=candidate.version,
            schema_version=current.schema_version,
            feature_flags=candidate.feature_flags,
            worker_protocols=current.worker_protocols,
            dependencies_healthy=current.dependencies_healthy,
        )
        if current.dependencies_healthy:
            health = StagingRollbackHealth(True, True, ())
            status = AppRollbackStatus.REHEARSED_HEALTHY
        else:
            health = StagingRollbackHealth(False, False, ("DEPENDENCY_UNHEALTHY",))
            status = AppRollbackStatus.REHEARSED_HEALTH_BLOCKED
        return StagingAppRollbackReport(
            status=status,
            before=current,
            after=after,
            health=health,
            application_rollback_completed=True,
            database_restore_escalation_required=False,
        )

    @staticmethod
    def _blocked(
        status: AppRollbackStatus,
        current: StagingRuntimeSnapshot,
        reason: str,
        *,
        restore_required: bool,
    ) -> StagingAppRollbackReport:
        return StagingAppRollbackReport(
            status=status,
            before=current,
            after=current,
            health=StagingRollbackHealth(False, False, (reason,)),
            application_rollback_completed=False,
            database_restore_escalation_required=restore_required,
        )
