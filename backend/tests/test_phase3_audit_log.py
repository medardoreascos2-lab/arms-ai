"""R32I tests for deterministic append-only audit evidence."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
import json
import sqlite3

import pytest

from backend.phase3 import (
    AccountIdentity,
    AuditEvent,
    AuditEventKind,
    AuditLog,
    AuditLogIntegrityError,
    DecimalUnit,
    DurableDecimal,
    DurableStatePayload,
    DurableStoreReadOnlyError,
    Phase3DurableStateStore,
    PropFirmProfileIdentity,
    SourceIdentity,
    TenantIdentity,
    UserIdentity,
    audit_event_hash,
    deserialize_audit_event,
    serialize_audit_event,
)


NOW = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)


def event(kind=AuditEventKind.SNAPSHOT_RECEIVED, at=NOW, **changes):
    values = dict(
        kind=kind,
        occurred_at=at,
        tenant=TenantIdentity("tenant-a"),
        source=SourceIdentity("phase3://runtime", "v1", True),
        payload=DurableStatePayload((
            ("accepted", True),
            ("amount", DurableDecimal(D("125.50"), DecimalUnit.CURRENCY, "USD")),
            ("reason", "VALIDATED"),
        )),
        actor=UserIdentity("tenant-a", "operator-1"),
        account=AccountIdentity("tenant-a", "account-1"),
        profile=PropFirmProfileIdentity(
            "lucid", "program", "FUNDED",
            DurableDecimal(D("50000"), DecimalUnit.CURRENCY, "USD"),
            "v1", "a" * 64,
        ),
        correlation_id="workflow-1",
        causation_id="input-1",
    )
    values.update(changes)
    return AuditEvent(**values)


def test_every_required_audit_event_kind_is_available():
    assert {item.value for item in AuditEventKind} == {
        "SNAPSHOT_RECEIVED", "SNAPSHOT_REJECTED", "PROFILE_RESOLVED",
        "EVALUATION_COMPLETED", "AUTHORIZATION_DENIED", "NOTIFICATION_QUEUED",
        "NOTIFICATION_SENT", "NOTIFICATION_TESTED", "RESEARCH_JOB_CREATED",
        "RESEARCH_JOB_COMPLETED", "CANDIDATE_PROMOTED_TO_PAPER_REVIEW",
        "CANDIDATE_REJECTED",
    }


def test_audit_codec_and_identity_are_deterministic_exact_and_tamper_evident():
    original = event()
    payload = serialize_audit_event(original)
    restored = deserialize_audit_event(payload)
    assert restored == original
    assert restored.event_id == audit_event_hash(original)
    assert serialize_audit_event(restored) == payload
    assert b'"value":"125.5"' in payload
    tampered = payload.replace(b'"accepted":true', b'"accepted":false')
    if tampered == payload:
        tampered = payload.replace(b'"VALIDATED"', b'"REJECTED"')
    with pytest.raises(ValueError, match="identity|canonical"):
        deserialize_audit_event(tampered)
    document = json.loads(payload)
    document["occurred_at"] = "2026-10-05T12:00:00+00:00"
    with pytest.raises(ValueError, match="canonical UTC"):
        deserialize_audit_event(
            json.dumps(document, sort_keys=True, separators=(",", ":"))
        )


def test_append_is_idempotent_and_has_no_authority(tmp_path):
    item = event()
    with Phase3DurableStateStore.create(tmp_path / "phase3.sqlite3") as store:
        log = AuditLog(store)
        inserted = log.append(item, recorded_at=NOW + timedelta(seconds=1))
        duplicate = log.append(item, recorded_at=NOW + timedelta(seconds=5))
        assert inserted.inserted is True
        assert duplicate.inserted is False
        assert duplicate.event == inserted.event
        assert duplicate.recorded_at == inserted.recorded_at
        assert inserted.execution_authorized is False
        assert log.execution_authorized is False
        assert store._connection.execute(
            "SELECT COUNT(*) FROM phase3_audit_events"
        ).fetchone() == (1,)


def test_unknown_denied_account_is_audited_without_creating_account_state(tmp_path):
    denied = event(
        AuditEventKind.AUTHORIZATION_DENIED,
        account=AccountIdentity("tenant-a", "unknown-account"),
        profile=None,
    )
    with Phase3DurableStateStore.create(tmp_path / "phase3.sqlite3") as store:
        result = AuditLog(store).append(denied, recorded_at=NOW + timedelta(seconds=1))
        assert result.event.account.account_id == "unknown-account"
        assert store._connection.execute(
            "SELECT COUNT(*) FROM phase3_accounts"
        ).fetchone() == (0,)


def test_history_is_tenant_scoped_ordered_and_filterable(tmp_path):
    with Phase3DurableStateStore.create(tmp_path / "phase3.sqlite3") as store:
        log = AuditLog(store)
        second = event(AuditEventKind.EVALUATION_COMPLETED, NOW + timedelta(seconds=2))
        first = event(AuditEventKind.SNAPSHOT_RECEIVED, NOW + timedelta(seconds=1))
        log.append(second, recorded_at=NOW + timedelta(seconds=3))
        log.append(first, recorded_at=NOW + timedelta(seconds=3))
        assert [row.event.kind for row in log.history(tenant_id="tenant-a")] == [
            AuditEventKind.SNAPSHOT_RECEIVED, AuditEventKind.EVALUATION_COMPLETED,
        ]
        assert [row.event for row in log.history(
            tenant_id="tenant-a", kind=AuditEventKind.EVALUATION_COMPLETED
        )] == [second]
        assert log.history(tenant_id="tenant-b") == ()
        assert log.by_id(tenant_id="tenant-b", event_id=first.event_id) is None


@pytest.mark.parametrize("statement", [
    "UPDATE phase3_audit_events SET event_kind = 'CHANGED'",
    "DELETE FROM phase3_audit_events",
])
def test_database_enforces_append_only_audit_events(tmp_path, statement):
    with Phase3DurableStateStore.create(tmp_path / "phase3.sqlite3") as store:
        AuditLog(store).append(event(), recorded_at=NOW + timedelta(seconds=1))
        with pytest.raises(sqlite3.IntegrityError, match="append only"):
            store._connection.execute(statement)


def test_corruption_is_detected(tmp_path):
    with Phase3DurableStateStore.create(tmp_path / "phase3.sqlite3") as store:
        item = event()
        log = AuditLog(store)
        log.append(item, recorded_at=NOW + timedelta(seconds=1))
        store._connection.execute("DROP TRIGGER phase3_audit_events_no_update")
        store._connection.execute(
            "UPDATE phase3_audit_events SET payload_sha256 = ?", ("0" * 64,)
        )
        with pytest.raises(AuditLogIntegrityError, match="payload hash"):
            log.by_id(tenant_id="tenant-a", event_id=item.event_id)
    with Phase3DurableStateStore.create(tmp_path / "indexed.sqlite3") as store:
        item = event()
        log = AuditLog(store)
        log.append(item, recorded_at=NOW + timedelta(seconds=1))
        store._connection.execute("DROP TRIGGER phase3_audit_events_no_update")
        store._connection.execute(
            "UPDATE phase3_audit_events SET event_kind = 'SNAPSHOT_REJECTED'"
        )
        with pytest.raises(AuditLogIntegrityError, match="index mismatch"):
            log.by_id(tenant_id="tenant-a", event_id=item.event_id)


def test_sensitive_payload_names_cross_tenant_scope_and_time_regression_fail_closed(tmp_path):
    with pytest.raises(ValueError, match="sensitive"):
        event(payload=DurableStatePayload((("api_token", "forbidden"),)))
    with pytest.raises(ValueError, match="tenant"):
        event(account=AccountIdentity("tenant-b", "account-1"))
    with Phase3DurableStateStore.create(tmp_path / "phase3.sqlite3") as store:
        with pytest.raises(ValueError, match="cannot precede"):
            AuditLog(store).append(event(), recorded_at=NOW - timedelta(seconds=1))
        assert store._connection.execute(
            "SELECT COUNT(*) FROM phase3_audit_events"
        ).fetchone() == (0,)


def test_read_only_reopen_reads_and_blocks_append(tmp_path):
    path = tmp_path / "phase3.sqlite3"
    item = event()
    with Phase3DurableStateStore.create(path) as store:
        AuditLog(store).append(item, recorded_at=NOW + timedelta(seconds=1))
    with Phase3DurableStateStore.open(path, read_only=True) as store:
        log = AuditLog(store)
        assert log.by_id(tenant_id="tenant-a", event_id=item.event_id).event == item
        with pytest.raises(DurableStoreReadOnlyError):
            log.append(
                event(AuditEventKind.PROFILE_RESOLVED, NOW + timedelta(seconds=2)),
                recorded_at=NOW + timedelta(seconds=3),
            )
