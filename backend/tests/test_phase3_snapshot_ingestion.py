"""R32D tests for deterministic account snapshot ingestion."""

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
from pathlib import Path

import pytest

from backend.phase3 import (
    AccountIdentity, DecimalUnit, DurableDecimal, IngestionCode,
    PropFirmProfileIdentity, SnapshotCursor, SnapshotFreshnessPolicy,
    SnapshotIngestionRequest, SnapshotIngestionSource, SnapshotSourceKind,
    SourceIdentity, TenantIdentity, evaluate_snapshot_ingestion,
)
from backend.prop_firms import (
    AccountSnapshot, AccountStage, ExposurePosition, PayoutCycleSnapshot,
    PropFirmAccountSnapshot,
)


NOW = datetime(2026, 10, 4, 14, 30, tzinfo=timezone.utc)
FRESHNESS = SnapshotFreshnessPolicy(30, 5)


def state(**changes):
    values = dict(
        as_of=NOW, account_started_at=NOW - timedelta(days=20),
        stage=AccountStage.FUNDED, starting_balance=D("50000"),
        current_balance=D("53200"), current_equity=D("53150"),
        realized_pnl=D("3200"), unrealized_pnl=D("-50"), daily_pnl=D("250"),
        highest_balance=D("53400"), highest_equity=D("53500"),
        highest_end_of_day_balance=D("53300"), prior_end_of_day_balance=D("53000"),
        contracts_open=2, working_orders=1, contracts_traded=4, trading_days=8,
        best_day_profit=D("600"), total_profit=D("3200"), withdrawals=D("0"),
        prior_payout_count=1, exposures=(ExposurePosition("NQ", 1),),
        payout_cycle=PayoutCycleSnapshot(
            cycle_id="cycle-2", payout_count=1, current_cycle_start=NOW - timedelta(days=5),
            withdrawals_total=D("0"), profit_since_last_payout=D("1200"),
            winning_days_since_last_payout=4, trading_days_since_last_payout=5,
            best_day_profit_since_last_payout=D("400"),
        ),
    )
    values.update(changes)
    return AccountSnapshot(**values)


def snapshot(rule_state=None, **changes):
    values = dict(
        account_id="account-1", firm_id="lucid", program_id="lucid-program",
        profile_version="v1", stage=AccountStage.FUNDED, account_size=D("50000"),
        captured_at=NOW, data_source="runtime://paper/account-1", simulated=True,
        state=rule_state or state(),
    )
    values.update(changes)
    return PropFirmAccountSnapshot(**values)


def request(account_snapshot=None, **changes):
    values = dict(
        ingestion_id="ingest-1", tenant=TenantIdentity("tenant-a"),
        account=AccountIdentity("tenant-a", "account-1"),
        profile=PropFirmProfileIdentity(
            "lucid", "lucid-program", "FUNDED",
            DurableDecimal(D("50000"), DecimalUnit.CURRENCY, "USD"),
            "v1", "a" * 64,
        ),
        source=SnapshotIngestionSource(
            SourceIdentity("runtime://paper/account-1", "v1", True),
            SnapshotSourceKind.PAPER,
        ),
        sequence=1, received_at=NOW + timedelta(seconds=1), currency="USD",
        snapshot=account_snapshot or snapshot(),
    )
    values.update(changes)
    return SnapshotIngestionRequest(**values)


def evaluate(item=None, **changes):
    return evaluate_snapshot_ingestion(
        item or request(), now=changes.pop("now", NOW + timedelta(seconds=2)),
        freshness=changes.pop("freshness", FRESHNESS), **changes,
    )


def test_complete_fresh_snapshot_is_accepted_without_authority():
    decision = evaluate()
    assert decision.accepted and not decision.duplicate
    assert decision.code is IngestionCode.ACCEPTED
    assert decision.next_cursor.sequence == 1
    assert decision.next_cursor.payload_hash == request().snapshot.content_hash
    assert decision.execution_authorized is False
    assert decision.production_mutation_authorized is False
    with pytest.raises(FrozenInstanceError):
        decision.accepted = False


@pytest.mark.parametrize("field", [
    "starting_balance", "current_balance", "current_equity", "realized_pnl",
    "unrealized_pnl", "daily_pnl", "highest_balance", "highest_equity",
    "highest_end_of_day_balance", "prior_end_of_day_balance", "exposures",
    "contracts_open", "working_orders", "contracts_traded", "trading_days",
    "best_day_profit", "total_profit", "withdrawals", "prior_payout_count",
    "payout_cycle",
])
def test_missing_financial_risk_or_payout_state_fails_closed(field):
    decision = evaluate(request(snapshot(state(**{field: None}))))
    assert decision.code is IngestionCode.INCOMPLETE_FINANCIAL_STATE
    assert field in decision.blocking_reasons
    assert decision.next_cursor is None


