"""R32L tests for the Phase 3 read-only runtime composition."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
from pathlib import Path

import pytest

from backend.analytics.prop_firm_trade_journal_analytics import ClosedJournalTrade
from backend.entitlements import FeatureEntitlement, UserIdentity, UserRole
from backend.phase3 import (
    AccountIdentity,
    AccountReadScope,
    AccountScopeMode,
    AuthorizationCode,
    AuthorizationPrincipal,
    DecimalUnit,
    DurableDecimal,
    IngestionCode,
    OutboxStatus,
    Phase3DurableStateStore,
    Phase3ReadOnlyRuntime,
    PropFirmProfileIdentity,
    ReadOnlyRuntimeRequest,
    ReadAuthorizationBoundary,
    RuntimeStatus,
    SnapshotFreshnessPolicy,
    SnapshotIngestionRequest,
    SnapshotIngestionSource,
    SnapshotSourceKind,
    SourceIdentity,
    TenantIdentity,
)
from backend.prop_firms import (
    AccountSnapshot,
    AccountStage,
    PayoutCycleSnapshot,
    PropFirmAccountSnapshot,
    canonical_profile_registry,
)


NOW = datetime(2026, 10, 4, 15, 0, tzinfo=timezone.utc)
FRESHNESS = SnapshotFreshnessPolicy(120, 5)
_UNSET = object()


def canonical_profile():
    return canonical_profile_registry().resolve_profile(
        "topstep",
        "trading_combine",
        AccountStage.EVALUATION,
        D("50000"),
        NOW,
        version="2026-10-03/no-dll",
    ).profile


def state(*, failed=False, **changes):
    balance = D("48000") if failed else D("53000")
    realized = balance - D("50000")
    values = dict(
        as_of=NOW,
        account_started_at=NOW - timedelta(days=10),
        stage=AccountStage.EVALUATION,
        starting_balance=D("50000"),
        current_balance=balance,
        current_equity=balance,
        realized_pnl=realized,
        unrealized_pnl=D("0"),
        daily_pnl=D("-250") if failed else D("250"),
        highest_balance=D("53000"),
        highest_equity=D("53000"),
        highest_end_of_day_balance=D("53000"),
        prior_end_of_day_balance=D("52500"),
        contracts_open=0,
        working_orders=0,
        contracts_traded=2,
        trading_days=5,
        best_day_profit=D("750"),
        total_profit=realized,
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
            profit_since_last_payout=realized,
            winning_days_since_last_payout=3,
            trading_days_since_last_payout=5,
            best_day_profit_since_last_payout=D("750"),
        ),
    )
    values.update(changes)
    return AccountSnapshot(**values)


def ingestion(*, failed=False, profile_hash=None, rule_state=None):
    profile = canonical_profile()
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
        state=rule_state or state(failed=failed),
    )
    return SnapshotIngestionRequest(
        ingestion_id="ingest-1",
        tenant=TenantIdentity("tenant-a"),
        account=AccountIdentity("tenant-a", "account-1"),
        profile=PropFirmProfileIdentity(
            profile.firm_id,
            profile.program_id,
            profile.stage.value,
            DurableDecimal(profile.account_size, DecimalUnit.CURRENCY, "USD"),
            profile.version,
            profile_hash or profile.config_hash,
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


def principal(*, entitlements=frozenset(FeatureEntitlement), tenant_id="tenant-a"):
    return AuthorizationPrincipal(
        identity=UserIdentity("user-1", tenant_id),
        roles=frozenset({UserRole.OPERATOR}),
        entitlements=entitlements,
        account_scope=AccountReadScope(
            tenant_id,
            AccountScopeMode.EXPLICIT,
            frozenset({"account-1"}),
        ),
    )


def journal_trade():
    return ClosedJournalTrade(
        trade_id="trade-1",
        realized_pnl=D("200"),
        initial_risk=D("100"),
        instrument="NQ",
        session="NEW_YORK",
        account_id="account-1",
        firm_id="topstep",
    )


def runtime(store):
    return Phase3ReadOnlyRuntime(
        store,
        authorization=ReadAuthorizationBoundary(frozenset({
            AccountIdentity("tenant-a", "account-1"),
            AccountIdentity("tenant-b", "account-1"),
        })),
        registry=canonical_profile_registry(),
    )


def request(*, item=None, auth=_UNSET, trades=None):
    return ReadOnlyRuntimeRequest(
        ingestion=item or ingestion(failed=True),
        principal=principal() if auth is _UNSET else auth,
        freshness=FRESHNESS,
        journal_trades=(journal_trade(),) if trades is None else trades,
    )


def operational_counts(store):
    return tuple(
        store._connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in (
            "phase3_accounts", "phase3_account_snapshots",
            "phase3_evaluations", "phase3_outbox",
        )
    )


def test_composed_flow_persists_evidence_analytics_notification_and_audit(tmp_path):
    item = ingestion(failed=True)
    original_hash = item.snapshot.content_hash
    with Phase3DurableStateStore.create(tmp_path / "phase3.sqlite3") as store:
        result = runtime(store).process(
            request(item=item),
            now=NOW + timedelta(seconds=2),
        )

        assert result.status is RuntimeStatus.COMPLETED
        assert result.ingestion_decision.code is IngestionCode.ACCEPTED
        assert len(result.authorization) == 5
        assert all(value.allowed for value in result.authorization)
        assert result.snapshot.inserted and not result.snapshot.duplicate
        assert result.evaluation.inserted and result.evaluation.record.authoritative
        assert result.diagnostics.total_accounts == 1
        assert result.diagnostics.accounts[0].account_failed
        assert result.portfolio.accounts.total_accounts == 1
        assert result.journal.performance.net_pnl == D("200")
        assert [event.event_type.value for event in result.notifications] == [
            "ACCOUNT_FAILED"
        ]
        assert len(result.outbox) == 1
        assert result.outbox[0].record.status is OutboxStatus.PENDING
        assert [row.event.kind.value for row in result.audit] == [
            "SNAPSHOT_RECEIVED", "PROFILE_RESOLVED",
            "EVALUATION_COMPLETED", "NOTIFICATION_QUEUED",
        ]
        assert operational_counts(store) == (1, 1, 1, 1)
        assert item.snapshot.content_hash == original_hash
        assert result.execution_authorized is False
        assert result.production_mutation_authorized is False
        assert result.source_account_mutation_authorized is False
        assert result.external_delivery_authorized is False


def test_exact_retry_is_idempotent_even_after_freshness_window(tmp_path):
    runtime_request = request()
    with Phase3DurableStateStore.create(tmp_path / "phase3.sqlite3") as store:
        service = runtime(store)
        first = service.process(runtime_request, now=NOW + timedelta(seconds=2))
        before = (
            operational_counts(store),
            store._connection.execute(
                "SELECT COUNT(*) FROM phase3_audit_events"
            ).fetchone()[0],
        )
        replay = service.process(runtime_request, now=NOW + timedelta(hours=1))
        after = (
            operational_counts(store),
            store._connection.execute(
                "SELECT COUNT(*) FROM phase3_audit_events"
            ).fetchone()[0],
        )

        assert first.status is RuntimeStatus.COMPLETED
        assert replay.status is RuntimeStatus.COMPLETED
        assert replay.ingestion_decision.code is IngestionCode.DUPLICATE_IDEMPOTENT
        assert replay.snapshot.duplicate and replay.evaluation.duplicate
        assert replay.outbox[0].duplicate
        assert before == after == ((1, 1, 1, 1), 4)


def test_missing_auth_audits_denial_with_zero_operational_side_effects(tmp_path):
    with Phase3DurableStateStore.create(tmp_path / "phase3.sqlite3") as store:
        result = runtime(store).process(
            request(auth=None),
            now=NOW + timedelta(seconds=2),
        )

        assert result.status is RuntimeStatus.DENIED
        assert result.authorization[-1].code is AuthorizationCode.MISSING_AUTH
        assert operational_counts(store) == (0, 0, 0, 0)
        assert len(result.audit) == 1
        assert result.audit[0].event.kind.value == "AUTHORIZATION_DENIED"
        assert result.execution_authorized is False


def test_missing_notification_entitlement_blocks_before_any_operational_write(tmp_path):
    without_notifications = frozenset(FeatureEntitlement) - {
        FeatureEntitlement.NOTIFICATIONS
    }
    with Phase3DurableStateStore.create(tmp_path / "phase3.sqlite3") as store:
        result = runtime(store).process(
            request(auth=principal(entitlements=without_notifications)),
            now=NOW + timedelta(seconds=2),
        )

        assert result.status is RuntimeStatus.DENIED
        assert result.authorization[-1].code is AuthorizationCode.ENTITLEMENT_MISSING
        assert operational_counts(store) == (0, 0, 0, 0)


def test_cross_tenant_principal_is_denied_without_account_creation(tmp_path):
    with Phase3DurableStateStore.create(tmp_path / "phase3.sqlite3") as store:
        result = runtime(store).process(
            request(auth=principal(tenant_id="tenant-b")),
            now=NOW + timedelta(seconds=2),
        )
        assert result.status is RuntimeStatus.DENIED
        assert result.authorization[-1].code is AuthorizationCode.TENANT_MISMATCH
        assert operational_counts(store) == (0, 0, 0, 0)


def test_invalid_snapshot_is_audited_and_never_authorized_or_persisted(tmp_path):
    invalid = ingestion(rule_state=state(current_equity=None))
    with Phase3DurableStateStore.create(tmp_path / "phase3.sqlite3") as store:
        result = runtime(store).process(
            request(item=invalid),
            now=NOW + timedelta(seconds=2),
        )

        assert result.status is RuntimeStatus.REJECTED
        assert result.ingestion_decision.code is IngestionCode.INCOMPLETE_FINANCIAL_STATE
        assert result.authorization == ()
        assert operational_counts(store) == (0, 0, 0, 0)
        assert result.audit[0].event.kind.value == "SNAPSHOT_REJECTED"


def test_registry_identity_mismatch_rejects_before_snapshot_persistence(tmp_path):
    mismatched = ingestion(profile_hash="a" * 64)
    with Phase3DurableStateStore.create(tmp_path / "phase3.sqlite3") as store:
        result = runtime(store).process(
            request(item=mismatched),
            now=NOW + timedelta(seconds=2),
        )

        assert result.status is RuntimeStatus.REJECTED
        assert result.blocking_reasons == ("PROFILE_REGISTRY_IDENTITY_MISMATCH",)
        assert operational_counts(store) == (0, 0, 0, 0)


def test_healthy_snapshot_generates_no_risk_notification(tmp_path):
    healthy = ingestion(failed=False)
    with Phase3DurableStateStore.create(tmp_path / "phase3.sqlite3") as store:
        result = runtime(store).process(
            request(item=healthy, trades=()),
            now=NOW + timedelta(seconds=2),
        )
        assert result.status is RuntimeStatus.COMPLETED
        assert result.notifications == ()
        assert result.outbox == ()
        assert len(result.audit) == 3


def test_journal_scope_is_validated_before_runtime_creation():
    foreign = replace(journal_trade(), account_id="account-2")
    with pytest.raises(ValueError, match="ingested account"):
        request(trades=(foreign,))
    with pytest.raises(ValueError, match="unique"):
        request(trades=(journal_trade(), journal_trade()))


def test_runtime_module_has_no_broker_network_or_external_delivery_dependency():
    from backend.phase3 import runtime as runtime_module

    source = Path(runtime_module.__file__).read_text(encoding="utf-8").lower()
    forbidden = (
        "import requests", "import httpx", "import socket", "telegram",
        "broker_connector",
        "backend.execution", "enterlong", "entershort", "submit_order",
        "notificationdispatcher", "telegramnotificationprovider",
    )
    assert all(token not in source for token in forbidden)
    assert Phase3ReadOnlyRuntime.execution_authorized is False
    assert Phase3ReadOnlyRuntime.production_mutation_authorized is False
    assert Phase3ReadOnlyRuntime.source_account_mutation_authorized is False
    assert Phase3ReadOnlyRuntime.external_delivery_authorized is False
