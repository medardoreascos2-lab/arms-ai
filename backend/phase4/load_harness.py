"""Bounded, in-process Phase 4 load harness with no external traffic authority."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
import math
import re
import time


_OPERATION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class LoadDomain(str, Enum):
    SNAPSHOT_INGESTION = "SNAPSHOT_INGESTION"
    EVALUATION = "EVALUATION"
    READ_API = "READ_API"
    RESEARCH_QUEUE = "RESEARCH_QUEUE"
    AUDIT_LOG = "AUDIT_LOG"
    OUTBOX = "OUTBOX"


@dataclass(frozen=True)
class LoadHarnessConfig:
    maximum_workers: int = 4
    maximum_in_flight: int = 16

    def __post_init__(self) -> None:
        if type(self.maximum_workers) is not int or not 1 <= self.maximum_workers <= 32:
            raise ValueError("maximum_workers must be between 1 and 32")
        if type(self.maximum_in_flight) is not int or not 1 <= self.maximum_in_flight <= 1024:
            raise ValueError("maximum_in_flight must be between 1 and 1024")
        if self.maximum_in_flight < self.maximum_workers:
            raise ValueError("maximum_in_flight cannot be less than maximum_workers")


@dataclass(frozen=True)
class LoadOperation:
    operation_id: str
    domain: LoadDomain
    action: Callable[[], object] = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.operation_id, str) or _OPERATION_ID.fullmatch(
            self.operation_id
        ) is None:
            raise ValueError("operation_id is invalid")
        if not isinstance(self.domain, LoadDomain):
            raise ValueError("domain must be a LoadDomain")
        if not callable(self.action):
            raise ValueError("action must be callable")


@dataclass(frozen=True)
class LoadSample:
    operation_id: str
    domain: LoadDomain
    queued_at_ns: int
    started_at_ns: int
    finished_at_ns: int
    succeeded: bool
    error_code: str | None

    @property
    def latency_ns(self) -> int:
        return self.finished_at_ns - self.started_at_ns

    @property
    def queue_lag_ns(self) -> int:
        return self.started_at_ns - self.queued_at_ns


@dataclass(frozen=True)
class DomainLoadMetrics:
    domain: LoadDomain
    attempted: int
    succeeded: int
    failed: int
    throughput_per_second: Decimal
    average_latency_ns: int
    p95_latency_ns: int
    maximum_latency_ns: int
    maximum_queue_lag_ns: int
    error_rate: Decimal


@dataclass(frozen=True)
class LoadTestReport:
    started_at_ns: int
    finished_at_ns: int
    maximum_queue_depth: int
    samples: tuple[LoadSample, ...]
    metrics: tuple[DomainLoadMetrics, ...]
    external_traffic_authorized: bool = field(default=False, init=False)
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)
    live_trading_authorized: bool = field(default=False, init=False)

    @property
    def duration_ns(self) -> int:
        return self.finished_at_ns - self.started_at_ns


class IsolatedLoadHarness:
    """Runs injected local operations with bounded workers and bounded submission."""

    external_traffic_authorized = False
    execution_authorized = False
    production_mutation_authorized = False
    live_trading_authorized = False

    def __init__(
        self,
        config: LoadHarnessConfig = LoadHarnessConfig(),
        *,
        monotonic_ns: Callable[[], int] = time.perf_counter_ns,
    ) -> None:
        if not isinstance(config, LoadHarnessConfig):
            raise ValueError("config must be LoadHarnessConfig")
        if not callable(monotonic_ns):
            raise ValueError("monotonic_ns must be callable")
        self.config = config
        self._clock = monotonic_ns

    def run(self, operations: tuple[LoadOperation, ...]) -> LoadTestReport:
        if not isinstance(operations, tuple) or not operations or any(
            not isinstance(item, LoadOperation) for item in operations
        ):
            raise ValueError("operations must be a nonempty LoadOperation tuple")
        ids = tuple(item.operation_id for item in operations)
        if len(set(ids)) != len(ids):
            raise ValueError("operation IDs must be unique")
        run_started = self._timestamp()
        samples: list[LoadSample] = []
        maximum_queue_depth = 0
        operation_iterator = iter(operations)

        with ThreadPoolExecutor(max_workers=self.config.maximum_workers) as executor:
            pending: dict[Future[LoadSample], LoadOperation] = {}

            def submit_next() -> bool:
                nonlocal maximum_queue_depth
                try:
                    operation = next(operation_iterator)
                except StopIteration:
                    return False
                queued_at = self._timestamp()
                future = executor.submit(self._execute, operation, queued_at)
                pending[future] = operation
                maximum_queue_depth = max(maximum_queue_depth, len(pending))
                return True

            while len(pending) < self.config.maximum_in_flight and submit_next():
                pass
            while pending:
                completed, _ = wait(tuple(pending), return_when=FIRST_COMPLETED)
                for future in completed:
                    pending.pop(future)
                    samples.append(future.result())
                while len(pending) < self.config.maximum_in_flight and submit_next():
                    pass

        run_finished = self._timestamp()
        if run_finished < run_started:
            raise ValueError("monotonic clock moved backwards")
        if run_finished == run_started:
            run_finished += 1
        ordered_samples = tuple(sorted(samples, key=lambda item: item.operation_id))
        metrics = tuple(
            self._metrics(domain, ordered_samples, run_finished - run_started)
            for domain in LoadDomain
        )
        return LoadTestReport(
            run_started,
            run_finished,
            maximum_queue_depth,
            ordered_samples,
            metrics,
        )

    def _timestamp(self) -> int:
        value = self._clock()
        if type(value) is not int or value < 0:
            raise ValueError("monotonic clock must return a nonnegative integer")
        return value

    def _execute(self, operation: LoadOperation, queued_at: int) -> LoadSample:
        started_at = self._timestamp()
        if started_at < queued_at:
            raise ValueError("monotonic clock moved backwards")
        succeeded = True
        error_code = None
        try:
            operation.action()
        except Exception as exc:
            succeeded = False
            error_code = type(exc).__name__
        finished_at = self._timestamp()
        if finished_at < started_at:
            raise ValueError("monotonic clock moved backwards")
        return LoadSample(
            operation.operation_id,
            operation.domain,
            queued_at,
            started_at,
            finished_at,
            succeeded,
            error_code,
        )

    @staticmethod
    def _metrics(
        domain: LoadDomain,
        samples: tuple[LoadSample, ...],
        duration_ns: int,
    ) -> DomainLoadMetrics:
        selected = tuple(item for item in samples if item.domain is domain)
        attempted = len(selected)
        succeeded = sum(item.succeeded for item in selected)
        failed = attempted - succeeded
        latencies = sorted(item.latency_ns for item in selected)
        p95_index = max(0, math.ceil(len(latencies) * 0.95) - 1)
        return DomainLoadMetrics(
            domain=domain,
            attempted=attempted,
            succeeded=succeeded,
            failed=failed,
            throughput_per_second=(
                Decimal(succeeded) * Decimal(1_000_000_000) / Decimal(duration_ns)
            ),
            average_latency_ns=(sum(latencies) // attempted if attempted else 0),
            p95_latency_ns=(latencies[p95_index] if latencies else 0),
            maximum_latency_ns=(latencies[-1] if latencies else 0),
            maximum_queue_lag_ns=max(
                (item.queue_lag_ns for item in selected),
                default=0,
            ),
            error_rate=(Decimal(failed) / Decimal(attempted) if attempted else Decimal(0)),
        )
