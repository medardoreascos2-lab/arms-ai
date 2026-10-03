"""Crash/restart recovery for the isolated Phase 3 read-only runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from .audit_log import AuditEventKind, AuditLog
from .durable_store import Phase3DurableStateStore
from .evaluation_repository import EvaluationRepository, StoredEvaluation
from .outbox import DurableOutbox, StoredOutboxEvent
from .runtime import (
    Phase3ReadOnlyRuntime,
    ReadOnlyRuntimeRequest,
    ReadOnlyRuntimeResult,
    RuntimeStatus,
    _notification_events,
    _notification_outbox_event,
    _same_snapshot,
)
from .snapshot_repository import AccountSnapshotRepository, StoredAccountSnapshot


class RuntimeRecoveryError(RuntimeError):
    """Recovery could not prove that all expected durable effects exist."""


class RecoveryStage(str, Enum):
    EMPTY = "EMPTY"
    SNAPSHOT_COMMITTED = "SNAPSHOT_COMMITTED"
    EVALUATION_COMMITTED = "EVALUATION_COMMITTED"
    OUTBOX_COMMITTED = "OUTBOX_COMMITTED"
    AUDIT_INCOMPLETE = "AUDIT_INCOMPLETE"
    COMPLETE = "COMPLETE"


class RecoveryStatus(str, Enum):
    RECOVERED = "RECOVERED"
    ALREADY_COMPLETE = "ALREADY_COMPLETE"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class RuntimeRecoveryState:
    tenant_id: str
    ingestion_id: str
    stage: RecoveryStage
    snapshot_present: bool
    evaluation_present: bool
    expected_outbox_event_ids: tuple[str, ...]
    persisted_outbox_event_ids: tuple[str, ...]
    audit_kinds: tuple[AuditEventKind, ...]
    incomplete_reasons: tuple[str, ...]
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)
    source_account_mutation_authorized: bool = field(default=False, init=False)
    external_delivery_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.stage, RecoveryStage):
            raise ValueError("stage must be a RecoveryStage")
        for name in (
            "expected_outbox_event_ids", "persisted_outbox_event_ids",
            "audit_kinds", "incomplete_reasons",
        ):
            if not isinstance(getattr(self, name), tuple):
                raise ValueError(f"{name} must be an immutable tuple")
        if self.expected_outbox_event_ids != tuple(sorted(set(
            self.expected_outbox_event_ids
        ))):
            raise ValueError("expected outbox event IDs must be sorted and unique")
        if self.persisted_outbox_event_ids != tuple(sorted(set(
            self.persisted_outbox_event_ids
        ))):
            raise ValueError("persisted outbox event IDs must be sorted and unique")
        if self.incomplete_reasons != tuple(sorted(set(self.incomplete_reasons))):
            raise ValueError("incomplete reasons must be sorted and unique")
        if self.stage is RecoveryStage.COMPLETE and self.incomplete_reasons:
            raise ValueError("complete recovery state cannot have incomplete reasons")

    @property
    def complete(self) -> bool:
        return self.stage is RecoveryStage.COMPLETE


@dataclass(frozen=True)
class RuntimeRecoveryResult:
    status: RecoveryStatus
    before: RuntimeRecoveryState
    runtime: ReadOnlyRuntimeResult
    after: RuntimeRecoveryState
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)
    source_account_mutation_authorized: bool = field(default=False, init=False)
    external_delivery_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.status, RecoveryStatus):
            raise ValueError("status must be a RecoveryStatus")
        if self.status is RecoveryStatus.BLOCKED:
            if self.runtime.status is RuntimeStatus.COMPLETED:
                raise ValueError("blocked recovery cannot contain a completed runtime")
        elif not self.after.complete or self.runtime.status is not RuntimeStatus.COMPLETED:
            raise ValueError("successful recovery requires complete durable state")


class Phase3RuntimeRecovery:
    """Inspects and idempotently completes a previously interrupted runtime request."""

    execution_authorized = False
    production_mutation_authorized = False
    source_account_mutation_authorized = False
    external_delivery_authorized = False

    _BASE_AUDITS = (
        AuditEventKind.SNAPSHOT_RECEIVED,
        AuditEventKind.PROFILE_RESOLVED,
        AuditEventKind.EVALUATION_COMPLETED,
    )

    def __init__(self, runtime: Phase3ReadOnlyRuntime):
        if not isinstance(runtime, Phase3ReadOnlyRuntime):
            raise ValueError("runtime must be a Phase3ReadOnlyRuntime")
        self.runtime = runtime
        self.store: Phase3DurableStateStore = runtime.store
        self.snapshots = AccountSnapshotRepository(self.store)
        self.evaluations = EvaluationRepository(self.store)
        self.outbox = DurableOutbox(self.store)
        self.audit = AuditLog(self.store)

    @staticmethod
    def _evaluation_id(ingestion_id: str) -> str:
        return f"evaluation:{ingestion_id}"

    def _snapshot(self, request: ReadOnlyRuntimeRequest) -> StoredAccountSnapshot | None:
        return self.snapshots.by_id(
            tenant_id=request.ingestion.tenant.tenant_id,
            snapshot_id=request.ingestion.ingestion_id,
        )

    def _evaluation(
        self, request: ReadOnlyRuntimeRequest,
    ) -> StoredEvaluation | None:
        return self.evaluations.by_id(
            tenant_id=request.ingestion.tenant.tenant_id,
            evaluation_id=self._evaluation_id(request.ingestion.ingestion_id),
        )

    def _outbox_state(
        self,
        request: ReadOnlyRuntimeRequest,
        snapshot: StoredAccountSnapshot,
        evaluation: StoredEvaluation,
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        evaluation_id = evaluation.evaluation_id
        notifications = _notification_events(
            snapshot=snapshot.snapshot,
            evaluation=evaluation.evaluation,
            evaluation_id=evaluation_id,
            occurred_at=request.ingestion.received_at,
            payout_evaluated=request.payout_request is not None,
        )
        events = tuple(
            _notification_outbox_event(
                tenant=request.ingestion.tenant,
                snapshot=snapshot.snapshot,
                evaluation=evaluation.evaluation,
                evaluation_id=evaluation_id,
                notification=item,
                occurred_at=request.ingestion.received_at,
            )
            for item in notifications
        )
        records: tuple[StoredOutboxEvent | None, ...] = tuple(
            self.outbox.by_id(
                tenant_id=request.ingestion.tenant.tenant_id,
                event_id=item.event_id,
            )
            for item in events
        )
        return (
            tuple(sorted(item.event_id for item in events)),
            tuple(sorted(
                item.event.event_id for item in records if item is not None
            )),
        )

    def inspect(self, request: ReadOnlyRuntimeRequest) -> RuntimeRecoveryState:
        if not isinstance(request, ReadOnlyRuntimeRequest):
            raise ValueError("request must be a ReadOnlyRuntimeRequest")
        tenant_id = request.ingestion.tenant.tenant_id
        ingestion_id = request.ingestion.ingestion_id
        snapshot = self._snapshot(request)
        if snapshot is not None and not _same_snapshot(snapshot, request.ingestion):
            raise RuntimeRecoveryError(
                "stored snapshot identity conflicts with recovery request"
            )
        evaluation = self._evaluation(request) if snapshot is not None else None
        expected_ids: tuple[str, ...] = ()
        persisted_ids: tuple[str, ...] = ()
        reasons: list[str] = []

        if snapshot is None:
            reasons.append("SNAPSHOT_MISSING")
        elif evaluation is None:
            reasons.append("EVALUATION_MISSING")
        else:
            expected_ids, persisted_ids = self._outbox_state(
                request, snapshot, evaluation
            )
            if persisted_ids != expected_ids:
                reasons.append("OUTBOX_INCOMPLETE")

        audits = self.audit.for_correlation(
            tenant_id=tenant_id,
            correlation_id=ingestion_id,
        )
        audit_kinds = tuple(item.event.kind for item in audits)
        if snapshot is not None and evaluation is not None:
            for required in self._BASE_AUDITS:
                if audit_kinds.count(required) != 1:
                    reasons.append(f"AUDIT_{required.value}_INCOMPLETE")
            if audit_kinds.count(AuditEventKind.NOTIFICATION_QUEUED) != len(expected_ids):
                reasons.append("AUDIT_NOTIFICATION_QUEUED_INCOMPLETE")

        if snapshot is None:
            stage = RecoveryStage.EMPTY
        elif evaluation is None:
            stage = RecoveryStage.SNAPSHOT_COMMITTED
        elif persisted_ids != expected_ids:
            stage = RecoveryStage.EVALUATION_COMMITTED
        elif not audit_kinds:
            stage = RecoveryStage.OUTBOX_COMMITTED
        elif reasons:
            stage = RecoveryStage.AUDIT_INCOMPLETE
        else:
            stage = RecoveryStage.COMPLETE
        return RuntimeRecoveryState(
            tenant_id=tenant_id,
            ingestion_id=ingestion_id,
            stage=stage,
            snapshot_present=snapshot is not None,
            evaluation_present=evaluation is not None,
            expected_outbox_event_ids=expected_ids,
            persisted_outbox_event_ids=persisted_ids,
            audit_kinds=audit_kinds,
            incomplete_reasons=tuple(sorted(set(reasons))),
        )

    def recover(
        self,
        request: ReadOnlyRuntimeRequest,
        *,
        now: datetime,
    ) -> RuntimeRecoveryResult:
        before = self.inspect(request)
        runtime_result = self.runtime.process(request, now=now)
        after = self.inspect(request)
        if runtime_result.status is not RuntimeStatus.COMPLETED:
            return RuntimeRecoveryResult(
                RecoveryStatus.BLOCKED, before, runtime_result, after,
            )
        if not after.complete:
            raise RuntimeRecoveryError(
                "runtime retry returned completed without complete durable state: "
                + ",".join(after.incomplete_reasons)
            )
        if runtime_result.snapshot is None or runtime_result.evaluation is None:
            raise RuntimeRecoveryError("completed runtime omitted durable evidence")
        if (
            runtime_result.snapshot.record.snapshot_id != request.ingestion.ingestion_id
            or runtime_result.evaluation.record.evaluation_id
            != self._evaluation_id(request.ingestion.ingestion_id)
            or tuple(sorted(item.record.event.event_id for item in runtime_result.outbox))
            != after.expected_outbox_event_ids
        ):
            raise RuntimeRecoveryError("recovered identities do not match durable state")
        status = (
            RecoveryStatus.ALREADY_COMPLETE
            if before.complete else RecoveryStatus.RECOVERED
        )
        return RuntimeRecoveryResult(status, before, runtime_result, after)
