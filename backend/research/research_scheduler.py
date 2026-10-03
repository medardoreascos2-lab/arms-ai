"""Bounded in-process scheduler for research jobs during closed markets."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
import hashlib
import json
import re
from threading import RLock


_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class ResearchSchedulerMode(str, Enum):
    LIVE_MARKET = "LIVE_MARKET"
    IDLE = "IDLE"
    WEEKEND_RESEARCH = "WEEKEND_RESEARCH"
    DEEP_RESEARCH = "DEEP_RESEARCH"


class ResearchJobKind(str, Enum):
    BACKTEST = "BACKTEST"
    WALK_FORWARD = "WALK_FORWARD"
    OOS_VALIDATION = "OOS_VALIDATION"
    STRESS = "STRESS"
    REPORT = "REPORT"


def _text(value: object, name: str, *, identifier: bool = False) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be nonempty text")
    normalized = value.strip()
    if len(normalized) > 512:
        raise ValueError(f"{name} is too long")
    if identifier and _ID.fullmatch(normalized) is None:
        raise ValueError(f"{name} is invalid")
    return normalized


def _utc(value: datetime, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _utc_text(value: datetime) -> str:
    return _utc(value, "timestamp").isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def _decimal(value: object, name: str, *, minimum: Decimal, maximum: Decimal) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite Decimal")
    try:
        number = value if isinstance(value, Decimal) else Decimal(str(value))
    except Exception as exc:
        raise ValueError(f"{name} must be a finite Decimal") from exc
    if not number.is_finite():
        raise ValueError(f"{name} must be a finite Decimal")
    if number < minimum or number > maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return number


def _int(value: object, name: str, *, minimum: int) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return value


def _hash(document: dict[str, object]) -> str:
    encoded = json.dumps(
        document, ensure_ascii=False, allow_nan=False,
        sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class MaintenanceWindow:
    starts_at: datetime
    ends_at: datetime

    def __post_init__(self) -> None:
        start = _utc(self.starts_at, "starts_at")
        end = _utc(self.ends_at, "ends_at")
        if start >= end:
            raise ValueError("maintenance window start must precede end")
        object.__setattr__(self, "starts_at", start)
        object.__setattr__(self, "ends_at", end)

    def contains(self, now: datetime) -> bool:
        moment = _utc(now, "now")
        return self.starts_at <= moment < self.ends_at

    def document(self) -> dict[str, str]:
        return {"ends_at": _utc_text(self.ends_at), "starts_at": _utc_text(self.starts_at)}


@dataclass(frozen=True)
class ResearchSchedulerLimits:
    maximum_cpu_percent: Decimal
    maximum_concurrent_jobs: int
    maximum_storage_bytes: int
    maximum_market_state_age_seconds: int
    maintenance_windows: tuple[MaintenanceWindow, ...] = ()
    hash: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "maximum_cpu_percent", _decimal(
            self.maximum_cpu_percent,
            "maximum_cpu_percent",
            minimum=Decimal("0.01"),
            maximum=Decimal("100"),
        ))
        object.__setattr__(self, "maximum_concurrent_jobs", _int(
            self.maximum_concurrent_jobs, "maximum_concurrent_jobs", minimum=1
        ))
        object.__setattr__(self, "maximum_storage_bytes", _int(
            self.maximum_storage_bytes, "maximum_storage_bytes", minimum=1
        ))
        object.__setattr__(self, "maximum_market_state_age_seconds", _int(
            self.maximum_market_state_age_seconds,
            "maximum_market_state_age_seconds",
            minimum=1,
        ))
        if not isinstance(self.maintenance_windows, tuple) or any(
            not isinstance(item, MaintenanceWindow) for item in self.maintenance_windows
        ):
            raise ValueError("maintenance_windows must be a tuple of MaintenanceWindow")
        ordered = tuple(sorted(
            self.maintenance_windows,
            key=lambda item: (item.starts_at, item.ends_at),
        ))
        if ordered != self.maintenance_windows:
            raise ValueError("maintenance_windows must be sorted")
        for previous, current in zip(ordered, ordered[1:]):
            if current.starts_at < previous.ends_at:
                raise ValueError("maintenance_windows cannot overlap")
        object.__setattr__(self, "hash", _hash(self.document(include_hash=False)))

    def document(self, *, include_hash: bool = True) -> dict[str, object]:
        document: dict[str, object] = {
            "maintenance_windows": [item.document() for item in self.maintenance_windows],
            "maximum_concurrent_jobs": self.maximum_concurrent_jobs,
            "maximum_cpu_percent": format(self.maximum_cpu_percent, "f"),
            "maximum_market_state_age_seconds": self.maximum_market_state_age_seconds,
            "maximum_storage_bytes": self.maximum_storage_bytes,
        }
        if include_hash:
            document["hash"] = self.hash
        return document


@dataclass(frozen=True)
class ResearchSchedulerContext:
    now: datetime
    market_is_open: bool
    market_state_observed_at: datetime
    preferred_closed_market_mode: ResearchSchedulerMode
    active_jobs: int
    reserved_cpu_percent: Decimal
    storage_used_bytes: int

    def __post_init__(self) -> None:
        now = _utc(self.now, "now")
        observed = _utc(self.market_state_observed_at, "market_state_observed_at")
        if observed > now:
            raise ValueError("market state observation cannot be in the future")
        if type(self.market_is_open) is not bool:
            raise ValueError("market_is_open must be bool")
        if self.preferred_closed_market_mode not in {
            ResearchSchedulerMode.IDLE,
            ResearchSchedulerMode.WEEKEND_RESEARCH,
            ResearchSchedulerMode.DEEP_RESEARCH,
        }:
            raise ValueError("preferred closed-market mode is invalid")
        object.__setattr__(self, "active_jobs", _int(
            self.active_jobs, "active_jobs", minimum=0
        ))
        object.__setattr__(self, "reserved_cpu_percent", _decimal(
            self.reserved_cpu_percent,
            "reserved_cpu_percent",
            minimum=Decimal("0"),
            maximum=Decimal("100"),
        ))
        object.__setattr__(self, "storage_used_bytes", _int(
            self.storage_used_bytes, "storage_used_bytes", minimum=0
        ))
        object.__setattr__(self, "now", now)
        object.__setattr__(self, "market_state_observed_at", observed)


@dataclass(frozen=True)
class ResearchJobRequest:
    strategy_id: str
    kind: ResearchJobKind
    evidence_ids: tuple[str, ...]
    eligible_modes: tuple[ResearchSchedulerMode, ...]
    estimated_cpu_percent: Decimal
    estimated_storage_bytes: int
    priority: int
    job_id: str = field(init=False)
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "strategy_id", _text(
            self.strategy_id, "strategy_id", identifier=True
        ))
        if not isinstance(self.kind, ResearchJobKind):
            raise ValueError("kind must be ResearchJobKind")
        if not isinstance(self.evidence_ids, tuple) or not self.evidence_ids:
            raise ValueError("evidence_ids must be a nonempty tuple")
        evidence = tuple(sorted(_text(item, "evidence_id", identifier=True) for item in self.evidence_ids))
        if len(set(evidence)) != len(evidence):
            raise ValueError("evidence_ids must be unique")
        object.__setattr__(self, "evidence_ids", evidence)
        valid_modes = {ResearchSchedulerMode.WEEKEND_RESEARCH, ResearchSchedulerMode.DEEP_RESEARCH}
        if not isinstance(self.eligible_modes, tuple) or not self.eligible_modes:
            raise ValueError("eligible_modes must be a nonempty tuple")
        modes = tuple(sorted(self.eligible_modes, key=lambda item: item.value))
        if any(mode not in valid_modes for mode in modes) or len(set(modes)) != len(modes):
            raise ValueError("eligible_modes must contain unique research modes")
        object.__setattr__(self, "eligible_modes", modes)
        object.__setattr__(self, "estimated_cpu_percent", _decimal(
            self.estimated_cpu_percent,
            "estimated_cpu_percent",
            minimum=Decimal("0.01"),
            maximum=Decimal("100"),
        ))
        object.__setattr__(self, "estimated_storage_bytes", _int(
            self.estimated_storage_bytes, "estimated_storage_bytes", minimum=1
        ))
        object.__setattr__(self, "priority", _int(self.priority, "priority", minimum=0))
        object.__setattr__(self, "job_id", _hash(self.document(include_job_id=False)))

    def document(self, *, include_job_id: bool = True) -> dict[str, object]:
        document: dict[str, object] = {
            "eligible_modes": [mode.value for mode in self.eligible_modes],
            "estimated_cpu_percent": format(self.estimated_cpu_percent, "f"),
            "estimated_storage_bytes": self.estimated_storage_bytes,
            "evidence_ids": list(self.evidence_ids),
            "kind": self.kind.value,
            "priority": self.priority,
            "strategy_id": self.strategy_id,
        }
        if include_job_id:
            document["job_id"] = self.job_id
        return document


@dataclass(frozen=True)
class ResearchJobEnqueueResult:
    job: ResearchJobRequest
    inserted: bool
    duplicate: bool

    def __post_init__(self) -> None:
        if not isinstance(self.job, ResearchJobRequest):
            raise ValueError("job must be ResearchJobRequest")
        if self.inserted == self.duplicate:
            raise ValueError("enqueue result must be inserted or duplicate")


class ResearchJobQueue:
    """In-process idempotent research queue with no worker or execution authority."""

    execution_authorized = False
    production_mutation_authorized = False
    operating_system_scheduler_authorized = False

    def __init__(self) -> None:
        self._jobs: dict[str, ResearchJobRequest] = {}
        self._lock = RLock()

    def enqueue(self, job: ResearchJobRequest) -> ResearchJobEnqueueResult:
        if not isinstance(job, ResearchJobRequest):
            raise ValueError("job must be ResearchJobRequest")
        with self._lock:
            existing = self._jobs.get(job.job_id)
            if existing is not None:
                return ResearchJobEnqueueResult(existing, False, True)
            self._jobs[job.job_id] = job
            return ResearchJobEnqueueResult(job, True, False)

    def get(self, job_id: str) -> ResearchJobRequest | None:
        key = _text(job_id, "job_id")
        with self._lock:
            return self._jobs.get(key)

    def list(self) -> tuple[ResearchJobRequest, ...]:
        with self._lock:
            return tuple(self._jobs[key] for key in sorted(self._jobs))


@dataclass(frozen=True)
class DeferredResearchJob:
    job_id: str
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.job_id, str) or _SHA256.fullmatch(self.job_id) is None:
            raise ValueError("job_id must be a lowercase sha256 digest")
        object.__setattr__(self, "reason", _text(self.reason, "reason", identifier=True))


@dataclass(frozen=True)
class ResearchScheduleDecision:
    mode: ResearchSchedulerMode
    enqueued: tuple[ResearchJobEnqueueResult, ...]
    deferred: tuple[DeferredResearchJob, ...]
    blocking_reasons: tuple[str, ...]
    cpu_percent_after: Decimal
    concurrent_jobs_after: int
    storage_bytes_after: int
    limits_hash: str
    evaluated_at: datetime
    decision_id: str = field(init=False)
    production_strategy_modified: bool = field(default=False, init=False)
    execution_authorized: bool = field(default=False, init=False)
    live_execution_authorized: bool = field(default=False, init=False)
    operating_system_scheduler_modified: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.mode, ResearchSchedulerMode):
            raise ValueError("mode must be ResearchSchedulerMode")
        if not isinstance(self.enqueued, tuple) or any(
            not isinstance(item, ResearchJobEnqueueResult) for item in self.enqueued
        ):
            raise ValueError("enqueued must be a tuple of ResearchJobEnqueueResult")
        if not isinstance(self.deferred, tuple) or any(
            not isinstance(item, DeferredResearchJob) for item in self.deferred
        ):
            raise ValueError("deferred must be a tuple of DeferredResearchJob")
        if self.mode in {ResearchSchedulerMode.LIVE_MARKET, ResearchSchedulerMode.IDLE} and self.enqueued:
            raise ValueError("LIVE_MARKET and IDLE decisions cannot enqueue jobs")
        if self.blocking_reasons != tuple(sorted(set(self.blocking_reasons))):
            raise ValueError("blocking_reasons must be sorted and unique")
        object.__setattr__(self, "cpu_percent_after", _decimal(
            self.cpu_percent_after,
            "cpu_percent_after",
            minimum=Decimal("0"),
            maximum=Decimal("100"),
        ))
        object.__setattr__(self, "concurrent_jobs_after", _int(
            self.concurrent_jobs_after, "concurrent_jobs_after", minimum=0
        ))
        object.__setattr__(self, "storage_bytes_after", _int(
            self.storage_bytes_after, "storage_bytes_after", minimum=0
        ))
        if not isinstance(self.limits_hash, str) or _SHA256.fullmatch(self.limits_hash) is None:
            raise ValueError("limits_hash must be a lowercase sha256 digest")
        object.__setattr__(self, "evaluated_at", _utc(self.evaluated_at, "evaluated_at"))
        object.__setattr__(self, "decision_id", _hash(self.document(
            include_decision_id=False
        )))

    def document(self, *, include_decision_id: bool = True) -> dict[str, object]:
        document: dict[str, object] = {
            "blocking_reasons": list(self.blocking_reasons),
            "concurrent_jobs_after": self.concurrent_jobs_after,
            "cpu_percent_after": format(self.cpu_percent_after, "f"),
            "deferred": [item.__dict__ for item in self.deferred],
            "enqueued": [
                {"duplicate": item.duplicate, "inserted": item.inserted, "job_id": item.job.job_id}
                for item in self.enqueued
            ],
            "evaluated_at": _utc_text(self.evaluated_at),
            "limits_hash": self.limits_hash,
            "mode": self.mode.value,
            "storage_bytes_after": self.storage_bytes_after,
        }
        if include_decision_id:
            document["decision_id"] = self.decision_id
        return document


class WeekendResearchScheduler:
    """Enqueues bounded research work only from a fresh closed-market state."""

    production_strategy_modified = False
    execution_authorized = False
    live_execution_authorized = False
    operating_system_scheduler_modified = False

    def __init__(self, queue: ResearchJobQueue, limits: ResearchSchedulerLimits):
        if not isinstance(queue, ResearchJobQueue):
            raise ValueError("queue must be ResearchJobQueue")
        if not isinstance(limits, ResearchSchedulerLimits):
            raise ValueError("limits must be ResearchSchedulerLimits")
        self._queue = queue
        self._limits = limits
        self._lock = RLock()

    def schedule(
        self,
        context: ResearchSchedulerContext,
        requests: tuple[ResearchJobRequest, ...],
    ) -> ResearchScheduleDecision:
        if not isinstance(context, ResearchSchedulerContext):
            raise ValueError("context must be ResearchSchedulerContext")
        if not isinstance(requests, tuple) or any(
            not isinstance(item, ResearchJobRequest) for item in requests
        ):
            raise ValueError("requests must be a tuple of ResearchJobRequest")
        if len({item.job_id for item in requests}) != len(requests):
            raise ValueError("requests must have unique job identities")
        with self._lock:
            mode, mode_reason = self._mode(context)
            ordered = tuple(sorted(requests, key=lambda item: (-item.priority, item.job_id)))
            if mode in {ResearchSchedulerMode.LIVE_MARKET, ResearchSchedulerMode.IDLE}:
                reason = mode_reason or "SCHEDULER_IDLE"
                return self._decision(
                    mode, (),
                    tuple(DeferredResearchJob(item.job_id, reason) for item in ordered),
                    (reason,), context,
                )

            cpu = context.reserved_cpu_percent
            jobs = context.active_jobs
            storage = context.storage_used_bytes
            enqueued: list[ResearchJobEnqueueResult] = []
            deferred: list[DeferredResearchJob] = []
            for request in ordered:
                if mode not in request.eligible_modes:
                    deferred.append(DeferredResearchJob(request.job_id, "MODE_NOT_ELIGIBLE"))
                    continue
                existing = self._queue.get(request.job_id)
                if existing is not None:
                    enqueued.append(self._queue.enqueue(request))
                    continue
                if jobs + 1 > self._limits.maximum_concurrent_jobs:
                    deferred.append(DeferredResearchJob(request.job_id, "CONCURRENCY_CAP"))
                    continue
                if cpu + request.estimated_cpu_percent > self._limits.maximum_cpu_percent:
                    deferred.append(DeferredResearchJob(request.job_id, "CPU_CAP"))
                    continue
                if storage + request.estimated_storage_bytes > self._limits.maximum_storage_bytes:
                    deferred.append(DeferredResearchJob(request.job_id, "STORAGE_CAP"))
                    continue
                result = self._queue.enqueue(request)
                enqueued.append(result)
                jobs += 1
                cpu += request.estimated_cpu_percent
                storage += request.estimated_storage_bytes
            reasons = tuple(sorted(set(item.reason for item in deferred)))
            return self._decision(
                mode, tuple(enqueued), tuple(deferred), reasons, context,
                cpu=cpu, jobs=jobs, storage=storage,
            )

    def _mode(self, context: ResearchSchedulerContext) -> tuple[ResearchSchedulerMode, str | None]:
        age = (context.now - context.market_state_observed_at).total_seconds()
        if age > self._limits.maximum_market_state_age_seconds:
            return ResearchSchedulerMode.IDLE, "MARKET_STATE_STALE"
        if context.market_is_open:
            return ResearchSchedulerMode.LIVE_MARKET, "MARKET_OPEN"
        if any(window.contains(context.now) for window in self._limits.maintenance_windows):
            return ResearchSchedulerMode.IDLE, "MAINTENANCE_WINDOW"
        if context.preferred_closed_market_mode is ResearchSchedulerMode.IDLE:
            return ResearchSchedulerMode.IDLE, "SCHEDULER_IDLE"
        return context.preferred_closed_market_mode, None

    def _decision(
        self,
        mode: ResearchSchedulerMode,
        enqueued: tuple[ResearchJobEnqueueResult, ...],
        deferred: tuple[DeferredResearchJob, ...],
        reasons: tuple[str, ...],
        context: ResearchSchedulerContext,
        *,
        cpu: Decimal | None = None,
        jobs: int | None = None,
        storage: int | None = None,
    ) -> ResearchScheduleDecision:
        return ResearchScheduleDecision(
            mode=mode,
            enqueued=enqueued,
            deferred=deferred,
            blocking_reasons=tuple(sorted(set(reasons))),
            cpu_percent_after=context.reserved_cpu_percent if cpu is None else cpu,
            concurrent_jobs_after=context.active_jobs if jobs is None else jobs,
            storage_bytes_after=context.storage_used_bytes if storage is None else storage,
            limits_hash=self._limits.hash,
            evaluated_at=context.now,
        )
