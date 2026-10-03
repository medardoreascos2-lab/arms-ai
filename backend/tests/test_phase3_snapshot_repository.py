"""R32G tests for durable, ordered account snapshot persistence."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
import hashlib
import json
import sqlite3

import pytest

from backend.phase3 import (
    AccountIdentity,
    AccountSnapshotRepository,
    DecimalUnit,
    DurableDecimal,
    DurableStoreReadOnlyError,
    IngestionCode,
    PropFirmProfileIdentity,
    SnapshotCursor,
    SnapshotFreshnessPolicy,
    SnapshotIngestionDecision,
    SnapshotIngestionRequest,
    SnapshotIngestionSource,
    SnapshotRepositoryConflictError,
    SnapshotRepositoryIntegrityError,
    SnapshotRepositoryOrderError,
    SnapshotRepositoryRejectedError,
    SnapshotSourceKind,
    SnapshotStreamIdentity,
    SourceIdentity,
    TenantIdentity,
    deserialize_account_snapshot,
    evaluate_snapshot_ingestion,
    serialize_account_snapshot,
)
from backend.phase3 import Phase3DurableStateStore
from backend.prop_firms import (
    AccountSnapshot,
    AccountStage,
    ExposurePosition,
    PayoutCycleSnapshot,
    PropFirmAccountSnapshot,
)


NOW = datetime(2026, 10, 4, 14, 30, tzinfo=timezone.utc)
FRESHNESS = SnapshotFreshnessPolicy(120, 5)


def state(at=NOW, **changes):
    values = dict(
        as_of=at,
        account_started_at=at - timedelta(days=20),
        stage=AccountStage.FUNDED,
        starting_balance=D("50000.00"),
        current_balance=D("53200.2500"),
        current_equity=D("53150.125"),
        realized_pnl=D("3200.25"),
        unrealized_pnl=D("-50.125"),
        daily_pnl=D("250.00"),
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
            current_cycle_start=at - timedelta(days=5),
            withdrawals_total=D("0"),
            profit_since_last_payout=D("1200.00"),
            winning_days_since_last_payout=4,
            trading_days_since_last_payout=5,
            best_day_profit_since_last_payout=D("400"),
        ),
    )
    values.update(changes)
    return AccountSnapshot(**values)


def snapshot(at=NOW, rule_state=None, **changes):
    values = dict(
        account_id="account-1",
        firm_id="lucid",
        program_id="lucid-program",
        profile_version="v1",
        stage=AccountStage.FUNDED,
        account_size=D("50000.00"),
        captured_at=at,
        data_source="runtime://paper/account-1",
        simulated=True,
        state=rule_state or state(at),
    )
    values.update(changes)
    return PropFirmAccountSnapshot(**values)


def request(sequence=1, at=NOW, account_snapshot=None, **changes):
    values = dict(
        ingestion_id=f"ingest-{sequence}",
        tenant=TenantIdentity("tenant-a"),
        account=AccountIdentity("tenant-a", "account-1"),
        profile=PropFirmProfileIdentity(
            "lucid",
            "lucid-program",
            "FUNDED",
            DurableDecimal(D("50000"), DecimalUnit.CURRENCY, "USD"),
            "v1",
            "a" * 64,
        ),
        source=SnapshotIngestionSource(
            SourceIdentity("runtime://paper/account-1", "v1", True),
            SnapshotSourceKind.PAPER,
        ),
        sequence=sequence,
        received_at=at + timedelta(seconds=1),
        currency="USD",
        snapshot=account_snapshot or snapshot(at),
    )
    values.update(changes)
    return SnapshotIngestionRequest(**values)


def decision(item, previous=None):
    return evaluate_snapshot_ingestion(
        item,
        now=item.received_at + timedelta(seconds=1),
        freshness=FRESHNESS,
        previous=previous,
    )


def forged_accept(item):
    cursor = SnapshotCursor(
        tenant_id=item.tenant.tenant_id,
        account_id=item.account.account_id,
        source_id=item.source.identity.source_id,
        source_version=item.source.identity.source_version,
        profile_config_hash=item.profile.config_hash,
        currency=item.currency,
        sequence=item.sequence,
        captured_at=item.snapshot.captured_at,
        payload_hash=item.snapshot.content_hash,
    )
    return SnapshotIngestionDecision(
        accepted=True,
        duplicate=False,
        code=IngestionCode.ACCEPTED,
        blocking_reasons=(),
        next_cursor=cursor,
    )


def stream(item=None):
    item = item or request()
    return SnapshotStreamIdentity(
        item.tenant.tenant_id,
        item.account.account_id,
        item.source.identity.source_id,
        item.source.identity.source_version,
        item.source.identity.simulated,
        item.profile.config_hash,
        item.currency,
    )


def test_snapshot_codec_round_trip_preserves_source_hash_offset_and_signed_zero():
    eastern = timezone(timedelta(hours=-4))
    at = NOW.astimezone(eastern)
    original = snapshot(
        at,
        rule_state=state(
            at,
            unrealized_pnl=D("-0.00"),
            exposures=(ExposurePosition("MNQ", 2, "NASDAQ"),),
        ),
    )
    encoded = serialize_account_snapshot(original)
    restored = deserialize_account_snapshot(encoded)
    assert restored == original
    assert restored.content_hash == original.content_hash
    assert restored.captured_at.isoformat() == original.captured_at.isoformat()
    assert restored.state.unrealized_pnl.is_signed()
    assert serialize_account_snapshot(restored) == encoded
    assert hashlib.sha256(encoded).hexdigest() == hashlib.sha256(
        serialize_account_snapshot(original)
    ).hexdigest()


def test_snapshot_codec_is_deterministic_exact_and_rejects_tampering():
    encoded = serialize_account_snapshot(snapshot())
    assert encoded == serialize_account_snapshot(snapshot())
    assert b'"value":"53200.25"' in encoded
    assert b"53200.2500" not in encoded
    assert b"53200.25" in encoded
    document = json.loads(encoded)
    document["content_hash"] = "0" * 64
    with pytest.raises(ValueError, match="content hash mismatch"):
        deserialize_account_snapshot(json.dumps(document, sort_keys=True, separators=(",", ":")))
    duplicate = encoded.decode().replace(
        '"account_id":"account-1"',
        '"account_id":"account-1","account_id":"account-2"',
    )
    with pytest.raises(ValueError, match="duplicate"):
        deserialize_account_snapshot(duplicate)
    document = json.loads(encoded)
    document["captured_at"]["utc"] = "2026-10-04T14:30:00+00:00"
    with pytest.raises(ValueError, match="timestamp is not canonical"):
        deserialize_account_snapshot(
            json.dumps(document, sort_keys=True, separators=(",", ":"))
        )


def test_accepted_snapshot_is_persisted_and_read_without_authority(tmp_path):
    path = tmp_path / "phase3.sqlite3"
    item = request()
    with Phase3DurableStateStore.create(path) as store:
        repository = AccountSnapshotRepository(store)
        result = repository.append(
            item,
            decision(item),
            stored_at=item.received_at + timedelta(seconds=1),
        )
        assert result.inserted is True and result.duplicate is False
        assert result.execution_authorized is False
        assert result.record.snapshot == item.snapshot
        assert result.record.snapshot_hash == item.snapshot.content_hash
        assert repository.by_id(
            tenant_id="tenant-a", snapshot_id="ingest-1"
        ) == result.record
        assert repository.latest(stream(item)) == result.record
        assert repository.execution_authorized is False


def test_rejected_ingestion_has_zero_persistence_side_effects(tmp_path):
    incomplete = request(
        account_snapshot=snapshot(rule_state=state(current_balance=None))
    )
    rejected = decision(incomplete)
    assert rejected.accepted is False
    with Phase3DurableStateStore.create(tmp_path / "phase3.sqlite3") as store:
        repository = AccountSnapshotRepository(store)
        with pytest.raises(SnapshotRepositoryRejectedError, match="rejected"):
            repository.append(
                incomplete,
                rejected,
                stored_at=incomplete.received_at + timedelta(seconds=1),
            )
        for table in (
            "phase3_account_snapshots", "phase3_tenants",
            "phase3_accounts", "phase3_profiles",
        ):
            assert store._connection.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone() == (0,)


def test_duplicate_retry_is_idempotent_even_with_new_ingestion_id(tmp_path):
    first = request()
    first_decision = decision(first)
    retry = request(ingestion_id="retry-1")
    retry_decision = decision(retry, previous=first_decision.next_cursor)
    assert retry_decision.code is IngestionCode.DUPLICATE_IDEMPOTENT
    with Phase3DurableStateStore.create(tmp_path / "phase3.sqlite3") as store:
        repository = AccountSnapshotRepository(store)
        inserted = repository.append(
            first, first_decision, stored_at=first.received_at + timedelta(seconds=1)
        )
        duplicate = repository.append(
            retry, retry_decision, stored_at=retry.received_at + timedelta(seconds=2)
        )
        assert duplicate.inserted is False and duplicate.duplicate is True
        assert duplicate.record == inserted.record
        assert store._connection.execute(
            "SELECT COUNT(*) FROM phase3_account_snapshots"
        ).fetchone() == (1,)


def test_duplicate_decision_without_stored_row_fails_without_scope_writes(tmp_path):
    item = request()
    duplicate = decision(item, previous=decision(item).next_cursor)
    with Phase3DurableStateStore.create(tmp_path / "phase3.sqlite3") as store:
        repository = AccountSnapshotRepository(store)
        with pytest.raises(SnapshotRepositoryRejectedError, match="no matching"):
            repository.append(
                item, duplicate, stored_at=item.received_at + timedelta(seconds=1)
            )
        assert store._connection.execute(
            "SELECT COUNT(*) FROM phase3_account_snapshots"
        ).fetchone() == (0,)
        assert store._connection.execute(
            "SELECT COUNT(*) FROM phase3_tenants"
        ).fetchone() == (0,)


def test_sequence_conflict_and_out_of_order_attempts_never_overwrite(tmp_path):
    first = request()
    changed = request(
        account_snapshot=snapshot(rule_state=state(current_balance=D("53199"))),
        ingestion_id="ingest-sequence-conflict",
    )
    with Phase3DurableStateStore.create(tmp_path / "phase3.sqlite3") as store:
        repository = AccountSnapshotRepository(store)
        original = repository.append(
            first, decision(first), stored_at=first.received_at + timedelta(seconds=1)
        )
        with pytest.raises(SnapshotRepositoryConflictError, match="sequence"):
            repository.append(
                changed,
                forged_accept(changed),
                stored_at=changed.received_at + timedelta(seconds=1),
            )

        later_at = NOW + timedelta(minutes=2)
        later = request(3, later_at)
        repository.append(
            later, forged_accept(later), stored_at=later.received_at + timedelta(seconds=1)
        )
        middle = request(2, NOW + timedelta(minutes=1))
        with pytest.raises(SnapshotRepositoryOrderError, match="sequence"):
            repository.append(
                middle,
                forged_accept(middle),
                stored_at=middle.received_at + timedelta(seconds=1),
            )
        assert repository.by_id(
            tenant_id="tenant-a", snapshot_id="ingest-1"
        ) == original.record
        assert store._connection.execute(
            "SELECT COUNT(*) FROM phase3_account_snapshots"
        ).fetchone() == (2,)


def test_capture_time_must_increase_with_sequence(tmp_path):
    first = request()
    second = request(2, NOW, ingestion_id="ingest-2")
    with Phase3DurableStateStore.create(tmp_path / "phase3.sqlite3") as store:
        repository = AccountSnapshotRepository(store)
        repository.append(
            first, decision(first), stored_at=first.received_at + timedelta(seconds=1)
        )
        with pytest.raises(SnapshotRepositoryOrderError, match="capture time"):
            repository.append(
                second,
                forged_accept(second),
                stored_at=second.received_at + timedelta(seconds=1),
            )
        assert repository.latest(stream()).sequence == 1


def test_history_latest_and_time_range_are_ordered_and_bounded(tmp_path):
    items = [
        request(index, NOW + timedelta(minutes=index - 1))
        for index in (1, 2, 3)
    ]
    with Phase3DurableStateStore.create(tmp_path / "phase3.sqlite3") as store:
        repository = AccountSnapshotRepository(store)
        previous = None
        for item in items:
            item_decision = decision(item, previous=previous)
            repository.append(
                item,
                item_decision,
                stored_at=item.received_at + timedelta(seconds=1),
            )
            previous = item_decision.next_cursor
        assert repository.latest(stream()).sequence == 3
        assert [row.sequence for row in repository.history(stream())] == [1, 2, 3]
        assert [row.sequence for row in repository.history(
            stream(), after_sequence=1, limit=1
        )] == [2]
        assert [row.sequence for row in repository.time_range(
            stream(),
            start=NOW + timedelta(seconds=1),
            end=NOW + timedelta(minutes=3),
        )] == [2, 3]
        with pytest.raises(ValueError, match="limit"):
            repository.history(stream(), limit=0)


def test_stream_identity_prevents_cross_tenant_or_source_reads(tmp_path):
    item = request()
    with Phase3DurableStateStore.create(tmp_path / "phase3.sqlite3") as store:
        repository = AccountSnapshotRepository(store)
        repository.append(
            item, decision(item), stored_at=item.received_at + timedelta(seconds=1)
        )
        other_tenant = replace(stream(), tenant_id="tenant-b")
        other_source = replace(stream(), source_id="file://import")
        assert repository.latest(other_tenant) is None
        assert repository.latest(other_source) is None
        assert repository.by_id(
            tenant_id="tenant-b", snapshot_id=item.ingestion_id
        ) is None


def test_read_only_reopen_supports_reads_and_blocks_append(tmp_path):
    path = tmp_path / "phase3.sqlite3"
    item = request()
    with Phase3DurableStateStore.create(path) as store:
        AccountSnapshotRepository(store).append(
            item, decision(item), stored_at=item.received_at + timedelta(seconds=1)
        )
    with Phase3DurableStateStore.open(path, read_only=True) as store:
        repository = AccountSnapshotRepository(store)
        assert repository.latest(stream()).snapshot == item.snapshot
        second = request(2, NOW + timedelta(minutes=1))
        with pytest.raises(DurableStoreReadOnlyError):
            repository.append(
                second,
                forged_accept(second),
                stored_at=second.received_at + timedelta(seconds=1),
            )


@pytest.mark.parametrize("statement", [
    "UPDATE phase3_account_snapshots SET sequence = 5",
    "DELETE FROM phase3_account_snapshots",
])
def test_snapshot_rows_are_database_enforced_append_only(tmp_path, statement):
    item = request()
    with Phase3DurableStateStore.create(tmp_path / "phase3.sqlite3") as store:
        repository = AccountSnapshotRepository(store)
        repository.append(
            item, decision(item), stored_at=item.received_at + timedelta(seconds=1)
        )
        with pytest.raises(sqlite3.IntegrityError, match="append only"):
            store._connection.execute(statement)
        assert repository.latest(stream()).sequence == 1


def test_stored_payload_corruption_is_detected(tmp_path):
    item = request()
    with Phase3DurableStateStore.create(tmp_path / "phase3.sqlite3") as store:
        repository = AccountSnapshotRepository(store)
        repository.append(
            item, decision(item), stored_at=item.received_at + timedelta(seconds=1)
        )
        store._connection.execute("DROP TRIGGER phase3_snapshots_no_update")
        store._connection.execute(
            "UPDATE phase3_account_snapshots SET payload_sha256 = ?",
            ("0" * 64,),
        )
        with pytest.raises(SnapshotRepositoryIntegrityError, match="payload hash"):
            repository.latest(stream())


def test_profile_hash_conflict_rolls_back_new_account_scope(tmp_path):
    first = request()
    conflicting_snapshot = snapshot(
        firm_id="other-firm",
        program_id="other-program",
        account_id="account-2",
        data_source="file://other",
    )
    conflicting = request(
        account_snapshot=conflicting_snapshot,
        account=AccountIdentity("tenant-a", "account-2"),
        profile=replace(
            first.profile,
            firm_id="other-firm",
            program_id="other-program",
        ),
        source=SnapshotIngestionSource(
            SourceIdentity("file://other", "v1", True),
            SnapshotSourceKind.FILE_IMPORT,
        ),
        ingestion_id="conflicting-profile",
    )
    with Phase3DurableStateStore.create(tmp_path / "phase3.sqlite3") as store:
        repository = AccountSnapshotRepository(store)
        repository.append(
            first, decision(first), stored_at=first.received_at + timedelta(seconds=1)
        )
        with pytest.raises(SnapshotRepositoryConflictError, match="profile hash"):
            repository.append(
                conflicting,
                forged_accept(conflicting),
                stored_at=conflicting.received_at + timedelta(seconds=1),
            )
        assert store._connection.execute(
            "SELECT COUNT(*) FROM phase3_accounts WHERE account_id = 'account-2'"
        ).fetchone() == (0,)
        assert store._connection.execute(
            "SELECT COUNT(*) FROM phase3_account_snapshots"
        ).fetchone() == (1,)


def test_repository_module_has_no_execution_network_or_account_mutation_dependency():
    from pathlib import Path
    from backend.phase3 import snapshot_repository

    source = Path(snapshot_repository.__file__).read_text(encoding="utf-8")
    forbidden = (
        "backend.execution",
        "broker_connector",
        "requests",
        "httpx",
        "account_state_manager",
        "EnterLong",
        "EnterShort",
    )
    assert all(token not in source for token in forbidden)