def test_incomplete_payout_cycle_fails_closed_with_exact_field():
    cycle = replace(state().payout_cycle, winning_days_since_last_payout=None)
    decision = evaluate(request(snapshot(state(payout_cycle=cycle))))
    assert decision.code is IngestionCode.INCOMPLETE_FINANCIAL_STATE
    assert "payout_cycle.winning_days_since_last_payout" in decision.blocking_reasons


@pytest.mark.parametrize(("changes", "reason"), [
    ({"highest_balance": D("53199")}, "highest_balance_below_current_balance"),
    ({"highest_equity": D("53149")}, "highest_equity_below_current_equity"),
    ({"highest_end_of_day_balance": D("52999")}, "highest_eod_below_prior_eod"),
    ({"exposures": (ExposurePosition("NQ", 1), ExposurePosition("NQ", 2))}, "duplicate_exposure"),
])
def test_inconsistent_high_water_or_exposure_is_rejected(changes, reason):
    decision = evaluate(request(snapshot(state(**changes))))
    assert decision.code is IngestionCode.INCONSISTENT_FINANCIAL_STATE
    assert reason in decision.blocking_reasons


def test_identity_profile_and_source_mismatches_are_distinct_rejections():
    identity = evaluate(request(account=AccountIdentity("tenant-a", "account-2")))
    wrong_profile = replace(request().profile, profile_version="v2")
    profile = evaluate(request(profile=wrong_profile))
    source = SnapshotIngestionSource(
        SourceIdentity("file://snapshot", "v1", True), SnapshotSourceKind.FILE_IMPORT,
    )
    provenance = evaluate(request(source=source))
    assert identity.code is IngestionCode.IDENTITY_MISMATCH
    assert profile.code is IngestionCode.PROFILE_MISMATCH
    assert provenance.code is IngestionCode.SOURCE_MISMATCH


def test_stale_future_and_invalid_receipt_times_fail_closed():
    stale = evaluate(now=NOW + timedelta(seconds=31))
    future_snapshot = snapshot(state(as_of=NOW + timedelta(seconds=6)), captured_at=NOW + timedelta(seconds=6))
    future = evaluate(request(future_snapshot), now=NOW)
    early = evaluate(request(received_at=NOW - timedelta(seconds=6)), now=NOW)
    assert stale.code is IngestionCode.STALE_SNAPSHOT
    assert future.code is IngestionCode.FUTURE_SNAPSHOT
    assert early.code is IngestionCode.INVALID_RECEIPT_TIME


def test_duplicate_and_sequence_handling_is_deterministic():
    first = evaluate().next_cursor
    duplicate = evaluate(previous=first)
    assert duplicate.code is IngestionCode.DUPLICATE_IDEMPOTENT
    assert duplicate.duplicate and not duplicate.accepted
    assert duplicate.next_cursor is first

    changed_snapshot = snapshot(state(current_balance=D("53199")))
    conflict = evaluate(request(changed_snapshot), previous=first)
    assert conflict.code is IngestionCode.DUPLICATE_CONFLICT
    older = evaluate(request(sequence=1), previous=replace(first, sequence=2))
    assert older.code is IngestionCode.OUT_OF_ORDER_SEQUENCE


def test_new_sequence_requires_strictly_newer_capture_time_and_matching_cursor_scope():
    first = evaluate().next_cursor
    same_time = evaluate(request(sequence=2), previous=first)
    assert same_time.code is IngestionCode.OUT_OF_ORDER_TIMESTAMP
    mismatched = evaluate(previous=replace(first, account_id="account-2"))
    assert mismatched.code is IngestionCode.CURSOR_SCOPE_MISMATCH
    changed_version = evaluate(previous=replace(first, source_version="v2"))
    assert changed_version.code is IngestionCode.CURSOR_SCOPE_MISMATCH


def test_newer_sequence_and_capture_time_is_accepted():
    first = evaluate().next_cursor
    later = NOW + timedelta(seconds=1)
    later_snapshot = snapshot(state(as_of=later), captured_at=later)
    decision = evaluate(request(later_snapshot, sequence=2, received_at=later), previous=first, now=later)
    assert decision.code is IngestionCode.ACCEPTED
    assert decision.next_cursor.sequence == 2


@pytest.mark.parametrize("changes", [
    {"sequence": 0}, {"sequence": True}, {"currency": "usd"},
    {"received_at": datetime(2026, 10, 4)},
])
def test_envelope_validation_rejects_invalid_sequence_currency_or_time(changes):
    with pytest.raises(ValueError):
        request(**changes)


def test_paper_source_must_be_explicitly_simulated():
    with pytest.raises(ValueError, match="simulated"):
        SnapshotIngestionSource(
            SourceIdentity("paper", "v1", False), SnapshotSourceKind.PAPER,
        )


def test_ingestion_module_has_no_io_storage_network_or_execution_dependency():
    from backend.phase3 import snapshot_ingestion

    source = Path(snapshot_ingestion.__file__).read_text(encoding="utf-8")
    forbidden = (
        "sqlite3", "sqlalchemy", "backend.execution", "requests", "subprocess",
        "open(",
    )
    assert all(token not in source for token in forbidden)
