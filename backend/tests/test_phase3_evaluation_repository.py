"""R32H tests for durable, non-authoritative-by-default evaluations."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
import sqlite3

import pytest

from backend.phase3 import (
    AccountIdentity,
    AccountSnapshotRepository,
    DecimalUnit,
    DurableDecimal,
    DurableStoreReadOnlyError,
    EvaluationRepository,
    EvaluationRepositoryConflictError,
    EvaluationRepositoryIntegrityError,
    EvaluationRepositoryRejectedError,
    Phase3DurableStateStore,
    PropFirmProfileIdentity,
    SnapshotFreshnessPolicy,
    SnapshotIngestionRequest,
    SnapshotIngestionSource,
    SnapshotSourceKind,
    SourceIdentity,
    TenantIdentity,
    deserialize_evaluation,
    evaluate_snapshot_ingestion,
    serialize_evaluation,
)
from backend.prop_firms import (
    AccountEvaluationV2,
    AccountSnapshot,
    AccountStage,
    ExposurePosition,
    PayoutCycleSnapshot,
    PropFirmAccountSnapshot,
    RuleOutcome,
    RuleScope,
    RuleStatus,
    SourceStatus,
)


NOW = datetime(2026, 10, 4, 14, 30, tzinfo=timezone.utc)
PROFILE_HASH = "a" * 64
PROFILE_IDENTITY = f"lucid/lucid-program/FUNDED/v1/{PROFILE_HASH}"


def snapshot():
    state = AccountSnapshot(
        as_of=NOW,
        account_started_at=NOW - timedelta(days=20),
        stage=AccountStage.FUNDED,
        starting_balance=D("50000"),
        current_balance=D("53200.25"),
        current_equity=D("53150.125"),
        realized_pnl=D("3200.25"),
        unrealized_pnl=D("-50.125"),
        daily_pnl=D("250"),
        highest_balance=D("53400"),
        highest_equity=D("53500"),
        highest_end_of_day_balance=D("53300"),
        prior_end_of_day_balance=D("53000"),
        contracts_open=2,
        working_orders=1,
        contracts_traded=4,
        trading_days=8,
        best_day_profit=D("600"),
        total_profit=D("3200.25"),
        withdrawals=D("0"),
        prior_payout_count=1,
        exposures=(ExposurePosition("NQ", 1),),
        payout_cycle=PayoutCycleSnapshot(
            cycle_id="cycle-2",
            payout_count=1,
            current_cycle_start=NOW - timedelta(days=5),
            withdrawals_total=D("0"),
            profit_since_last_payout=D("1200"),
            winning_days_since_last_payout=4,
            trading_days_since_last_payout=5,
            best_day_profit_since_last_payout=D("400"),
        ),
    )
    return PropFirmAccountSnapshot(
        "account-1", "lucid", "lucid-program", "v1", AccountStage.FUNDED,
        D("50000"), NOW, "runtime://paper/account-1", True, state,
    )


def ingestion():
    return SnapshotIngestionRequest(
        ingestion_id="snapshot-1",
        tenant=TenantIdentity("tenant-a"),
        account=AccountIdentity("tenant-a", "account-1"),
        profile=PropFirmProfileIdentity(
            "lucid", "lucid-program", "FUNDED",
            DurableDecimal(D("50000"), DecimalUnit.CURRENCY, "USD"),
            "v1", PROFILE_HASH,
        ),
        source=SnapshotIngestionSource(
            SourceIdentity("runtime://paper/account-1", "v1", True),
            SnapshotSourceKind.PAPER,
        ),
        sequence=1,
        received_at=NOW + timedelta(seconds=1),
        currency="USD",
        snapshot=snapshot(),
    )


def evaluation(*, status=SourceStatus.CURRENT_VERIFIED, incomplete=False):
    outcome_status = RuleStatus.INCOMPLETE_DATA if incomplete else RuleStatus.PASS
    return AccountEvaluationV2(
        account_valid=not incomplete,
        account_failed=False,
        trading_allowed_now=not incomplete,
        stage_objective_met=True,
        payout_eligible=False,
        outcomes=(RuleOutcome(
            "drawdown", RuleScope.ACCOUNT, outcome_status,
            "MISSING_CURRENT_EQUITY" if incomplete else "DRAWDOWN_OK",
            (("remaining_drawdown", D("3150.125")),),
            NOW + timedelta(hours=1),
        ),),
        warnings=("PAYOUT_NOT_EVALUATED",),
        blocking_reasons=("MISSING_CURRENT_EQUITY",) if incomplete else (),
        failure_reasons=(),
        metrics=(("current_equity", D("53150.125")), ("contracts_open", 2)),
        profile_identity=PROFILE_IDENTITY,
        rule_version="v1",
        source_status=status,
    )


def persist_snapshot(store):
    item = ingestion()
    decision = evaluate_snapshot_ingestion(
        item,
        now=item.received_at + timedelta(seconds=1),
        freshness=SnapshotFreshnessPolicy(120, 5),
    )
    return AccountSnapshotRepository(store).append(
        item, decision, stored_at=item.received_at + timedelta(seconds=1)
    ).record


def append(repository, result=None, **changes):
    values = dict(
        tenant_id="tenant-a",
        evaluation_id="evaluation-1",
        snapshot_id="snapshot-1",
        evaluation=result or evaluation(),
        evaluated_at=NOW + timedelta(seconds=3),
        stored_at=NOW + timedelta(seconds=4),
    )
    values.update(changes)
    return repository.append(**values)


def test_evaluation_codec_round_trip_is_exact_and_deterministic():
    original = evaluation()
    payload = serialize_evaluation(original)
    restored = deserialize_evaluation(payload)
    assert restored == original
    assert serialize_evaluation(restored) == payload
    assert b"53150.125" in payload
    assert b"3150.125" in payload


def test_current_complete_evaluation_is_authoritative_without_any_execution_authority(tmp_path):
    with Phase3DurableStateStore.create(tmp_path / "phase3.sqlite3") as store:
        persist_snapshot(store)
        repository = EvaluationRepository(store)
        result = append(repository)
        assert result.inserted is True and result.duplicate is False
        assert result.record.authoritative is True
        assert result.record.evaluation == evaluation()
        assert result.execution_authorized is False
        assert result.record.execution_authorized is False
        assert repository.execution_authorized is False
        assert repository.by_id(
            tenant_id="tenant-a", evaluation_id="evaluation-1"
        ) == result.record


@pytest.mark.parametrize("item", [
    evaluation(status=SourceStatus.INCOMPLETE),
    evaluation(incomplete=True),
    replace(evaluation(), outcomes=()),
])
def test_incomplete_source_or_input_is_never_authoritative(tmp_path, item):
    with Phase3DurableStateStore.create(tmp_path / "phase3.sqlite3") as store:
        persist_snapshot(store)
        result = append(EvaluationRepository(store), item)
        assert result.record.authoritative is False
        assert store._connection.execute(
            "SELECT authoritative FROM phase3_evaluations"
        ).fetchone() == (0,)


def test_missing_snapshot_or_profile_mismatch_is_rejected_without_writes(tmp_path):
    with Phase3DurableStateStore.create(tmp_path / "phase3.sqlite3") as store:
        repository = EvaluationRepository(store)
        with pytest.raises(EvaluationRepositoryRejectedError, match="not found"):
            append(repository)
        assert store._connection.execute(
            "SELECT COUNT(*) FROM phase3_evaluations"
        ).fetchone() == (0,)
        persist_snapshot(store)
        mismatch = replace(evaluation(), profile_identity="wrong/profile")
        with pytest.raises(EvaluationRepositoryRejectedError, match="profile"):
            append(repository, mismatch)
        wrong_version = replace(evaluation(), rule_version="v2")
        with pytest.raises(EvaluationRepositoryRejectedError, match="version"):
            append(repository, wrong_version)
        assert store._connection.execute(
            "SELECT COUNT(*) FROM phase3_evaluations"
        ).fetchone() == (0,)


def test_duplicate_is_idempotent_and_conflict_never_overwrites(tmp_path):
    with Phase3DurableStateStore.create(tmp_path / "phase3.sqlite3") as store:
        persist_snapshot(store)
        repository = EvaluationRepository(store)
        first = append(repository)
        duplicate = append(repository, stored_at=NOW + timedelta(seconds=8))
        assert duplicate.duplicate is True
        assert duplicate.record == first.record
        changed = replace(evaluation(), warnings=("CHANGED",))
        with pytest.raises(EvaluationRepositoryConflictError, match="different"):
            append(repository, changed)
        with pytest.raises(EvaluationRepositoryConflictError, match="different"):
            append(
                repository,
                evaluated_at=NOW + timedelta(seconds=7),
                stored_at=NOW + timedelta(seconds=8),
            )
        assert repository.by_id(
            tenant_id="tenant-a", evaluation_id="evaluation-1"
        ) == first.record


def test_reads_are_tenant_scoped_and_snapshot_ordered(tmp_path):
    with Phase3DurableStateStore.create(tmp_path / "phase3.sqlite3") as store:
        persist_snapshot(store)
        repository = EvaluationRepository(store)
        first = append(repository).record
        second = append(
            repository,
            evaluation_id="evaluation-2",
            evaluated_at=NOW + timedelta(seconds=5),
            stored_at=NOW + timedelta(seconds=6),
        ).record
        assert repository.by_id(
            tenant_id="tenant-b", evaluation_id="evaluation-1"
        ) is None
        assert repository.for_snapshot(
            tenant_id="tenant-a", snapshot_id="snapshot-1"
        ) == (first, second)


@pytest.mark.parametrize("statement", [
    "UPDATE phase3_evaluations SET authoritative = 0",
    "DELETE FROM phase3_evaluations",
])
def test_database_enforces_append_only_evaluations(tmp_path, statement):
    with Phase3DurableStateStore.create(tmp_path / "phase3.sqlite3") as store:
        persist_snapshot(store)
        append(EvaluationRepository(store))
        with pytest.raises(sqlite3.IntegrityError, match="append only"):
            store._connection.execute(statement)


def test_corruption_is_detected_and_read_only_reopen_blocks_append(tmp_path):
    path = tmp_path / "phase3.sqlite3"
    with Phase3DurableStateStore.create(path) as store:
        persist_snapshot(store)
        append(EvaluationRepository(store))
        store._connection.execute("DROP TRIGGER phase3_evaluations_no_update")
        store._connection.execute(
            "UPDATE phase3_evaluations SET payload_sha256 = ?", ("0" * 64,)
        )
        with pytest.raises(EvaluationRepositoryIntegrityError, match="payload hash"):
            EvaluationRepository(store).by_id(
                tenant_id="tenant-a", evaluation_id="evaluation-1"
            )
    linked = tmp_path / "linked.sqlite3"
    with Phase3DurableStateStore.create(linked) as store:
        persist_snapshot(store)
        append(EvaluationRepository(store))
        store._connection.execute("DROP TRIGGER phase3_snapshots_no_update")
        store._connection.execute(
            "UPDATE phase3_account_snapshots SET payload_sha256 = ?", ("0" * 64,)
        )
        with pytest.raises(EvaluationRepositoryIntegrityError, match="snapshot evidence"):
            EvaluationRepository(store).by_id(
                tenant_id="tenant-a", evaluation_id="evaluation-1"
            )
    clean = tmp_path / "clean.sqlite3"
    with Phase3DurableStateStore.create(clean) as store:
        persist_snapshot(store)
    with Phase3DurableStateStore.open(clean, read_only=True) as store:
        with pytest.raises(DurableStoreReadOnlyError):
            append(EvaluationRepository(store))
