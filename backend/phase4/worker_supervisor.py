"""Deterministic worker supervision with injected processes and clocks."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
import re
from typing import Protocol
import uuid

from .secret_redaction import RedactedRecord, SecretRedactor


_WORKER_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_LEASE_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{15,255}$")


class SupervisorError(RuntimeError):
    pass


class SupervisorStateError(SupervisorError):
    pass


class SupervisorLeaseError(SupervisorError):
    pass


class WorkerState(str, Enum):
    STOPPED = "STOPPED"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    FAILED = "FAILED"


class RestartPolicy(str, Enum):
    NEVER = "NEVER"
    ON_FAILURE = "ON_FAILURE"
    ALWAYS = "ALWAYS"


@dataclass(frozen=True)
class WorkerSupervisorConfig:
    heartbeat_timeout_seconds: int = 30
    lease_seconds: int = 45
    graceful_shutdown_seconds: int = 15
    restart_policy: RestartPolicy = RestartPolicy.ON_FAILURE
    max_restart_count: int = 3

    def __post_init__(self) -> None:
        for name in (
            "heartbeat_timeout_seconds",
            "lease_seconds",
            "graceful_shutdown_seconds",
        ):
            if type(getattr(self, name)) is not int or getattr(self, name) < 1:
                raise ValueError(f"{name} must be a positive integer")
        if self.heartbeat_timeout_seconds > self.lease_seconds:
            raise ValueError("heartbeat timeout cannot exceed lease duration")
        if not isinstance(self.restart_policy, RestartPolicy):
            raise ValueError("restart_policy must be a RestartPolicy")
        if type(self.max_restart_count) is not int or self.max_restart_count < 0:
            raise ValueError("max_restart_count must be a nonnegative integer")


@dataclass(frozen=True)
class WorkerLease:
    worker_id: str
    generation: int
    token: str = field(repr=False)
    acquired_at: datetime
    expires_at: datetime
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.worker_id, str) or _WORKER_ID.fullmatch(self.worker_id) is None:
            raise ValueError("worker_id is invalid")
        if type(self.generation) is not int or self.generation < 1:
            raise ValueError("generation must be positive")
        if not isinstance(self.token, str) or _LEASE_TOKEN.fullmatch(self.token) is None:
            raise ValueError("lease token is invalid")
        for name in ("acquired_at", "expires_at"):
            value = getattr(self, name)
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{name} must be timezone-aware")
        if self.expires_at <= self.acquired_at:
            raise ValueError("lease expiration must follow acquisition")


@dataclass(frozen=True)
class WorkerSupervisorStatus:
    worker_id: str
    state: WorkerState
    generation: int
    restart_count: int
    lease: WorkerLease | None
    last_heartbeat_at: datetime | None
    shutdown_deadline: datetime | None
    last_failure: RedactedRecord | None
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)
    external_delivery_authorized: bool = field(default=False, init=False)


class SupervisedProcess(Protocol):
    def start(self) -> None: ...

    def request_stop(self) -> None: ...

    def force_stop(self) -> None: ...

    def is_running(self) -> bool: ...

    def exit_code(self) -> int | None: ...


ProcessFactory = Callable[[str, int], SupervisedProcess]


class WorkerSupervisor:
    """State machine only; no thread, subprocess, service, or scheduler is created."""

    execution_authorized = False
    production_mutation_authorized = False
    external_delivery_authorized = False

    def __init__(
        self,
        *,
        worker_id: str,
        process_factory: ProcessFactory,
        clock: Callable[[], datetime],
        config: WorkerSupervisorConfig = WorkerSupervisorConfig(),
        token_factory: Callable[[], str] | None = None,
        redactor: SecretRedactor | None = None,
    ):
        if not isinstance(worker_id, str) or _WORKER_ID.fullmatch(worker_id) is None:
            raise ValueError("worker_id is invalid")
        if not callable(process_factory) or not callable(clock):
            raise ValueError("process_factory and clock must be callable")
        if not isinstance(config, WorkerSupervisorConfig):
            raise ValueError("config must be a WorkerSupervisorConfig")
        if token_factory is not None and not callable(token_factory):
            raise ValueError("token_factory must be callable")
        if redactor is not None and not isinstance(redactor, SecretRedactor):
            raise ValueError("redactor must be a SecretRedactor")
        self.worker_id = worker_id
        self.process_factory = process_factory
        self.clock = clock
        self.config = config
        self.token_factory = token_factory or (lambda: uuid.uuid4().hex)
        self.redactor = redactor or SecretRedactor()
        self._state = WorkerState.STOPPED
        self._generation = 0
        self._restart_count = 0
        self._lease: WorkerLease | None = None
        self._last_heartbeat_at: datetime | None = None
        self._heartbeat_deadline: datetime | None = None
        self._shutdown_deadline: datetime | None = None
        self._last_failure: RedactedRecord | None = None
        self._process: SupervisedProcess | None = None
        self._desired_running = False
        self._restart_after_stop = False

    def _now(self) -> datetime:
        value = self.clock()
        if (
            not isinstance(value, datetime)
            or value.tzinfo is None
            or value.utcoffset() is None
        ):
            raise SupervisorError("supervisor clock must be timezone-aware")
        return value.astimezone(timezone.utc)

    def _token(self) -> str:
        value = self.token_factory()
        if not isinstance(value, str) or _LEASE_TOKEN.fullmatch(value) is None:
            raise SupervisorError("token factory returned an invalid lease token")
        return value

    def _failure(self, message: str, error: BaseException | None = None) -> None:
        failure = error or RuntimeError(message)
        self._last_failure = self.redactor.worker_failure(
            self.worker_id,
            failure,
            {"reason": message, "generation": self._generation},
        )

    def _new_lease(self, now: datetime) -> WorkerLease:
        return WorkerLease(
            worker_id=self.worker_id,
            generation=self._generation,
            token=self._token(),
            acquired_at=now,
            expires_at=now + timedelta(seconds=self.config.lease_seconds),
        )

    def _start_process(self, now: datetime, *, restarting: bool) -> None:
        next_generation = self._generation + 1
        try:
            process = self.process_factory(self.worker_id, next_generation)
            if process is None:
                raise RuntimeError("process factory returned no process")
            process.start()
            if not process.is_running():
                raise RuntimeError("process did not enter running state")
        except Exception as exc:
            self._generation = next_generation
            self._process = None
            self._lease = None
            self._state = WorkerState.FAILED
            self._desired_running = False
            self._failure("worker start failed", exc)
            return
        self._generation = next_generation
        if restarting:
            self._restart_count += 1
        self._process = process
        self._state = WorkerState.RUNNING
        self._lease = self._new_lease(now)
        self._last_heartbeat_at = now
        self._heartbeat_deadline = now + timedelta(
            seconds=self.config.heartbeat_timeout_seconds
        )
        self._shutdown_deadline = None
        self._restart_after_stop = False

    def start(self) -> WorkerSupervisorStatus:
        if self._state is not WorkerState.STOPPED:
            raise SupervisorStateError("worker can start only from STOPPED")
        self._desired_running = True
        self._restart_count = 0
        self._last_failure = None
        self._start_process(self._now(), restarting=False)
        return self.status()

    def heartbeat(self, lease_token: str) -> WorkerSupervisorStatus:
        now = self._now()
        if self._state is not WorkerState.RUNNING or self._lease is None:
            raise SupervisorLeaseError("worker has no active lease")
        if lease_token != self._lease.token:
            raise SupervisorLeaseError("worker lease token does not match")
        if now >= self._lease.expires_at:
            raise SupervisorLeaseError("worker lease has expired")
        if self._process is None or not self._process.is_running():
            raise SupervisorLeaseError("worker process is not running")
        self._lease = WorkerLease(
            worker_id=self.worker_id,
            generation=self._generation,
            token=lease_token,
            acquired_at=self._lease.acquired_at,
            expires_at=now + timedelta(seconds=self.config.lease_seconds),
        )
        self._last_heartbeat_at = now
        self._heartbeat_deadline = now + timedelta(
            seconds=self.config.heartbeat_timeout_seconds
        )
        return self.status()

    def stop(self) -> WorkerSupervisorStatus:
        self._desired_running = False
        self._restart_after_stop = False
        if self._state is WorkerState.STOPPED:
            return self.status()
        if self._state is WorkerState.FAILED:
            self._state = WorkerState.STOPPED
            self._lease = None
            self._process = None
            return self.status()
        if self._state is WorkerState.RUNNING:
            self._begin_stop(self._now(), restart_after=False)
        return self.poll()

    def _begin_stop(self, now: datetime, *, restart_after: bool) -> None:
        self._state = WorkerState.STOPPING
        self._lease = None
        self._heartbeat_deadline = None
        self._restart_after_stop = restart_after
        self._shutdown_deadline = now + timedelta(
            seconds=self.config.graceful_shutdown_seconds
        )
        try:
            assert self._process is not None
            self._process.request_stop()
        except Exception as exc:
            self._failure("graceful shutdown request failed", exc)

    def _restart_allowed(self, *, failed: bool) -> bool:
        if not self._desired_running:
            return False
        if self._restart_count >= self.config.max_restart_count:
            return False
        if self.config.restart_policy is RestartPolicy.NEVER:
            return False
        if self.config.restart_policy is RestartPolicy.ON_FAILURE:
            return failed
        return True

    def _complete_exit(self, now: datetime, *, failed: bool) -> None:
        should_restart = self._restart_allowed(failed=failed)
        self._process = None
        self._lease = None
        self._heartbeat_deadline = None
        self._shutdown_deadline = None
        self._restart_after_stop = False
        if should_restart:
            self._start_process(now, restarting=True)
        elif self._desired_running:
            self._desired_running = False
            self._state = WorkerState.FAILED
        else:
            self._state = WorkerState.STOPPED

    def poll(self) -> WorkerSupervisorStatus:
        now = self._now()
        if self._state is WorkerState.RUNNING:
            assert self._process is not None and self._lease is not None
            if not self._process.is_running():
                exit_code = self._process.exit_code()
                failed = exit_code is None or exit_code != 0
                self._failure(
                    "worker process crashed" if failed else "worker process exited"
                )
                self._complete_exit(now, failed=failed)
            elif (
                self._heartbeat_deadline is not None
                and now >= self._heartbeat_deadline
            ):
                self._failure("worker heartbeat timed out")
                self._begin_stop(now, restart_after=True)
            elif now >= self._lease.expires_at:
                self._failure("worker lease expired")
                self._begin_stop(now, restart_after=True)

        if self._state is WorkerState.STOPPING:
            assert self._process is not None
            if not self._process.is_running():
                restart_after = self._restart_after_stop
                self._complete_exit(now, failed=restart_after)
            elif self._shutdown_deadline is not None and now >= self._shutdown_deadline:
                try:
                    self._process.force_stop()
                except Exception as exc:
                    self._failure("forced shutdown failed", exc)
                if self._process.is_running():
                    self._desired_running = False
                    self._restart_after_stop = False
                    self._state = WorkerState.FAILED
                    self._lease = None
                    self._heartbeat_deadline = None
                else:
                    restart_after = self._restart_after_stop
                    self._complete_exit(now, failed=restart_after)
        return self.status()

    def status(self) -> WorkerSupervisorStatus:
        return WorkerSupervisorStatus(
            worker_id=self.worker_id,
            state=self._state,
            generation=self._generation,
            restart_count=self._restart_count,
            lease=self._lease,
            last_heartbeat_at=self._last_heartbeat_at,
            shutdown_deadline=self._shutdown_deadline,
            last_failure=self._last_failure,
        )
