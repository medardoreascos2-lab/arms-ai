"""Provider-neutral scheduler leases for Phase 4 supervised jobs."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
import re
from threading import RLock
from typing import Protocol, runtime_checkable
import uuid

from .secret_redaction import RedactedRecord, SecretRedactor


_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{15,255}$")


def _utc(value: datetime, name: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


class SchedulerLeaseError(RuntimeError):
    pass


class SchedulerJobKind(str, Enum):
    RESEARCH_SCHEDULER = "RESEARCH_SCHEDULER"
    OUTBOX_WORKER = "OUTBOX_WORKER"
    MAINTENANCE = "MAINTENANCE"


class SchedulerClaimStatus(str, Enum):
    CLAIMED = "CLAIMED"
    NOT_DUE = "NOT_DUE"
    LEASE_HELD = "LEASE_HELD"


class SchedulerRunStatus(str, Enum):
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    NOT_DUE = "NOT_DUE"
    LEASE_HELD = "LEASE_HELD"
    LEASE_LOST = "LEASE_LOST"


@dataclass(frozen=True)
class ScheduledJobSpec:
    job_id: str
    kind: SchedulerJobKind
    interval_seconds: int
    lease_seconds: int
    first_due_at: datetime
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.job_id, str) or _ID.fullmatch(self.job_id) is None:
            raise ValueError("job_id is invalid")
        if not isinstance(self.kind, SchedulerJobKind):
            raise ValueError("kind must be a SchedulerJobKind")
        for name in ("interval_seconds", "lease_seconds"):
            if type(getattr(self, name)) is not int or getattr(self, name) < 1:
                raise ValueError(f"{name} must be a positive integer")
        object.__setattr__(self, "first_due_at", _utc(self.first_due_at, "first_due_at"))


@dataclass(frozen=True)
class SchedulerClaim:
    job_id: str
    scheduler_id: str
    generation: int
    lease_token: str = field(repr=False)
    acquired_at: datetime
    expires_at: datetime
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        for name in ("job_id", "scheduler_id"):
            if not isinstance(getattr(self, name), str) or _ID.fullmatch(
                getattr(self, name)
            ) is None:
                raise ValueError(f"{name} is invalid")
        if type(self.generation) is not int or self.generation < 1:
            raise ValueError("generation must be positive")
        if not isinstance(self.lease_token, str) or _TOKEN.fullmatch(
            self.lease_token
        ) is None:
            raise ValueError("lease_token is invalid")
        acquired = _utc(self.acquired_at, "acquired_at")
        expires = _utc(self.expires_at, "expires_at")
        if expires <= acquired:
            raise ValueError("lease expiration must follow acquisition")
        object.__setattr__(self, "acquired_at", acquired)
        object.__setattr__(self, "expires_at", expires)


@dataclass(frozen=True)
class SchedulerClaimResult:
    status: SchedulerClaimStatus
    claim: SchedulerClaim | None
    execution_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.status, SchedulerClaimStatus):
            raise ValueError("status must be a SchedulerClaimStatus")
        if (self.status is SchedulerClaimStatus.CLAIMED) != (self.claim is not None):
            raise ValueError("only CLAIMED results may carry a claim")


@dataclass(frozen=True)
class ScheduledJobState:
    spec: ScheduledJobSpec
    next_due_at: datetime
    generation: int
    lease_owner: str | None
    lease_expires_at: datetime | None
    last_completed_at: datetime | None
    last_failure: RedactedRecord | None
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)


@runtime_checkable
class SchedulerLeaseStore(Protocol):
    execution_authorized: bool
    production_mutation_authorized: bool

    def register(self, spec: ScheduledJobSpec) -> ScheduledJobState: ...

    def try_claim(
        self, *, job_id: str, scheduler_id: str, now: datetime
    ) -> SchedulerClaimResult: ...

    def renew(self, claim: SchedulerClaim, *, now: datetime) -> SchedulerClaim: ...

    def complete(
        self, claim: SchedulerClaim, *, completed_at: datetime
    ) -> ScheduledJobState: ...

    def fail(
        self,
        claim: SchedulerClaim,
        *,
        failed_at: datetime,
        failure: RedactedRecord,
    ) -> ScheduledJobState: ...

    def state(self, job_id: str) -> ScheduledJobState: ...


@dataclass
class _MutableJobState:
    spec: ScheduledJobSpec
    next_due_at: datetime
    generation: int = 0
    lease_owner: str | None = None
    lease_token: str | None = None
    lease_acquired_at: datetime | None = None
    lease_expires_at: datetime | None = None
    last_completed_at: datetime | None = None
    last_failure: RedactedRecord | None = None


class InMemorySchedulerLeaseStore:
    """Shared local/test lease store; persistence is supplied by a future adapter."""

    execution_authorized = False
    production_mutation_authorized = False
    external_delivery_authorized = False

    def __init__(self, token_factory: Callable[[], str] | None = None):
        if token_factory is not None and not callable(token_factory):
            raise ValueError("token_factory must be callable")
        self._token_factory = token_factory or (lambda: uuid.uuid4().hex)
        self._states: dict[str, _MutableJobState] = {}
        self._lock = RLock()

    def _token(self) -> str:
        token = self._token_factory()
        if not isinstance(token, str) or _TOKEN.fullmatch(token) is None:
            raise SchedulerLeaseError("token factory returned an invalid lease token")
        return token

    def register(self, spec: ScheduledJobSpec) -> ScheduledJobState:
        if not isinstance(spec, ScheduledJobSpec):
            raise ValueError("spec must be a ScheduledJobSpec")
        with self._lock:
            existing = self._states.get(spec.job_id)
            if existing is None:
                existing = _MutableJobState(spec, spec.first_due_at)
                self._states[spec.job_id] = existing
            elif existing.spec != spec:
                raise SchedulerLeaseError("job registration conflicts with stored spec")
            return self._snapshot(existing)

    def try_claim(
        self,
        *,
        job_id: str,
        scheduler_id: str,
        now: datetime,
    ) -> SchedulerClaimResult:
        moment = _utc(now, "now")
        if not isinstance(scheduler_id, str) or _ID.fullmatch(scheduler_id) is None:
            raise ValueError("scheduler_id is invalid")
        with self._lock:
            state = self._states.get(job_id)
            if state is None:
                raise SchedulerLeaseError("job is not registered")
            if moment < state.next_due_at:
                return SchedulerClaimResult(SchedulerClaimStatus.NOT_DUE, None)
            if (
                state.lease_owner is not None
                and state.lease_expires_at is not None
                and moment < state.lease_expires_at
            ):
                return SchedulerClaimResult(SchedulerClaimStatus.LEASE_HELD, None)
            token = self._token()
            state.generation += 1
            state.lease_owner = scheduler_id
            state.lease_token = token
            state.lease_acquired_at = moment
            state.lease_expires_at = moment + timedelta(
                seconds=state.spec.lease_seconds
            )
            claim = SchedulerClaim(
                job_id=job_id,
                scheduler_id=scheduler_id,
                generation=state.generation,
                lease_token=token,
                acquired_at=moment,
                expires_at=state.lease_expires_at,
            )
            return SchedulerClaimResult(SchedulerClaimStatus.CLAIMED, claim)

    def renew(self, claim: SchedulerClaim, *, now: datetime) -> SchedulerClaim:
        moment = _utc(now, "now")
        with self._lock:
            state = self._owned_state(claim, moment)
            state.lease_expires_at = moment + timedelta(
                seconds=state.spec.lease_seconds
            )
            return SchedulerClaim(
                job_id=claim.job_id,
                scheduler_id=claim.scheduler_id,
                generation=claim.generation,
                lease_token=claim.lease_token,
                acquired_at=claim.acquired_at,
                expires_at=state.lease_expires_at,
            )

    def complete(
        self,
        claim: SchedulerClaim,
        *,
        completed_at: datetime,
    ) -> ScheduledJobState:
        moment = _utc(completed_at, "completed_at")
        with self._lock:
            state = self._owned_state(claim, moment)
            state.next_due_at = moment + timedelta(seconds=state.spec.interval_seconds)
            state.last_completed_at = moment
            state.last_failure = None
            self._clear_lease(state)
            return self._snapshot(state)

    def fail(
        self,
        claim: SchedulerClaim,
        *,
        failed_at: datetime,
        failure: RedactedRecord,
    ) -> ScheduledJobState:
        moment = _utc(failed_at, "failed_at")
        if not isinstance(failure, RedactedRecord):
            raise ValueError("failure must be a RedactedRecord")
        with self._lock:
            state = self._owned_state(claim, moment)
            state.next_due_at = moment + timedelta(seconds=state.spec.interval_seconds)
            state.last_failure = failure
            self._clear_lease(state)
            return self._snapshot(state)

    def state(self, job_id: str) -> ScheduledJobState:
        with self._lock:
            state = self._states.get(job_id)
            if state is None:
                raise SchedulerLeaseError("job is not registered")
            return self._snapshot(state)

    def _owned_state(
        self, claim: SchedulerClaim, now: datetime
    ) -> _MutableJobState:
        if not isinstance(claim, SchedulerClaim):
            raise ValueError("claim must be a SchedulerClaim")
        state = self._states.get(claim.job_id)
        if (
            state is None
            or state.lease_owner != claim.scheduler_id
            or state.lease_token != claim.lease_token
            or state.generation != claim.generation
            or state.lease_acquired_at != claim.acquired_at
            or state.lease_expires_at != claim.expires_at
            or now >= claim.expires_at
        ):
            raise SchedulerLeaseError("scheduler lease is no longer owned")
        return state

    @staticmethod
    def _clear_lease(state: _MutableJobState) -> None:
        state.lease_owner = None
        state.lease_token = None
        state.lease_acquired_at = None
        state.lease_expires_at = None

    @staticmethod
    def _snapshot(state: _MutableJobState) -> ScheduledJobState:
        return ScheduledJobState(
            spec=state.spec,
            next_due_at=state.next_due_at,
            generation=state.generation,
            lease_owner=state.lease_owner,
            lease_expires_at=state.lease_expires_at,
            last_completed_at=state.last_completed_at,
            last_failure=state.last_failure,
        )


@dataclass
class SchedulerRunContext:
    job: ScheduledJobSpec
    scheduler_id: str
    claim: SchedulerClaim
    _heartbeat: Callable[[SchedulerClaim], SchedulerClaim] = field(repr=False)
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)

    def heartbeat(self) -> SchedulerClaim:
        self.claim = self._heartbeat(self.claim)
        return self.claim


@dataclass(frozen=True)
class SchedulerRunResult:
    job_id: str
    kind: SchedulerJobKind
    status: SchedulerRunStatus
    generation: int
    failure: RedactedRecord | None
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)
    external_delivery_authorized: bool = field(default=False, init=False)


ScheduledRunner = Callable[[SchedulerRunContext], None]


class SchedulerSupervisor:
    """Runs due callbacks synchronously after exclusive shared lease acquisition."""

    execution_authorized = False
    production_mutation_authorized = False
    external_delivery_authorized = False
    operating_system_scheduler_modified = False

    def __init__(
        self,
        *,
        scheduler_id: str,
        lease_store: SchedulerLeaseStore,
        clock: Callable[[], datetime],
        redactor: SecretRedactor | None = None,
    ):
        if not isinstance(scheduler_id, str) or _ID.fullmatch(scheduler_id) is None:
            raise ValueError("scheduler_id is invalid")
        if not isinstance(lease_store, SchedulerLeaseStore):
            raise ValueError("lease_store must implement SchedulerLeaseStore")
        if not callable(clock):
            raise ValueError("clock must be callable")
        self.scheduler_id = scheduler_id
        self.lease_store = lease_store
        self.clock = clock
        self.redactor = redactor or SecretRedactor()
        self._jobs: dict[str, tuple[ScheduledJobSpec, ScheduledRunner]] = {}

    def _now(self) -> datetime:
        return _utc(self.clock(), "scheduler clock")

    def register(self, spec: ScheduledJobSpec, runner: ScheduledRunner) -> None:
        if not isinstance(spec, ScheduledJobSpec):
            raise ValueError("spec must be a ScheduledJobSpec")
        if not callable(runner):
            raise ValueError("runner must be callable")
        if spec.job_id in self._jobs:
            raise ValueError("job is already registered by this scheduler")
        self.lease_store.register(spec)
        self._jobs[spec.job_id] = (spec, runner)

    def tick(self) -> tuple[SchedulerRunResult, ...]:
        results = []
        for job_id in sorted(self._jobs):
            spec, runner = self._jobs[job_id]
            claim_result = self.lease_store.try_claim(
                job_id=job_id,
                scheduler_id=self.scheduler_id,
                now=self._now(),
            )
            if claim_result.claim is None:
                status = (
                    SchedulerRunStatus.NOT_DUE
                    if claim_result.status is SchedulerClaimStatus.NOT_DUE
                    else SchedulerRunStatus.LEASE_HELD
                )
                state = self.lease_store.state(job_id)
                results.append(
                    SchedulerRunResult(job_id, spec.kind, status, state.generation, None)
                )
                continue

            context = SchedulerRunContext(
                job=spec,
                scheduler_id=self.scheduler_id,
                claim=claim_result.claim,
                _heartbeat=lambda claim: self.lease_store.renew(
                    claim, now=self._now()
                ),
            )
            try:
                runner(context)
            except Exception as exc:
                failure = self.redactor.worker_failure(job_id, exc)
                try:
                    self.lease_store.fail(
                        context.claim,
                        failed_at=self._now(),
                        failure=failure,
                    )
                    status = SchedulerRunStatus.FAILED
                except SchedulerLeaseError:
                    status = SchedulerRunStatus.LEASE_LOST
                results.append(
                    SchedulerRunResult(
                        job_id, spec.kind, status, context.claim.generation, failure
                    )
                )
                continue
            try:
                self.lease_store.complete(
                    context.claim,
                    completed_at=self._now(),
                )
                status = SchedulerRunStatus.COMPLETED
            except SchedulerLeaseError:
                status = SchedulerRunStatus.LEASE_LOST
            results.append(
                SchedulerRunResult(
                    job_id, spec.kind, status, context.claim.generation, None
                )
            )
        return tuple(results)
