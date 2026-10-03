"""Read-only source-account composition for the isolated Phase 3 runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from backend.analytics.prop_firm_trade_journal_analytics import (
    ClosedJournalTrade,
    TradeJournalAnalyticsReport,
    analyze_trade_journal,
)
from backend.notifications import (
    NotificationEvent,
    NotificationEventType,
    NotificationIdentity,
    create_notification_event,
)
from backend.prop_firms import (
    AccountEvaluationV2,
    MultiAccountDiagnosticSummary,
    PayoutRequest,
    ProfileRegistryError,
    PropFirmAccountSnapshot,
    PropFirmPortfolioAnalytics,
    PropFirmProfileRegistry,
    SourceStatus,
    analyze_prop_firm_portfolio,
    evaluate_account_v2,
    evaluate_accounts,
    evaluate_payout_v2,
)

from .audit_log import AuditEvent, AuditEventKind, AuditLog, StoredAuditEvent
from .durable_store import Phase3DurableStateStore
from .evaluation_repository import EvaluationAppendResult, EvaluationRepository
from .outbox import DurableOutbox, OutboxEnqueueResult, OutboxEvent
from .read_authorization import (
    AuthorizationDecision,
    AuthorizationPrincipal,
    ReadAction,
    ReadAuthorizationBoundary,
    ReadRequest,
)
from .snapshot_ingestion import (
    IngestionCode,
    SnapshotCursor,
    SnapshotFreshnessPolicy,
    SnapshotIngestionDecision,
    SnapshotIngestionRequest,
    evaluate_snapshot_ingestion,
)
from .snapshot_repository import (
    AccountSnapshotRepository,
    SnapshotAppendResult,
    SnapshotStreamIdentity,
    StoredAccountSnapshot,
)
from .state_contracts import DurableStatePayload, UserIdentity as StateUserIdentity


class RuntimeCompositionError(RuntimeError):
    """The composed read-only flow produced internally inconsistent evidence."""


class RuntimeStatus(str, Enum):
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    DENIED = "DENIED"


@dataclass(frozen=True)
class ReadOnlyRuntimeRequest:
    ingestion: SnapshotIngestionRequest
    principal: AuthorizationPrincipal | None
    freshness: SnapshotFreshnessPolicy
    journal_trades: tuple[ClosedJournalTrade, ...] = ()
    payout_request: PayoutRequest | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.ingestion, SnapshotIngestionRequest):
            raise ValueError("ingestion must be a SnapshotIngestionRequest")
        if self.principal is not None and not isinstance(
            self.principal, AuthorizationPrincipal
        ):
            raise ValueError("principal must be an AuthorizationPrincipal or None")
        if not isinstance(self.freshness, SnapshotFreshnessPolicy):
            raise ValueError("freshness must be a SnapshotFreshnessPolicy")
        if not isinstance(self.journal_trades, tuple) or any(
            not isinstance(item, ClosedJournalTrade) for item in self.journal_trades
        ):
            raise ValueError("journal_trades must be an immutable tuple")
        if self.payout_request is not None and not isinstance(
            self.payout_request, PayoutRequest
        ):
            raise ValueError("payout_request must be a PayoutRequest or None")
        account_id = self.ingestion.account.account_id
        firm_id = self.ingestion.snapshot.firm_id
        if any(item.account_id != account_id for item in self.journal_trades):
            raise ValueError("journal trades must belong to the ingested account")
        if any(item.firm_id != firm_id for item in self.journal_trades):
            raise ValueError("journal trades must belong to the ingested firm")
        trade_ids = tuple(item.trade_id for item in self.journal_trades)
        if len(trade_ids) != len(set(trade_ids)):
            raise ValueError("journal trade IDs must be unique")


@dataclass(frozen=True)
class ReadOnlyRuntimeResult:
    status: RuntimeStatus
    ingestion_decision: SnapshotIngestionDecision
    authorization: tuple[AuthorizationDecision, ...]
    snapshot: SnapshotAppendResult | None
    evaluation: EvaluationAppendResult | None
    diagnostics: MultiAccountDiagnosticSummary | None
    portfolio: PropFirmPortfolioAnalytics | None
    journal: TradeJournalAnalyticsReport | None
    notifications: tuple[NotificationEvent, ...]
    outbox: tuple[OutboxEnqueueResult, ...]
    audit: tuple[StoredAuditEvent, ...]
    blocking_reasons: tuple[str, ...]
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)
    source_account_mutation_authorized: bool = field(default=False, init=False)
    external_delivery_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.status, RuntimeStatus):
            raise ValueError("status must be a RuntimeStatus")
        for name in ("authorization", "notifications", "outbox", "audit"):
            if not isinstance(getattr(self, name), tuple):
                raise ValueError(f"{name} must be an immutable tuple")
        if tuple(sorted(set(self.blocking_reasons))) != self.blocking_reasons:
            raise ValueError("blocking_reasons must be sorted and unique")
        operational = (
            self.snapshot, self.evaluation, self.diagnostics,
            self.portfolio, self.journal,
        )
        if self.status is RuntimeStatus.COMPLETED:
            if any(value is None for value in operational):
                raise ValueError("completed runtime results require complete evidence")
        elif any(value is not None for value in operational) or self.outbox:
            raise ValueError("blocked runtime results cannot carry operational effects")


def _aware(value: datetime, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _stream(request: SnapshotIngestionRequest) -> SnapshotStreamIdentity:
    return SnapshotStreamIdentity(
        tenant_id=request.tenant.tenant_id,
        account_id=request.account.account_id,
        source_id=request.source.identity.source_id,
        source_version=request.source.identity.source_version,
        source_simulated=request.source.identity.simulated,
        profile_config_hash=request.profile.config_hash,
        currency=request.currency,
    )


def _cursor(record: StoredAccountSnapshot) -> SnapshotCursor:
    return SnapshotCursor(
        tenant_id=record.stream.tenant_id,
        account_id=record.stream.account_id,
        source_id=record.stream.source_id,
        source_version=record.stream.source_version,
        profile_config_hash=record.stream.profile_config_hash,
        currency=record.stream.currency,
        sequence=record.sequence,
        captured_at=record.snapshot.captured_at,
        payload_hash=record.snapshot_hash,
    )


def _same_snapshot(
    record: StoredAccountSnapshot,
    request: SnapshotIngestionRequest,
) -> bool:
    return (
        record.stream == _stream(request)
        and record.sequence == request.sequence
        and record.received_at == request.received_at
        and record.snapshot_hash == request.snapshot.content_hash
        and record.snapshot == request.snapshot
    )


def _ingestion_rejection(
    code: IngestionCode,
    *reasons: str,
) -> SnapshotIngestionDecision:
    return SnapshotIngestionDecision(
        accepted=False,
        duplicate=False,
        code=code,
        blocking_reasons=tuple(sorted(set(reasons))),
        next_cursor=None,
    )


def _notification_events(
    *,
    snapshot: PropFirmAccountSnapshot,
    evaluation: AccountEvaluationV2,
    evaluation_id: str,
    occurred_at: datetime,
    payout_evaluated: bool,
) -> tuple[NotificationEvent, ...]:
    identity = NotificationIdentity(
        account_id=snapshot.account_id,
        firm_id=snapshot.firm_id,
        program_id=snapshot.program_id,
        profile_version=snapshot.profile_version,
    )
    values: list[tuple[NotificationEventType, str]] = []
    if evaluation.account_failed:
        values.append((NotificationEventType.ACCOUNT_FAILED, "account_failed"))
    elif not evaluation.trading_allowed_now:
        values.append((NotificationEventType.RISK_BLOCK, "trading_blocked"))
    if payout_evaluated and evaluation.payout_eligible:
        values.append((NotificationEventType.PAYOUT_ELIGIBLE, "payout_eligible"))
    reason = (
        evaluation.blocking_reasons[0]
        if evaluation.blocking_reasons else "NONE"
    )
    return tuple(
        create_notification_event(
            event_type,
            f"{evaluation_id}:{suffix}",
            occurred_at,
            identity=identity,
            payload={
                "evaluation_id": evaluation_id,
                "reason": reason,
                "trading_allowed_now": evaluation.trading_allowed_now,
            },
        )
        for event_type, suffix in values
    )


class Phase3ReadOnlyRuntime:
    """Composes Phase 3 evidence while preserving source-account read-only safety."""

    execution_authorized = False
    production_mutation_authorized = False
    source_account_mutation_authorized = False
    external_delivery_authorized = False

    _ACTIONS = (
        ReadAction.ACCOUNT_STATE,
        ReadAction.PROP_FIRM_EVALUATION,
        ReadAction.PORTFOLIO_SUMMARY,
        ReadAction.JOURNAL_ANALYTICS,
        ReadAction.NOTIFICATION_EVENT,
    )

    def __init__(
        self,
        store: Phase3DurableStateStore,
        *,
        authorization: ReadAuthorizationBoundary,
        registry: PropFirmProfileRegistry,
    ):
        if not isinstance(store, Phase3DurableStateStore):
            raise ValueError("store must be a Phase3DurableStateStore")
        if not isinstance(authorization, ReadAuthorizationBoundary):
            raise ValueError("authorization must be a ReadAuthorizationBoundary")
        if not isinstance(registry, PropFirmProfileRegistry):
            raise ValueError("registry must be a PropFirmProfileRegistry")
        self.store = store
        self.authorization_boundary = authorization
        self.registry = registry
        self.snapshots = AccountSnapshotRepository(store)
        self.evaluations = EvaluationRepository(store)
        self.audit_log = AuditLog(store)
        self.outbox = DurableOutbox(store)

    @staticmethod
    def _actor(request: ReadOnlyRuntimeRequest) -> StateUserIdentity | None:
        principal = request.principal
        if principal is None or (
            principal.identity.tenant_id != request.ingestion.tenant.tenant_id
        ):
            return None
        return StateUserIdentity(
            principal.identity.tenant_id,
            principal.identity.user_id,
        )

    def _audit(
        self,
        request: ReadOnlyRuntimeRequest,
        *,
        kind: AuditEventKind,
        occurred_at: datetime,
        recorded_at: datetime,
        fields: tuple[tuple[str, object], ...],
        causation_id: str | None = None,
    ) -> StoredAuditEvent:
        ingestion = request.ingestion
        event = AuditEvent(
            kind=kind,
            occurred_at=occurred_at,
            tenant=ingestion.tenant,
            source=ingestion.source.identity,
            payload=DurableStatePayload(tuple(sorted(fields))),
            actor=self._actor(request),
            account=ingestion.account,
            profile=ingestion.profile,
            correlation_id=ingestion.ingestion_id,
            causation_id=causation_id,
        )
        return self.audit_log.append(
            event,
            recorded_at=max(
                _aware(recorded_at, "recorded_at"),
                _aware(occurred_at, "occurred_at"),
            ),
        )

    def _ingestion_decision(
        self,
        request: SnapshotIngestionRequest,
        *,
        now: datetime,
        freshness: SnapshotFreshnessPolicy,
    ) -> SnapshotIngestionDecision:
        existing = self.snapshots.by_id(
            tenant_id=request.tenant.tenant_id,
            snapshot_id=request.ingestion_id,
        )
        if existing is not None and not _same_snapshot(existing, request):
            return _ingestion_rejection(
                IngestionCode.DUPLICATE_CONFLICT,
                "ingestion_id_conflict",
            )
        latest = self.snapshots.latest(_stream(request))
        previous = None if latest is None else _cursor(latest)
        decision = evaluate_snapshot_ingestion(
            request,
            now=now,
            freshness=freshness,
            previous=previous,
        )
        exact = existing if existing is not None else latest
        if (
            exact is not None
            and _same_snapshot(exact, request)
            and decision.code in {
                IngestionCode.STALE_SNAPSHOT,
                IngestionCode.FUTURE_SNAPSHOT,
                IngestionCode.INVALID_RECEIPT_TIME,
            }
        ):
            return SnapshotIngestionDecision(
                accepted=False,
                duplicate=True,
                code=IngestionCode.DUPLICATE_IDEMPOTENT,
                blocking_reasons=(),
                next_cursor=_cursor(exact),
            )
        return decision

    def _authorize(
        self,
        request: ReadOnlyRuntimeRequest,
    ) -> tuple[AuthorizationDecision, ...]:
        ingestion = request.ingestion
        principal = request.principal
        user_id = (
            principal.identity.user_id
            if isinstance(principal, AuthorizationPrincipal)
            else "unauthenticated"
        )
        decisions = []
        for action in self._ACTIONS:
            read_request = ReadRequest(
                action=action,
                tenant_id=ingestion.tenant.tenant_id,
                account_id=(
                    None if action is ReadAction.NOTIFICATION_EVENT
                    else ingestion.account.account_id
                ),
                user_id=(
                    user_id if action is ReadAction.NOTIFICATION_EVENT else None
                ),
            )
            decision = self.authorization_boundary.evaluate(principal, read_request)
            decisions.append(decision)
            if not decision.allowed:
                break
        return tuple(decisions)

    @staticmethod
    def _profile_matches(request: SnapshotIngestionRequest, profile: object) -> bool:
        return all((
            getattr(profile, "firm_id", None) == request.profile.firm_id,
            getattr(profile, "program_id", None) == request.profile.program_id,
            getattr(getattr(profile, "stage", None), "value", None) == request.profile.stage,
            getattr(profile, "account_size", None) == request.profile.account_size.value,
            getattr(profile, "version", None) == request.profile.profile_version,
            getattr(profile, "config_hash", None) == request.profile.config_hash,
        ))

    def process(
        self,
        request: ReadOnlyRuntimeRequest,
        *,
        now: datetime,
    ) -> ReadOnlyRuntimeResult:
        if not isinstance(request, ReadOnlyRuntimeRequest):
            raise ValueError("request must be a ReadOnlyRuntimeRequest")
        now = _aware(now, "now")
        ingestion = request.ingestion
        occurred_at = ingestion.received_at
        decision = self._ingestion_decision(
            ingestion,
            now=now,
            freshness=request.freshness,
        )
        if not (decision.accepted or decision.duplicate):
            audit = self._audit(
                request,
                kind=AuditEventKind.SNAPSHOT_REJECTED,
                occurred_at=occurred_at,
                recorded_at=now,
                fields=(
                    ("code", decision.code.value),
                    ("reasons", decision.blocking_reasons),
                ),
            )
            return ReadOnlyRuntimeResult(
                RuntimeStatus.REJECTED, decision, (), None, None, None, None,
                None, (), (), (audit,), decision.blocking_reasons,
            )

        authorization = self._authorize(request)
        denied = next((item for item in authorization if not item.allowed), None)
        if denied is not None:
            audit = self._audit(
                request,
                kind=AuditEventKind.AUTHORIZATION_DENIED,
                occurred_at=occurred_at,
                recorded_at=now,
                fields=(("decision_code", denied.code.value),),
            )
            reasons = (f"AUTHORIZATION_{denied.code.value}",)
            return ReadOnlyRuntimeResult(
                RuntimeStatus.DENIED, decision, authorization, None, None,
                None, None, None, (), (), (audit,), reasons,
            )

        snapshot = ingestion.snapshot
        try:
            resolved = self.registry.resolve_profile(
                snapshot.firm_id,
                snapshot.program_id,
                snapshot.stage,
                snapshot.account_size,
                snapshot.captured_at,
                version=snapshot.profile_version,
                required_source_status=SourceStatus.CURRENT_VERIFIED,
            )
        except ProfileRegistryError as exc:
            reason = f"PROFILE_RESOLUTION_{type(exc).__name__.upper()}"
            rejected = _ingestion_rejection(IngestionCode.PROFILE_MISMATCH, reason)
            audit = self._audit(
                request,
                kind=AuditEventKind.SNAPSHOT_REJECTED,
                occurred_at=occurred_at,
                recorded_at=now,
                fields=(("code", rejected.code.value), ("reasons", (reason,))),
            )
            return ReadOnlyRuntimeResult(
                RuntimeStatus.REJECTED, rejected, authorization, None, None,
                None, None, None, (), (), (audit,), (reason,),
            )
        if not self._profile_matches(ingestion, resolved.profile):
            reason = "PROFILE_REGISTRY_IDENTITY_MISMATCH"
            rejected = _ingestion_rejection(IngestionCode.PROFILE_MISMATCH, reason)
            audit = self._audit(
                request,
                kind=AuditEventKind.SNAPSHOT_REJECTED,
                occurred_at=occurred_at,
                recorded_at=now,
                fields=(("code", rejected.code.value), ("reasons", (reason,))),
            )
            return ReadOnlyRuntimeResult(
                RuntimeStatus.REJECTED, rejected, authorization, None, None,
                None, None, None, (), (), (audit,), (reason,),
            )

        stored_at = max(now, _aware(ingestion.received_at, "received_at"))
        snapshot_result = self.snapshots.append(
            ingestion,
            decision,
            stored_at=stored_at,
        )
        payout_requests = (
            {snapshot.account_id: request.payout_request}
            if request.payout_request is not None else None
        )
        evaluation = (
            evaluate_payout_v2(
                resolved.profile,
                snapshot.to_rule_snapshot(),
                request.payout_request,
                require_current_sources=True,
            )
            if request.payout_request is not None
            else evaluate_account_v2(
                resolved.profile,
                snapshot.to_rule_snapshot(),
                require_current_sources=True,
            )
        )
        evaluation_id = f"evaluation:{snapshot_result.record.snapshot_id}"
        evaluation_result = self.evaluations.append(
            tenant_id=ingestion.tenant.tenant_id,
            evaluation_id=evaluation_id,
            snapshot_id=snapshot_result.record.snapshot_id,
            evaluation=evaluation,
            evaluated_at=occurred_at,
            stored_at=stored_at,
        )
        diagnostics = evaluate_accounts(
            self.registry,
            (snapshot,),
            payout_requests=payout_requests,
            require_current_sources=True,
        )
        account_diagnostic = diagnostics.accounts[0]
        if any((
            account_diagnostic.account_valid != evaluation.account_valid,
            account_diagnostic.account_failed != evaluation.account_failed,
            account_diagnostic.trading_allowed_now != evaluation.trading_allowed_now,
            account_diagnostic.blocking_reasons != evaluation.blocking_reasons,
            account_diagnostic.failure_reasons != evaluation.failure_reasons,
        )):
            raise RuntimeCompositionError("multi-account evaluation drift detected")
        portfolio = analyze_prop_firm_portfolio(
            self.registry,
            (snapshot,),
            payout_requests=payout_requests,
            require_current_sources=True,
        )
        journal = analyze_trade_journal(request.journal_trades)
        notifications = _notification_events(
            snapshot=snapshot,
            evaluation=evaluation,
            evaluation_id=evaluation_id,
            occurred_at=occurred_at,
            payout_evaluated=request.payout_request is not None,
        )
        queued = []
        for notification in notifications:
            payload = DurableStatePayload(tuple(sorted((
                ("account_id", snapshot.account_id),
                ("blocking_reasons", evaluation.blocking_reasons),
                ("evaluation_id", evaluation_id),
                ("notification_event_id", notification.event_id),
                ("severity", notification.severity.value),
            ))))
            queued.append(self.outbox.enqueue(OutboxEvent(
                tenant=ingestion.tenant,
                event_kind=notification.event_type.value,
                dedupe_key=f"notification:{notification.dedupe_identity}",
                payload=payload,
                created_at=occurred_at,
                available_at=occurred_at,
            )))

        audits = [
            self._audit(
                request,
                kind=AuditEventKind.SNAPSHOT_RECEIVED,
                occurred_at=occurred_at,
                recorded_at=stored_at,
                fields=(("snapshot_id", snapshot_result.record.snapshot_id),),
                causation_id=snapshot_result.record.snapshot_id,
            ),
            self._audit(
                request,
                kind=AuditEventKind.PROFILE_RESOLVED,
                occurred_at=occurred_at,
                recorded_at=stored_at,
                fields=(
                    ("profile_config_hash", resolved.profile.config_hash),
                    ("source_status", resolved.source_status.value),
                ),
                causation_id=snapshot_result.record.snapshot_id,
            ),
            self._audit(
                request,
                kind=AuditEventKind.EVALUATION_COMPLETED,
                occurred_at=occurred_at,
                recorded_at=stored_at,
                fields=(
                    ("authoritative", evaluation_result.record.authoritative),
                    ("evaluation_id", evaluation_id),
                    ("trading_allowed_now", evaluation.trading_allowed_now),
                ),
                causation_id=evaluation_id,
            ),
        ]
        for notification, queued_item in zip(notifications, queued):
            audits.append(self._audit(
                request,
                kind=AuditEventKind.NOTIFICATION_QUEUED,
                occurred_at=occurred_at,
                recorded_at=stored_at,
                fields=(
                    ("notification_event_id", notification.event_id),
                    ("outbox_event_id", queued_item.record.event.event_id),
                    ("type", notification.event_type.value),
                ),
                causation_id=evaluation_id,
            ))
        return ReadOnlyRuntimeResult(
            status=RuntimeStatus.COMPLETED,
            ingestion_decision=decision,
            authorization=authorization,
            snapshot=snapshot_result,
            evaluation=evaluation_result,
            diagnostics=diagnostics,
            portfolio=portfolio,
            journal=journal,
            notifications=notifications,
            outbox=tuple(queued),
            audit=tuple(audits),
            blocking_reasons=(),
        )
