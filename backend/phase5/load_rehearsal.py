"""Measured, bounded Phase 5 staging load rehearsals with no external authority."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
import math
from threading import Lock

from backend.phase4.load_harness import (
    IsolatedLoadHarness,
    LoadDomain,
    LoadHarnessConfig,
    LoadOperation,
    LoadTestReport,
)


class StagingLoadProfileName(str, Enum):
    SMALL = "SMALL"
    MEDIUM = "MEDIUM"
    STRESS = "STRESS"


@dataclass(frozen=True)
class StagingLoadProfile:
    name: StagingLoadProfileName
    tenant_count: int
    accounts_per_tenant: int
    snapshot_rate: int
    evaluation_rate: int
    api_read_rate: int
    research_jobs_per_minute: int
    notification_rate: int
    outbox_rate: int
    maximum_workers: int
    maximum_in_flight: int
    window_seconds: int = 10

    @property
    def total_accounts(self) -> int:
        return self.tenant_count * self.accounts_per_tenant

    @property
    def research_count(self) -> int:
        return max(1, math.ceil(self.research_jobs_per_minute * self.window_seconds / 60))

    @property
    def notification_count(self) -> int:
        return self.notification_rate * self.window_seconds

    @property
    def domain_counts(self) -> dict[LoadDomain, int]:
        return {
            LoadDomain.SNAPSHOT_INGESTION: self.snapshot_rate * self.window_seconds,
            LoadDomain.EVALUATION: self.evaluation_rate * self.window_seconds,
            LoadDomain.READ_API: self.api_read_rate * self.window_seconds,
            LoadDomain.RESEARCH_QUEUE: self.research_count,
            LoadDomain.OUTBOX: self.outbox_rate * self.window_seconds,
        }

    @property
    def total_operations(self) -> int:
        return sum(self.domain_counts.values())


STAGING_LOAD_PROFILES = {
    StagingLoadProfileName.SMALL: StagingLoadProfile(
        StagingLoadProfileName.SMALL, 2, 4, 2, 2, 20, 1, 1, 2, 4, 16
    ),
    StagingLoadProfileName.MEDIUM: StagingLoadProfile(
        StagingLoadProfileName.MEDIUM, 10, 20, 20, 15, 100, 10, 10, 20, 8, 64
    ),
    StagingLoadProfileName.STRESS: StagingLoadProfile(
        StagingLoadProfileName.STRESS, 25, 40, 100, 80, 500, 60, 50, 100, 16, 256
    ),
}


@dataclass(frozen=True)
class StagingLoadObservation:
    tenant_id: str
    account_id: str
    durable_write_id: str | None = None
    outbox_depth: int | None = None
    worker_available_at_ns: int | None = None
    worker_claimed_at_ns: int | None = None
    scheduler_due_at_ns: int | None = None
    scheduler_claimed_at_ns: int | None = None

    def __post_init__(self) -> None:
        if not self.tenant_id or not self.account_id:
            raise ValueError("observation identity is required")
        if self.outbox_depth is not None and self.outbox_depth < 0:
            raise ValueError("outbox_depth cannot be negative")
        for start, finish, label in (
            (self.worker_available_at_ns, self.worker_claimed_at_ns, "worker"),
            (self.scheduler_due_at_ns, self.scheduler_claimed_at_ns, "scheduler"),
        ):
            if (start is None) != (finish is None):
                raise ValueError(f"{label} timestamps must be provided together")
            if start is not None and (start < 0 or finish < start):
                raise ValueError(f"{label} timestamps are invalid")


@dataclass(frozen=True)
class StagingLoadOperation:
    operation_id: str
    domain: LoadDomain
    tenant_id: str
    account_id: str
    action: Callable[[], StagingLoadObservation] = field(repr=False, compare=False)
    notification_event: bool = False

    def __post_init__(self) -> None:
        if not self.tenant_id or not self.account_id:
            raise ValueError("operation tenant and account are required")
        if self.notification_event and self.domain is not LoadDomain.OUTBOX:
            raise ValueError("notification events must be outbox operations")
        if not callable(self.action):
            raise ValueError("operation action must be callable")


@dataclass(frozen=True)
class StagingLatencyMetrics:
    p50_ns: int
    p95_ns: int
    p99_ns: int


@dataclass(frozen=True)
class StagingLoadRehearsalReport:
    profile: StagingLoadProfileName
    attempted: int
    succeeded: int
    failed: int
    throughput_per_second: Decimal
    latency: StagingLatencyMetrics
    error_rate: Decimal
    maximum_queue_depth: int
    maximum_queue_lag_ns: int
    database_busy_failures: int
    peak_database_occupancy: int
    maximum_worker_lag_ns: int
    maximum_scheduler_lag_ns: int
    final_outbox_depth: int
    maximum_outbox_depth: int
    tenant_isolation_violations: int
    duplicate_durable_writes: int
    samples: LoadTestReport = field(repr=False, compare=False)
    external_traffic_authorized: bool = field(default=False, init=False)
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)
    live_trading_authorized: bool = field(default=False, init=False)

    @property
    def passed(self) -> bool:
        return (
            self.failed == 0
            and self.error_rate == 0
            and self.tenant_isolation_violations == 0
            and self.duplicate_durable_writes == 0
            and not self.external_traffic_authorized
            and not self.execution_authorized
            and not self.production_mutation_authorized
            and not self.live_trading_authorized
        )


class TenantIsolationViolation(RuntimeError):
    """Raised when a load operation returns data outside its declared scope."""


class StagingLoadRehearsal:
    """Validates a complete synthetic profile, then runs it in a bounded harness."""

    external_traffic_authorized = False
    execution_authorized = False
    production_mutation_authorized = False
    live_trading_authorized = False

    def run(
        self,
        profile: StagingLoadProfile,
        operations: tuple[StagingLoadOperation, ...],
    ) -> StagingLoadRehearsalReport:
        self._validate_workload(profile, operations)
        lock = Lock()
        observations: list[StagingLoadObservation] = []
        isolation_violations = 0
        active_database_operations = 0
        peak_database_occupancy = 0

        def measured(operation: StagingLoadOperation) -> Callable[[], None]:
            def invoke() -> None:
                nonlocal isolation_violations
                nonlocal active_database_operations, peak_database_occupancy
                with lock:
                    active_database_operations += 1
                    peak_database_occupancy = max(
                        peak_database_occupancy, active_database_operations
                    )
                try:
                    observation = operation.action()
                    if not isinstance(observation, StagingLoadObservation):
                        raise ValueError("load action must return StagingLoadObservation")
                    if (
                        observation.tenant_id != operation.tenant_id
                        or observation.account_id != operation.account_id
                    ):
                        with lock:
                            isolation_violations += 1
                        raise TenantIsolationViolation("operation crossed tenant/account scope")
                    with lock:
                        observations.append(observation)
                finally:
                    with lock:
                        active_database_operations -= 1

            return invoke

        harness = IsolatedLoadHarness(LoadHarnessConfig(
            maximum_workers=profile.maximum_workers,
            maximum_in_flight=profile.maximum_in_flight,
        ))
        base_report = harness.run(tuple(
            LoadOperation(item.operation_id, item.domain, measured(item))
            for item in operations
        ))
        latencies = sorted(item.latency_ns for item in base_report.samples)
        succeeded = sum(item.succeeded for item in base_report.samples)
        failed = len(base_report.samples) - succeeded
        duration = max(1, base_report.duration_ns)
        write_ids = [
            item.durable_write_id for item in observations
            if item.durable_write_id is not None
        ]
        outbox_depths = [
            item.outbox_depth for item in observations if item.outbox_depth is not None
        ]
        worker_lags = [
            item.worker_claimed_at_ns - item.worker_available_at_ns
            for item in observations if item.worker_available_at_ns is not None
        ]
        scheduler_lags = [
            item.scheduler_claimed_at_ns - item.scheduler_due_at_ns
            for item in observations if item.scheduler_due_at_ns is not None
        ]
        return StagingLoadRehearsalReport(
            profile=profile.name,
            attempted=len(base_report.samples),
            succeeded=succeeded,
            failed=failed,
            throughput_per_second=(
                Decimal(succeeded) * Decimal(1_000_000_000) / Decimal(duration)
            ),
            latency=StagingLatencyMetrics(
                self._nearest_rank(latencies, Decimal("0.50")),
                self._nearest_rank(latencies, Decimal("0.95")),
                self._nearest_rank(latencies, Decimal("0.99")),
            ),
            error_rate=Decimal(failed) / Decimal(len(base_report.samples)),
            maximum_queue_depth=base_report.maximum_queue_depth,
            maximum_queue_lag_ns=max(
                (item.queue_lag_ns for item in base_report.samples), default=0
            ),
            database_busy_failures=sum(
                item.error_code in {"OperationalError", "DatabaseError"}
                for item in base_report.samples
            ),
            peak_database_occupancy=peak_database_occupancy,
            maximum_worker_lag_ns=max(worker_lags, default=0),
            maximum_scheduler_lag_ns=max(scheduler_lags, default=0),
            final_outbox_depth=max(outbox_depths, default=0),
            maximum_outbox_depth=max(outbox_depths, default=0),
            tenant_isolation_violations=isolation_violations,
            duplicate_durable_writes=len(write_ids) - len(set(write_ids)),
            samples=base_report,
        )

    @staticmethod
    def _nearest_rank(values: list[int], percentile: Decimal) -> int:
        if not values:
            return 0
        return values[max(0, math.ceil(len(values) * percentile) - 1)]

    @staticmethod
    def _validate_workload(
        profile: StagingLoadProfile,
        operations: tuple[StagingLoadOperation, ...],
    ) -> None:
        if not isinstance(profile, StagingLoadProfile):
            raise ValueError("profile must be StagingLoadProfile")
        if not isinstance(operations, tuple) or any(
            not isinstance(item, StagingLoadOperation) for item in operations
        ):
            raise ValueError("operations must be a StagingLoadOperation tuple")
        counts = Counter(item.domain for item in operations)
        expected = profile.domain_counts
        if any(counts[domain] != count for domain, count in expected.items()):
            raise ValueError("operation counts do not match the selected profile")
        if any(counts[domain] for domain in (LoadDomain.AUDIT_LOG,)):
            raise ValueError("profile contains an unsupported operation domain")
        notification_count = sum(item.notification_event for item in operations)
        if notification_count != profile.notification_count:
            raise ValueError("notification count does not match the selected profile")
        tenants = {item.tenant_id for item in operations}
        accounts = {(item.tenant_id, item.account_id) for item in operations}
        if len(tenants) != profile.tenant_count or len(accounts) != profile.total_accounts:
            raise ValueError("tenant/account coverage does not match the selected profile")
