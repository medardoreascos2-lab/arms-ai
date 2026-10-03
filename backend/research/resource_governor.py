"""Fail-closed resource admission for bounded research jobs."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
import hashlib
import json
import re


_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


def _integer(value: object, name: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return value


def _decimal(value: object, name: str) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite nonnegative Decimal")
    try:
        number = value if isinstance(value, Decimal) else Decimal(str(value))
    except Exception as exc:
        raise ValueError(f"{name} must be a finite nonnegative Decimal") from exc
    if not number.is_finite() or number < 0:
        raise ValueError(f"{name} must be a finite nonnegative Decimal")
    return number


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class ResearchResourceLimits:
    maximum_cpu_percent: Decimal
    maximum_concurrent_jobs: int
    maximum_memory_bytes: int
    maximum_disk_bytes: int
    maximum_datasets: int
    maximum_experiments: int
    maximum_runtime_seconds_per_job: int
    limits_hash: str = field(init=False)

    def __post_init__(self) -> None:
        cpu = _decimal(self.maximum_cpu_percent, "maximum_cpu_percent")
        if cpu <= 0 or cpu > 100:
            raise ValueError("maximum_cpu_percent must be within (0, 100]")
        object.__setattr__(self, "maximum_cpu_percent", cpu)
        for name in (
            "maximum_concurrent_jobs", "maximum_memory_bytes", "maximum_disk_bytes",
            "maximum_datasets", "maximum_experiments", "maximum_runtime_seconds_per_job",
        ):
            object.__setattr__(self, name, _integer(getattr(self, name), name, 1))
        object.__setattr__(self, "limits_hash", _digest(self.document(include_hash=False)))

    def document(self, *, include_hash: bool = True) -> dict[str, object]:
        value = {name: format(item, "f") if isinstance(item, Decimal) else item
                 for name, item in self.__dict__.items() if name != "limits_hash"}
        if include_hash:
            value["limits_hash"] = self.limits_hash
        return value


@dataclass(frozen=True)
class ResearchResourceUsage:
    active_jobs: int
    reserved_cpu_percent: Decimal
    memory_used_bytes: int
    disk_used_bytes: int
    dataset_count: int
    experiment_count: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "reserved_cpu_percent", _decimal(self.reserved_cpu_percent, "reserved_cpu_percent"))
        if self.reserved_cpu_percent > 100:
            raise ValueError("reserved_cpu_percent cannot exceed 100")
        for name in ("active_jobs", "memory_used_bytes", "disk_used_bytes", "dataset_count", "experiment_count"):
            object.__setattr__(self, name, _integer(getattr(self, name), name))


@dataclass(frozen=True)
class ResearchResourceRequest:
    job_id: str
    requested_cpu_percent: Decimal
    requested_memory_bytes: int
    requested_disk_bytes: int
    requested_datasets: int
    requested_experiments: int
    maximum_runtime_seconds: int

    def __post_init__(self) -> None:
        if not isinstance(self.job_id, str) or _ID.fullmatch(self.job_id) is None:
            raise ValueError("job_id is invalid")
        cpu = _decimal(self.requested_cpu_percent, "requested_cpu_percent")
        if cpu <= 0 or cpu > 100:
            raise ValueError("requested_cpu_percent must be within (0, 100]")
        object.__setattr__(self, "requested_cpu_percent", cpu)
        for name in ("requested_memory_bytes", "requested_disk_bytes", "maximum_runtime_seconds"):
            object.__setattr__(self, name, _integer(getattr(self, name), name, 1))
        for name in ("requested_datasets", "requested_experiments"):
            object.__setattr__(self, name, _integer(getattr(self, name), name))


@dataclass(frozen=True)
class ResearchResourceDecision:
    job_id: str
    accepted: bool
    blocking_reasons: tuple[str, ...]
    projected_cpu_percent: Decimal
    projected_concurrent_jobs: int
    projected_memory_bytes: int
    projected_disk_bytes: int
    projected_datasets: int
    projected_experiments: int
    limits_hash: str
    execution_authorized: bool = field(default=False, init=False)
    queue_mutation_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if self.accepted != (not self.blocking_reasons):
            raise ValueError("accepted does not reconcile with blocking_reasons")
        if self.blocking_reasons != tuple(sorted(set(self.blocking_reasons))):
            raise ValueError("blocking_reasons must be sorted and unique")


class ResearchResourceGovernor:
    """Evaluate a reservation without reserving resources or enqueuing work."""

    def evaluate(self, request: ResearchResourceRequest, usage: ResearchResourceUsage,
                 limits: ResearchResourceLimits) -> ResearchResourceDecision:
        if not isinstance(request, ResearchResourceRequest) or not isinstance(usage, ResearchResourceUsage) or not isinstance(limits, ResearchResourceLimits):
            raise ValueError("request, usage, and limits are required")
        projected = {
            "cpu": usage.reserved_cpu_percent + request.requested_cpu_percent,
            "jobs": usage.active_jobs + 1,
            "memory": usage.memory_used_bytes + request.requested_memory_bytes,
            "disk": usage.disk_used_bytes + request.requested_disk_bytes,
            "datasets": usage.dataset_count + request.requested_datasets,
            "experiments": usage.experiment_count + request.requested_experiments,
        }
        reasons: list[str] = []
        checks = (
            (projected["cpu"] > limits.maximum_cpu_percent, "CPU_LIMIT_REACHED"),
            (projected["jobs"] > limits.maximum_concurrent_jobs, "CONCURRENCY_LIMIT_REACHED"),
            (projected["memory"] > limits.maximum_memory_bytes, "MEMORY_LIMIT_REACHED"),
            (projected["disk"] > limits.maximum_disk_bytes, "DISK_LIMIT_REACHED"),
            (projected["datasets"] > limits.maximum_datasets, "DATASET_LIMIT_REACHED"),
            (projected["experiments"] > limits.maximum_experiments, "EXPERIMENT_LIMIT_REACHED"),
            (request.maximum_runtime_seconds > limits.maximum_runtime_seconds_per_job, "JOB_RUNTIME_LIMIT_REACHED"),
        )
        reasons.extend(reason for failed, reason in checks if failed)
        return ResearchResourceDecision(request.job_id, not reasons, tuple(sorted(reasons)),
                                        projected["cpu"], projected["jobs"], projected["memory"],
                                        projected["disk"], projected["datasets"], projected["experiments"],
                                        limits.limits_hash)
