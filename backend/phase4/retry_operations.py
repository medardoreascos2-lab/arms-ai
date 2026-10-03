"""Authorized durable dead-letter inspection, quarantine, and retry operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import re

from backend.phase3.durable_store import (
    DurableStoreReadOnlyError,
    Phase3DurableStateStore,
    _canonical_utc,
)
from backend.phase3.outbox import (
    DurableOutbox,
    OutboxStatus,
    StoredOutboxEvent,
    _SELECT,
)
from backend.phase3.state_contracts import TenantIdentity

from .secret_redaction import redact_text


_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
_QUARANTINE_PREFIX = "[QUARANTINED] "
_MAX_EVIDENCE = 512


class RetryOperationError(RuntimeError):
    pass


@dataclass(frozen=True)
class RetryOperationsPolicy:
    maximum_attempts: int
    retry_delay_seconds: int = 0

    def __post_init__(self) -> None:
        if type(self.maximum_attempts) is not int or self.maximum_attempts < 1:
            raise ValueError("maximum_attempts must be a positive integer")
        if type(self.retry_delay_seconds) is not int or self.retry_delay_seconds < 0:
            raise ValueError("retry_delay_seconds must be a nonnegative integer")


@dataclass(frozen=True)
class RetryAuthorizationDecision:
    accepted: bool
    principal_id: str
    request_id: str
    reason: str
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if type(self.accepted) is not bool:
            raise ValueError("accepted must be boolean")
        for name in ("principal_id", "request_id"):
            if not isinstance(getattr(self, name), str) or _ID.fullmatch(
                getattr(self, name)
            ) is None:
                raise ValueError(f"{name} is invalid")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("reason must be nonempty")


@dataclass(frozen=True)
class DeadLetterInspection:
    tenant_id: str
    event_id: str
    event_kind: str
    attempt_count: int
    sanitized_error_evidence: str
    updated_at: datetime
    quarantined: bool
    retry_eligible: bool
    blocking_reasons: tuple[str, ...]
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)
    external_delivery_authorized: bool = field(default=False, init=False)


@dataclass(frozen=True)
class RetryOperationResult:
    accepted: bool
    changed: bool
    operation: str
    event_id: str
    record: StoredOutboxEvent | None
    blocking_reasons: tuple[str, ...]
    sanitized_evidence: str | None
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)
    external_delivery_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if type(self.accepted) is not bool or type(self.changed) is not bool:
            raise ValueError("operation result flags must be booleans")
        if self.changed and not self.accepted:
            raise ValueError("rejected retry operations cannot report changes")
        if self.blocking_reasons != tuple(sorted(set(self.blocking_reasons))):
            raise ValueError("blocking_reasons must be sorted and unique")
        if self.accepted == bool(self.blocking_reasons):
            raise ValueError("accepted results and blocking reasons are inconsistent")


def _evidence(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("operation evidence must be nonempty text")
    return redact_text(value)[:_MAX_EVIDENCE]


class DurableRetryOperations:
    """Mutates only existing Phase 3 outbox state after explicit approval."""

    execution_authorized = False
    production_mutation_authorized = False
    external_delivery_authorized = False

    def __init__(
        self,
        store: Phase3DurableStateStore,
        policy: RetryOperationsPolicy,
    ):
        if not isinstance(store, Phase3DurableStateStore):
            raise ValueError("store must be a Phase3DurableStateStore")
        if not isinstance(policy, RetryOperationsPolicy):
            raise ValueError("policy must be a RetryOperationsPolicy")
        self.store = store
        self.policy = policy
        self.outbox = DurableOutbox(store)

    def _inspection(self, record: StoredOutboxEvent) -> DeadLetterInspection:
        if record.status is not OutboxStatus.DEAD_LETTER:
            raise RetryOperationError("record is not dead-lettered")
        evidence = _evidence(record.last_error or "dead-letter error unavailable")
        quarantined = evidence.startswith(_QUARANTINE_PREFIX)
        reasons = []
        if quarantined:
            reasons.append("QUARANTINED")
        if record.attempt_count >= self.policy.maximum_attempts:
            reasons.append("MAX_ATTEMPTS_REACHED")
        return DeadLetterInspection(
            tenant_id=record.event.tenant.tenant_id,
            event_id=record.event.event_id,
            event_kind=record.event.event_kind,
            attempt_count=record.attempt_count,
            sanitized_error_evidence=evidence,
            updated_at=record.updated_at,
            quarantined=quarantined,
            retry_eligible=not reasons,
            blocking_reasons=tuple(sorted(reasons)),
        )

    def inspect_dead_letters(
        self,
        *,
        tenant_id: str,
        limit: int = 100,
    ) -> tuple[DeadLetterInspection, ...]:
        tenant = TenantIdentity(tenant_id)
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        rows = self.store._require_open().execute(
            _SELECT
            + " WHERE tenant_id = ? AND status = ? "
            "ORDER BY updated_at, event_id LIMIT ?",
            (tenant.tenant_id, OutboxStatus.DEAD_LETTER.value, limit),
        ).fetchall()
        return tuple(self._inspection(self.outbox._record(row)) for row in rows)

    def quarantine(
        self,
        *,
        tenant_id: str,
        event_id: str,
        reason: str,
        now: datetime,
        authorization: RetryAuthorizationDecision,
    ) -> RetryOperationResult:
        evidence = _evidence(reason)
        return self._mutate(
            operation="QUARANTINE",
            tenant_id=tenant_id,
            event_id=event_id,
            now=now,
            authorization=authorization,
            quarantine_evidence=evidence,
            release_quarantine=False,
        )

    def schedule_retry(
        self,
        *,
        tenant_id: str,
        event_id: str,
        reason: str,
        now: datetime,
        authorization: RetryAuthorizationDecision,
        release_quarantine: bool = False,
    ) -> RetryOperationResult:
        if type(release_quarantine) is not bool:
            raise ValueError("release_quarantine must be boolean")
        evidence = _evidence(reason)
        return self._mutate(
            operation="SCHEDULE_RETRY",
            tenant_id=tenant_id,
            event_id=event_id,
            now=now,
            authorization=authorization,
            quarantine_evidence=evidence,
            release_quarantine=release_quarantine,
        )

    def _blocked(
        self,
        operation: str,
        event_id: str,
        *reasons: str,
    ) -> RetryOperationResult:
        return RetryOperationResult(
            accepted=False,
            changed=False,
            operation=operation,
            event_id=event_id,
            record=None,
            blocking_reasons=tuple(sorted(set(reasons))),
            sanitized_evidence=None,
        )

    def _mutate(
        self,
        *,
        operation: str,
        tenant_id: str,
        event_id: str,
        now: datetime,
        authorization: RetryAuthorizationDecision,
        quarantine_evidence: str,
        release_quarantine: bool,
    ) -> RetryOperationResult:
        tenant = TenantIdentity(tenant_id)
        if not isinstance(event_id, str) or _ID.fullmatch(event_id) is None:
            raise ValueError("event_id is invalid")
        if not isinstance(authorization, RetryAuthorizationDecision):
            raise ValueError("authorization must be a RetryAuthorizationDecision")
        moment = now.astimezone(timezone.utc) if isinstance(now, datetime) else now
        now_text = _canonical_utc(moment, "now")
        if not authorization.accepted:
            return self._blocked(operation, event_id, "UNAUTHORIZED")
        if self.store.read_only:
            raise DurableStoreReadOnlyError("phase3 store is read-only")

        connection = self.store._require_open()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                _SELECT + " WHERE tenant_id = ? AND event_id = ?",
                (tenant.tenant_id, event_id),
            ).fetchone()
            if row is None:
                connection.execute("COMMIT")
                return self._blocked(operation, event_id, "NOT_FOUND")
            record = self.outbox._record(row)
            if record.status is not OutboxStatus.DEAD_LETTER:
                connection.execute("COMMIT")
                return self._blocked(operation, event_id, "NOT_DEAD_LETTER")
            if moment < record.updated_at:
                connection.execute("COMMIT")
                return self._blocked(operation, event_id, "TIME_REGRESSION")
            inspection = self._inspection(record)

            if operation == "QUARANTINE":
                if inspection.quarantined:
                    connection.execute("COMMIT")
                    return self._blocked(operation, event_id, "ALREADY_QUARANTINED")
                stored_evidence = (
                    f"{_QUARANTINE_PREFIX}{authorization.principal_id} "
                    f"{authorization.request_id}: {quarantine_evidence}"
                )[:_MAX_EVIDENCE]
                next_attempt = record.next_attempt_at
                new_status = OutboxStatus.DEAD_LETTER
            else:
                reasons = [
                    reason
                    for reason in inspection.blocking_reasons
                    if reason != "QUARANTINED" or not release_quarantine
                ]
                if reasons:
                    connection.execute("COMMIT")
                    return self._blocked(operation, event_id, *reasons)
                stored_evidence = (
                    f"manual retry scheduled by {authorization.principal_id} "
                    f"{authorization.request_id}: {quarantine_evidence}"
                )[:_MAX_EVIDENCE]
                next_attempt = moment + timedelta(
                    seconds=self.policy.retry_delay_seconds
                )
                new_status = OutboxStatus.PENDING

            changed = connection.execute(
                """UPDATE phase3_outbox
                   SET status = ?, next_attempt_at = ?, last_error = ?,
                       updated_at = ?, lease_owner = NULL, lease_token = NULL,
                       lease_expires_at = NULL, delivered_at = NULL
                   WHERE tenant_id = ? AND event_id = ? AND status = ?
                     AND attempt_count = ? AND updated_at = ?""",
                (
                    new_status.value,
                    _canonical_utc(next_attempt, "next_attempt_at"),
                    stored_evidence,
                    now_text,
                    tenant.tenant_id,
                    event_id,
                    OutboxStatus.DEAD_LETTER.value,
                    record.attempt_count,
                    _canonical_utc(record.updated_at, "updated_at"),
                ),
            )
            if changed.rowcount != 1:
                raise RetryOperationError("dead-letter state changed concurrently")
            updated_row = connection.execute(
                _SELECT + " WHERE tenant_id = ? AND event_id = ?",
                (tenant.tenant_id, event_id),
            ).fetchone()
            updated = self.outbox._record(updated_row)
            connection.execute("COMMIT")
        except BaseException:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        return RetryOperationResult(
            accepted=True,
            changed=True,
            operation=operation,
            event_id=event_id,
            record=updated,
            blocking_reasons=(),
            sanitized_evidence=stored_evidence,
        )
