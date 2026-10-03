"""Isolated durable outbox worker with injected clock and transport."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
import re
import uuid

from .durable_store import DurableStoreReadOnlyError, Phase3DurableStateStore, _canonical_utc
from .outbox import (
    DurableOutbox,
    OutboxEvent,
    OutboxStatus,
    StoredOutboxEvent,
    _SELECT,
    sanitize_outbox_error,
)
from .state_contracts import TenantIdentity


_WORKER_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{15,255}$")


class WorkerError(RuntimeError):
    """Base worker failure."""


class WorkerLeaseLostError(WorkerError):
    """A claim no longer belongs to this worker."""


class WorkerStepStatus(str, Enum):
    IDLE = "IDLE"
    DELIVERED = "DELIVERED"
    RETRY_SCHEDULED = "RETRY_SCHEDULED"
    DEAD_LETTERED = "DEAD_LETTERED"
    SHUTDOWN = "SHUTDOWN"


@dataclass(frozen=True)
class WorkerConfig:
    lease_seconds: int = 30
    max_attempts: int = 5
    initial_backoff_seconds: int = 5
    maximum_backoff_seconds: int = 300

    def __post_init__(self) -> None:
        for name in (
            "lease_seconds", "max_attempts", "initial_backoff_seconds",
            "maximum_backoff_seconds",
        ):
            value = getattr(self, name)
            if type(value) is not int or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        if self.initial_backoff_seconds > self.maximum_backoff_seconds:
            raise ValueError("initial backoff cannot exceed maximum backoff")


@dataclass(frozen=True)
class WorkerClaim:
    record: StoredOutboxEvent
    worker_id: str
    lease_token: str
    lease_expires_at: datetime
    execution_authorized: bool = field(default=False, init=False)


@dataclass(frozen=True)
class WorkerStepResult:
    status: WorkerStepStatus
    record: StoredOutboxEvent | None
    execution_authorized: bool = field(default=False, init=False)
    external_delivery_authorized: bool = field(default=False, init=False)


class OutboxWorker:
    """Processes one durable event at a time through an injected fake/safe transport."""

    execution_authorized = False
    production_mutation_authorized = False
    external_delivery_authorized = False

    def __init__(
        self,
        store: Phase3DurableStateStore,
        *,
        tenant_id: str,
        worker_id: str,
        clock: Callable[[], datetime],
        transport: Callable[[OutboxEvent], None],
        config: WorkerConfig = WorkerConfig(),
        token_factory: Callable[[], str] | None = None,
    ):
        if not isinstance(store, Phase3DurableStateStore):
            raise ValueError("store must be a Phase3DurableStateStore")
        tenant = TenantIdentity(tenant_id)
        if not isinstance(worker_id, str) or _WORKER_ID.fullmatch(worker_id) is None:
            raise ValueError("worker_id is invalid")
        if not callable(clock) or not callable(transport):
            raise ValueError("clock and transport must be callable")
        if not isinstance(config, WorkerConfig):
            raise ValueError("config must be a WorkerConfig")
        if token_factory is not None and not callable(token_factory):
            raise ValueError("token_factory must be callable")
        self.store = store
        self.tenant_id = tenant.tenant_id
        self.worker_id = worker_id
        self.clock = clock
        self.transport = transport
        self.config = config
        self.token_factory = token_factory or (lambda: uuid.uuid4().hex)
        self._shutdown_requested = False
        self.outbox = DurableOutbox(store)

    @property
    def shutdown_requested(self) -> bool:
        return self._shutdown_requested

    def request_shutdown(self) -> None:
        self._shutdown_requested = True

    def _now(self) -> datetime:
        value = self.clock()
        _canonical_utc(value, "worker clock")
        return value.astimezone(timezone.utc)

    def _token(self) -> str:
        value = self.token_factory()
        if not isinstance(value, str) or _TOKEN.fullmatch(value) is None:
            raise ValueError("token_factory returned an invalid lease token")
        return value

    def claim_one(self) -> WorkerClaim | None:
        if self._shutdown_requested:
            return None
        if self.store.read_only:
            raise DurableStoreReadOnlyError("phase3 store is read-only")
        now = self._now()
        now_text = _canonical_utc(now, "now")
        connection = self.store._require_open()
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """UPDATE phase3_outbox
                   SET status = ?, last_error = ?, updated_at = ?,
                       lease_owner = NULL, lease_token = NULL, lease_expires_at = NULL
                   WHERE tenant_id = ? AND status = ?
                     AND lease_expires_at <= ? AND attempt_count >= ?""",
                (
                    OutboxStatus.DEAD_LETTER.value,
                    sanitize_outbox_error("lease expired at maximum attempts"),
                    now_text, self.tenant_id, OutboxStatus.IN_PROGRESS.value,
                    now_text, self.config.max_attempts,
                ),
            )
            candidate = connection.execute(
                """SELECT event_id, status, lease_owner, lease_token, lease_expires_at
                   FROM phase3_outbox
                   WHERE tenant_id = ? AND attempt_count < ? AND (
                       (status = ? AND next_attempt_at <= ?)
                       OR (status = ? AND lease_expires_at <= ?)
                   )
                   ORDER BY CASE WHEN status = ? THEN next_attempt_at
                                 ELSE lease_expires_at END,
                            created_at, event_id
                   LIMIT 1""",
                (
                    self.tenant_id, self.config.max_attempts,
                    OutboxStatus.PENDING.value, now_text,
                    OutboxStatus.IN_PROGRESS.value, now_text,
                    OutboxStatus.PENDING.value,
                ),
            ).fetchone()
            if candidate is None:
                connection.execute("COMMIT")
                return None
            event_id, prior_status, prior_owner, prior_token, prior_expiry = candidate
            token = self._token()
            expires = now + timedelta(seconds=self.config.lease_seconds)
            expires_text = _canonical_utc(expires, "lease_expires_at")
            if prior_status == OutboxStatus.PENDING.value:
                ownership_predicate = "AND next_attempt_at <= ?"
                ownership_parameters = (now_text,)
            else:
                ownership_predicate = (
                    "AND lease_owner IS ? AND lease_token IS ? "
                    "AND lease_expires_at = ? AND lease_expires_at <= ?"
                )
                ownership_parameters = (
                    prior_owner, prior_token, prior_expiry, now_text,
                )
            changed = connection.execute(
                """UPDATE phase3_outbox
                   SET status = ?, attempt_count = attempt_count + 1,
                       updated_at = ?, lease_owner = ?, lease_token = ?,
                       lease_expires_at = ?, last_error = NULL
                   WHERE tenant_id = ? AND event_id = ? AND status = ? """
                + ownership_predicate,
                (
                    OutboxStatus.IN_PROGRESS.value, now_text, self.worker_id,
                    token, expires_text, self.tenant_id, event_id, prior_status,
                ) + ownership_parameters,
            )
            if changed.rowcount != 1:
                raise WorkerLeaseLostError("outbox claim changed concurrently")
            row = connection.execute(
                _SELECT + " WHERE tenant_id = ? AND event_id = ?",
                (self.tenant_id, event_id),
            ).fetchone()
            record = self.outbox._record(row)
            connection.execute("COMMIT")
            return WorkerClaim(record, self.worker_id, token, expires)
        except BaseException:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise

    def _finish(
        self,
        claim: WorkerClaim,
        *,
        delivered: bool,
        error: str | None = None,
    ) -> StoredOutboxEvent:
        if not isinstance(claim, WorkerClaim) or claim.worker_id != self.worker_id:
            raise WorkerLeaseLostError("claim does not belong to this worker")
        now = self._now()
        now_text = _canonical_utc(now, "now")
        connection = self.store._require_open()
        attempt_count = claim.record.attempt_count
        if delivered:
            status = OutboxStatus.DELIVERED
            next_attempt = claim.record.next_attempt_at
            last_error = None
            delivered_at = now_text
        else:
            last_error = sanitize_outbox_error(error or "transport failure")
            delivered_at = None
            if attempt_count >= self.config.max_attempts:
                status = OutboxStatus.DEAD_LETTER
                next_attempt = now
            else:
                status = OutboxStatus.PENDING
                delay = min(
                    self.config.initial_backoff_seconds * (2 ** (attempt_count - 1)),
                    self.config.maximum_backoff_seconds,
                )
                next_attempt = now + timedelta(seconds=delay)
        try:
            connection.execute("BEGIN IMMEDIATE")
            changed = connection.execute(
                """UPDATE phase3_outbox
                   SET status = ?, next_attempt_at = ?, last_error = ?,
                       updated_at = ?, delivered_at = ?, lease_owner = NULL,
                       lease_token = NULL, lease_expires_at = NULL
                   WHERE tenant_id = ? AND event_id = ? AND status = ?
                     AND lease_owner = ? AND lease_token = ?
                     AND lease_expires_at = ? AND attempt_count = ?
                     AND lease_expires_at > ?""",
                (
                    status.value, _canonical_utc(next_attempt, "next_attempt_at"),
                    last_error, now_text, delivered_at, self.tenant_id,
                    claim.record.event.event_id, OutboxStatus.IN_PROGRESS.value,
                    self.worker_id, claim.lease_token,
                    _canonical_utc(claim.lease_expires_at, "lease_expires_at"),
                    claim.record.attempt_count, now_text,
                ),
            )
            if changed.rowcount != 1:
                raise WorkerLeaseLostError("outbox lease is no longer owned")
            row = connection.execute(
                _SELECT + " WHERE tenant_id = ? AND event_id = ?",
                (self.tenant_id, claim.record.event.event_id),
            ).fetchone()
            record = self.outbox._record(row)
            connection.execute("COMMIT")
            return record
        except BaseException:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise

    def process_one(self) -> WorkerStepResult:
        if self._shutdown_requested:
            return WorkerStepResult(WorkerStepStatus.SHUTDOWN, None)
        claim = self.claim_one()
        if claim is None:
            return WorkerStepResult(WorkerStepStatus.IDLE, None)
        try:
            self.transport(claim.record.event)
        except Exception as exc:
            message = f"{type(exc).__name__}: {exc}"
            record = self._finish(claim, delivered=False, error=message)
            status = (
                WorkerStepStatus.DEAD_LETTERED
                if record.status is OutboxStatus.DEAD_LETTER
                else WorkerStepStatus.RETRY_SCHEDULED
            )
            return WorkerStepResult(status, record)
        record = self._finish(claim, delivered=True)
        return WorkerStepResult(WorkerStepStatus.DELIVERED, record)
