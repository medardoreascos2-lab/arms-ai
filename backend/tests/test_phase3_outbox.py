"""R32J tests for the persistence-only durable outbox."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
from pathlib import Path
import sqlite3

import pytest

from backend.phase3 import (
    DecimalUnit,
    DurableDecimal,
    DurableOutbox,
    DurableStatePayload,
    DurableStoreReadOnlyError,
    OutboxConflictError,
    OutboxEvent,
    OutboxIntegrityError,
    OutboxStatus,
    Phase3DurableStateStore,
    TenantIdentity,
    deserialize_outbox_event,
    outbox_event_hash,
    sanitize_outbox_error,
    serialize_outbox_event,
)


NOW = datetime(2026, 10, 5, 16, 0, tzinfo=timezone.utc)


def event(index=1, at=NOW, **changes):
    values = dict(
        tenant=TenantIdentity("tenant-a"),
        event_kind="NOTIFICATION_QUEUED",
        dedupe_key=f"telegram:account-1:drawdown:{index}",
        payload=DurableStatePayload((
            ("account_id", "account-1"),
            ("amount", DurableDecimal(D("250.00"), DecimalUnit.CURRENCY, "USD")),
            ("severity", "WARNING"),
        )),
        created_at=at,
        available_at=at + timedelta(seconds=index),
    )
    values.update(changes)
    return OutboxEvent(**values)


def test_outbox_codec_is_exact_deterministic_and_tamper_evident():
    original = event()
    payload = serialize_outbox_event(original)
    restored = deserialize_outbox_event(payload)
    assert restored == original
    assert restored.event_id == outbox_event_hash(original)
    assert serialize_outbox_event(restored) == payload
    assert b'"value":"250"' in payload
    tampered = payload.replace(b'"WARNING"', b'"CRITICAL"')
    with pytest.raises(ValueError, match="identity|canonical"):
        deserialize_outbox_event(tampered)


def test_enqueue_initializes_pending_state_without_delivery_authority(tmp_path):
    item = event()
    with Phase3DurableStateStore.create(tmp_path / "phase3.sqlite3") as store:
        outbox = DurableOutbox(store)
        result = outbox.enqueue(item)
        assert result.inserted is True and result.duplicate is False
        assert result.record.event == item
        assert result.record.status is OutboxStatus.PENDING
        assert result.record.attempt_count == 0
        assert result.record.next_attempt_at == item.available_at
        assert result.record.last_error is None
        assert result.record.updated_at == item.created_at
        assert result.execution_authorized is False
        assert outbox.execution_authorized is False
        assert outbox.external_delivery_authorized is False


def test_retry_is_idempotent_and_dedupe_conflict_rolls_back(tmp_path):
    item = event()
    with Phase3DurableStateStore.create(tmp_path / "phase3.sqlite3") as store:
        outbox = DurableOutbox(store)
        first = outbox.enqueue(item)
        duplicate = outbox.enqueue(item)
        assert duplicate.duplicate is True
        assert duplicate.record == first.record
        conflict = event(payload=DurableStatePayload((
            ("account_id", "account-1"),
            ("amount", DurableDecimal(D("999"), DecimalUnit.CURRENCY, "USD")),
            ("severity", "WARNING"),
        )))
        with pytest.raises(OutboxConflictError, match="dedupe key"):
            outbox.enqueue(conflict)
        assert store._connection.execute(
            "SELECT COUNT(*) FROM phase3_outbox"
        ).fetchone() == (1,)


def test_ready_is_tenant_scoped_due_ordered_and_bounded(tmp_path):
    items = (
        event(3, NOW),
        event(1, NOW),
        event(2, NOW),
    )
    with Phase3DurableStateStore.create(tmp_path / "phase3.sqlite3") as store:
        outbox = DurableOutbox(store)
        for item in items:
            outbox.enqueue(item)
        assert [row.event.dedupe_key for row in outbox.ready(
            tenant_id="tenant-a", now=NOW + timedelta(seconds=2)
        )] == [items[1].dedupe_key, items[2].dedupe_key]
        assert outbox.ready(tenant_id="tenant-b", now=NOW + timedelta(minutes=1)) == ()
        assert outbox.by_id(tenant_id="tenant-b", event_id=items[0].event_id) is None
        with pytest.raises(ValueError, match="limit"):
            outbox.ready(tenant_id="tenant-a", now=NOW, limit=0)


def test_payload_and_index_corruption_fail_closed(tmp_path):
    with Phase3DurableStateStore.create(tmp_path / "payload.sqlite3") as store:
        item = event()
        outbox = DurableOutbox(store)
        outbox.enqueue(item)
        store._connection.execute(
            "UPDATE phase3_outbox SET payload_sha256 = ?", ("0" * 64,)
        )
        with pytest.raises(OutboxIntegrityError, match="payload hash"):
            outbox.by_id(tenant_id="tenant-a", event_id=item.event_id)
    with Phase3DurableStateStore.create(tmp_path / "index.sqlite3") as store:
        item = event()
        outbox = DurableOutbox(store)
        outbox.enqueue(item)
        store._connection.execute("UPDATE phase3_outbox SET dedupe_key = 'changed'")
        with pytest.raises(OutboxIntegrityError, match="index or state"):
            outbox.by_id(tenant_id="tenant-a", event_id=item.event_id)


def test_database_constraints_reject_invalid_mutable_state(tmp_path):
    with Phase3DurableStateStore.create(tmp_path / "phase3.sqlite3") as store:
        item = event()
        outbox = DurableOutbox(store)
        outbox.enqueue(item)
        with pytest.raises(sqlite3.IntegrityError):
            store._connection.execute("UPDATE phase3_outbox SET attempt_count = -1")
        with pytest.raises(sqlite3.IntegrityError):
            store._connection.execute("UPDATE phase3_outbox SET status = 'UNKNOWN'")
        store._connection.execute(
            "UPDATE phase3_outbox SET last_error = ?",
            ("authorization=Bearer-secret",),
        )
        with pytest.raises(OutboxIntegrityError, match="index or state"):
            outbox.by_id(tenant_id="tenant-a", event_id=item.event_id)


def test_error_sanitizer_redacts_secrets_flattens_and_bounds_text():
    sanitized = sanitize_outbox_error(
        "delivery failed\napi_key=super-secret token:abc123 retry"
    )
    assert sanitized == (
        "delivery failed api_key=[REDACTED] token=[REDACTED] retry"
    )
    assert len(sanitize_outbox_error("x" * 1000)) == 512


def test_invalid_keys_sensitive_payloads_and_time_regression_are_rejected():
    with pytest.raises(ValueError, match="dedupe_key"):
        event(dedupe_key="bad key")
    with pytest.raises(ValueError, match="sensitive"):
        event(payload=DurableStatePayload((("password", "forbidden"),)))
    with pytest.raises(ValueError, match="cannot precede"):
        event(available_at=NOW - timedelta(seconds=1))


def test_read_only_reopen_reads_and_blocks_enqueue(tmp_path):
    path = tmp_path / "phase3.sqlite3"
    item = event()
    with Phase3DurableStateStore.create(path) as store:
        DurableOutbox(store).enqueue(item)
    with Phase3DurableStateStore.open(path, read_only=True) as store:
        outbox = DurableOutbox(store)
        assert outbox.by_id(tenant_id="tenant-a", event_id=item.event_id).event == item
        with pytest.raises(DurableStoreReadOnlyError):
            outbox.enqueue(event(2))


def test_outbox_module_has_no_transport_network_or_execution_dependency():
    from backend.phase3 import outbox

    source = Path(outbox.__file__).read_text(encoding="utf-8")
    forbidden = (
        "requests", "httpx", "telegram", "broker_connector",
        "backend.execution", "EnterLong", "EnterShort",
    )
    assert all(token not in source for token in forbidden)
    readme = Path(outbox.__file__).with_name("README.md").read_text(encoding="utf-8")
    assert "at-least-once delivery" in readme
    assert "exactly-once-effect intent" in readme
