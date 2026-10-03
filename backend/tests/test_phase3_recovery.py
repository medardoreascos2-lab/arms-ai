"""R32M crash/restart recovery tests for the Phase 3 read-only runtime."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D

import pytest

from backend.analytics.prop_firm_trade_journal_analytics import ClosedJournalTrade
from backend.entitlements import FeatureEntitlement, UserIdentity, UserRole
from backend.phase3 import (
    AccountIdentity,
    AccountReadScope,
    AccountScopeMode,
    AuthorizationPrincipal,
    DurableDecimal,
    DecimalUnit,
    OutboxWorker,
    Phase3DurableStateStore,
    Phase3ReadOnlyRuntime,
    Phase3RuntimeRecovery,
    PropFirmProfileIdentity,
    ReadAuthorizationBoundary,
    ReadOnlyRuntimeRequest,
    RecoveryStage,
    RecoveryStatus,
    RuntimeCheckpoint,
    RuntimeRecoveryError,
    SnapshotFreshnessPolicy,
    SnapshotIngestionRequest,
    SnapshotIngestionSource,
    SnapshotSourceKind,
    SourceIdentity,
    TenantIdentity,
    WorkerConfig,
    WorkerStepStatus,
)
from backend.prop_firms import (
    AccountSnapshot,
    AccountStage,
    PayoutCycleSnapshot,
    PropFirmAccountSnapshot,
    canonical_profile_registry,
)


NOW = datetime(2026, 10, 4, 15, 0, tzinfo=timezone.utc)


class SimulatedCrash(RuntimeError):
    pass


class SimulatedProcessCrash(BaseException):
    pass


class FakeClock:
    def __init__(self, value):
        self.value = value

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += timedelta(seconds=seconds)


def canonical_profile():
    return canonical_profile_registry().resolve_profile(
        "topstep",
        "trading_combine",
        AccountStage.EVALUATION,
        D("50000"),
        NOW,
        version="2026-10-03/no-dll",
    ).profile


def runtime_request():
    profile = canonical_profile()
    state = AccountSnapshot(
        as_of=NOW,
        account_started_at=NOW - timedelta(days=10),
        stage=AccountStage.EVALUATION,
        starting_balance=D("50000"),
        current_balance=D("48000"),
        current_equity=D("48000"),
        realized_pnl=D("-2000"),
        unrealized_pnl=D("0"),
        daily_pnl=D("-250"),
        highest_balance=D("53000"),
        highest_equity=D("53000"),
        highest_end_of_day_balance=D("53000"),
        prior_end_of_day_balance=D("52500"),
        contracts_open=0,
        working_orders=0,
        contracts_traded=2,
        trading_days=5,
        best_day_profit=D("750"),
        total_profit=D("-2000"),
        withdrawals=D("0"),
        prior_payout_count=0,
        prior_account_failed=False,
        session_id="session-1",
        daily_pnl_session_id="session-1",
        prior_session_blocked=False,
        trading_day_ends_at=NOW + timedelta(hours=2),
        exposures=(),
        payout_cycle=PayoutCycleSnapshot(
            cycle_id="cycle-1",
            payout_count=0,
            current_cycle_start=NOW - timedelta(days=5),
            withdrawals_total=D("0"),
            profit_since_last_payout=D("-2000"),
            winning_days_since_last_payout=3,
            trading_days_since_last_payout=5,
            best_day_profit_since_last_payout=D("750"),
        ),
    )
    snapshot = PropFirmAccountSnapshot(
        account_id="account-1",
        firm_id=profile.firm_id,
        program_id=profile.program_id,
        profile_version=profile.version,
        stage=profile.stage,
        account_size=profile.account_size,
        captured_at=NOW,
        data_source="runtime://paper/account-1",
        simulated=True,
        state=state,
    )
    ingestion = SnapshotIngestionRequest(
        ingestion_id="ingest-recovery-1",
        tenant=TenantIdentity("tenant-a"),
        account=AccountIdentity("tenant-a", "account-1"),
        profile=PropFirmProfileIdentity(
            profile.firm_id,
            profile.program_id,
            profile.stage.value,
            DurableDecimal(profile.account_size, DecimalUnit.CURRENCY, "USD"),
            profile.version,
            profile.config_hash,
        ),
        source=SnapshotIngestionSource(
            SourceIdentity("runtime://paper/account-1", "v1", True),
            SnapshotSourceKind.PAPER,
        ),
        sequence=1,
        received_at=NOW + timedelta(seconds=1),
        currency="USD",
        snapshot=snapshot,
    )
    principal = AuthorizationPrincipal(
        identity=UserIdentity("user-1", "tenant-a"),
        roles=frozenset({UserRole.OPERATOR}),
        entitlements=frozenset(FeatureEntitlement),
        account_scope=AccountReadScope(
            "tenant-a", AccountScopeMode.EXPLICIT, frozenset({"account-1"}),
        ),
    )
    trade = ClosedJournalTrade(
        trade_id="trade-1",
        realized_pnl=D("200"),
        initial_risk=D("100"),
        instrument="NQ",
        session="NEW_YORK",
        account_id="account-1",
        firm_id="topstep",
    )
    return ReadOnlyRuntimeRequest(
        ingestion=ingestion,
        principal=principal,
        freshness=SnapshotFreshnessPolicy(120, 5),
        journal_trades=(trade,),
    )


def runtime(store):
    return Phase3ReadOnlyRuntime(
        store,
        authorization=ReadAuthorizationBoundary(frozenset({
            AccountIdentity("tenant-a", "account-1"),
        })),
        registry=canonical_profile_registry(),
    )


def crash_at(target):
    def checkpoint(value):
        if value is target:
            raise SimulatedCrash(target.value)

    return checkpoint


def counts(store):
    return tuple(
        store._connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in (
            "phase3_account_snapshots", "phase3_evaluations",
            "phase3_outbox", "phase3_audit_events",
        )
    )


@pytest.mark.parametrize(
    ("checkpoint", "expected_stage", "expected_counts"),
    (
        (
            RuntimeCheckpoint.SNAPSHOT_COMMITTED,
            RecoveryStage.SNAPSHOT_COMMITTED,
            (1, 0, 0, 0),
        ),
        (
            RuntimeCheckpoint.BEFORE_EVALUATION_COMMIT,
            RecoveryStage.SNAPSHOT_COMMITTED,
            (1, 0, 0, 0),
        ),
        (
            RuntimeCheckpoint.OUTBOX_BEFORE_COMMIT,
            RecoveryStage.EVALUATION_COMMITTED,
            (1, 1, 0, 0),
        ),
        (
            RuntimeCheckpoint.OUTBOX_ENQUEUED,
            RecoveryStage.OUTBOX_COMMITTED,
            (1, 1, 1, 0),
        ),
        (
            RuntimeCheckpoint.AUDIT_COMMITTED,
            RecoveryStage.AUDIT_INCOMPLETE,
            (1, 1, 1, 1),
        ),
    ),
)
def test_restart_completes_each_interrupted_runtime_stage(
    tmp_path, checkpoint, expected_stage, expected_counts,
):
    database = tmp_path / "phase3.sqlite3"
    request = runtime_request()
    with Phase3DurableStateStore.create(database) as store:
        with pytest.raises(SimulatedCrash, match=checkpoint.value):
            runtime(store).process(
                request,
                now=NOW + timedelta(seconds=2),
                checkpoint=crash_at(checkpoint),
            )
        assert counts(store) == expected_counts

    with Phase3DurableStateStore.open(database) as store:
        recovery = Phase3RuntimeRecovery(runtime(store))
        assert recovery.inspect(request).stage is expected_stage
        result = recovery.recover(request, now=NOW + timedelta(minutes=1))

        assert result.status is RecoveryStatus.RECOVERED
        assert result.before.stage is expected_stage
        assert result.after.stage is RecoveryStage.COMPLETE
        assert result.after.incomplete_reasons == ()
        assert counts(store) == (1, 1, 1, 4)
        assert result.execution_authorized is False
        assert result.external_delivery_authorized is False


def test_duplicate_recovery_retry_has_no_double_evaluation_or_outbox_effect(tmp_path):
    database = tmp_path / "phase3.sqlite3"
    request = runtime_request()
    with Phase3DurableStateStore.create(database) as store:
        service = runtime(store)
        first = service.process(request, now=NOW + timedelta(seconds=2))
        before = counts(store)
        recovery = Phase3RuntimeRecovery(service)
        replay = recovery.recover(request, now=NOW + timedelta(hours=1))

        assert first.evaluation.inserted
        assert replay.status is RecoveryStatus.ALREADY_COMPLETE
        assert replay.runtime.snapshot.duplicate
        assert replay.runtime.evaluation.duplicate
        assert replay.runtime.outbox[0].duplicate
        assert before == counts(store) == (1, 1, 1, 4)


def test_recovery_rejects_conflicting_request_for_existing_snapshot_identity(tmp_path):
    request = runtime_request()
    with Phase3DurableStateStore.create(tmp_path / "phase3.sqlite3") as store:
        runtime(store).process(request, now=NOW + timedelta(seconds=2))
        conflicting = replace(
            request,
            ingestion=replace(
                request.ingestion,
                received_at=request.ingestion.received_at + timedelta(seconds=1),
            ),
        )

        with pytest.raises(RuntimeRecoveryError, match="conflicts"):
            Phase3RuntimeRecovery(runtime(store)).inspect(conflicting)


def test_worker_restart_reclaims_expired_lease_and_delivers_once(tmp_path):
    database = tmp_path / "phase3.sqlite3"
    request = runtime_request()
    clock = FakeClock(NOW + timedelta(minutes=1))
    delivered = []
    crash_once = [True]
    config = WorkerConfig(lease_seconds=30, max_attempts=3)

    def idempotent_transport(event):
        if event.event_id not in delivered:
            delivered.append(event.event_id)
        if crash_once[0]:
            crash_once[0] = False
            raise SimulatedProcessCrash("after external effect")

    with Phase3DurableStateStore.create(database) as store:
        runtime(store).process(request, now=NOW + timedelta(seconds=2))
        first_worker = OutboxWorker(
            store,
            tenant_id="tenant-a",
            worker_id="worker-before-crash",
            clock=clock,
            transport=idempotent_transport,
            config=config,
            token_factory=lambda: "lease-token-before-crash-0001",
        )
        with pytest.raises(SimulatedProcessCrash, match="after external effect"):
            first_worker.process_one()
        assert len(delivered) == 1

    clock.advance(31)
    with Phase3DurableStateStore.open(database) as store:
        restarted_worker = OutboxWorker(
            store,
            tenant_id="tenant-a",
            worker_id="worker-after-crash",
            clock=clock,
            transport=idempotent_transport,
            config=config,
            token_factory=lambda: "lease-token-after-crash-00002",
        )
        result = restarted_worker.process_one()
        idle = restarted_worker.process_one()

        assert result.status is WorkerStepStatus.DELIVERED
        assert result.record.attempt_count == 2
        assert idle.status is WorkerStepStatus.IDLE
        assert delivered == [result.record.event.event_id]
        assert restarted_worker.execution_authorized is False
        assert restarted_worker.external_delivery_authorized is False
