"""R58A local synthetic API multi-replica staging tests."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from threading import Lock

from fastapi import Body, FastAPI, Header, HTTPException
from fastapi.testclient import TestClient

from backend.phase3 import (
    AccountIdentity,
    DurableOutbox,
    DurableStateKind,
    DurableStatePayload,
    DurableStateRecord,
    OutboxEvent,
    Phase3DurableStateStore,
    SchemaIdentity,
    SourceIdentity,
    TenantIdentity,
)
from backend.phase4 import (
    Phase4RequestEnvelope,
    ReplayProtectionCode,
    ReplayProtectionScope,
    RequestEffect,
    RequestReplayProtector,
)


NOW = datetime(2026, 10, 6, 14, 0, tzinfo=timezone.utc)
TOKENS = {
    "synthetic-token-tenant-a": "tenant-a",
    "synthetic-token-tenant-b": "tenant-b",
}


def _canonical_payload(tenant_id: str, payload: dict[str, str]) -> bytes:
    return json.dumps(
        {"tenant_id": tenant_id, **payload},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


class SyntheticReplicaCoordinator:
    """Shared staging coordinator with no execution or external delivery authority."""

    execution_authorized = False
    production_mutation_authorized = False
    external_delivery_authorized = False

    def __init__(self, database: Path):
        self.database = database
        self.replay = RequestReplayProtector()
        self._lock = Lock()

    def write(
        self,
        tenant_id: str,
        payload: dict[str, str],
        *,
        request_id: str,
        nonce: str,
        idempotency_key: str,
    ) -> dict[str, object]:
        encoded = _canonical_payload(tenant_id, payload)
        envelope = Phase4RequestEnvelope(
            request_id=request_id,
            operation="phase5.staging.record.write",
            issued_at=NOW,
            effect=RequestEffect.STATE_CHANGE,
            nonce=nonce,
            idempotency_key=idempotency_key,
            payload_sha256=hashlib.sha256(encoded).hexdigest(),
        )
        scope = ReplayProtectionScope("phase5.api.user", tenant_id)
        with self._lock:
            decision = self.replay.evaluate(scope, envelope, evaluated_at=NOW)
            if not decision.accepted:
                raise HTTPException(status_code=409, detail=decision.code.value)

            with Phase3DurableStateStore.open(self.database) as store:
                if decision.code is ReplayProtectionCode.IDEMPOTENT_REPLAY:
                    existing = store.get(
                        tenant_id=tenant_id,
                        record_id=payload["record_id"],
                    )
                    if existing is None:
                        raise HTTPException(
                            status_code=503,
                            detail="IDEMPOTENT_RECORD_UNAVAILABLE",
                        )
                    return self._response(existing.record.record_id, inserted=False)

                record = DurableStateRecord(
                    record_id=payload["record_id"],
                    schema=SchemaIdentity("arms.phase5", "account", 1),
                    kind=DurableStateKind.ACCOUNT,
                    observed_at=NOW,
                    tenant=TenantIdentity(tenant_id),
                    source=SourceIdentity(
                        "phase5://synthetic-api-replica",
                        "r58a-v1",
                        True,
                    ),
                    payload=DurableStatePayload((("value", payload["value"]),)),
                    account=AccountIdentity(tenant_id, payload["account_id"]),
                )
                stored = store.append(record, committed_at=NOW + timedelta(seconds=1))
                DurableOutbox(store).enqueue(
                    OutboxEvent(
                        tenant=TenantIdentity(tenant_id),
                        event_kind="STAGING_RECORD_STORED",
                        dedupe_key=f"r58a:{tenant_id}:{payload['record_id']}",
                        payload=DurableStatePayload((
                            ("account_id", payload["account_id"]),
                            ("record_id", payload["record_id"]),
                        )),
                        created_at=NOW + timedelta(seconds=1),
                        available_at=NOW + timedelta(seconds=1),
                    )
                )
                return self._response(stored.record_id, inserted=stored.inserted)

    def read(self, tenant_id: str, record_id: str) -> dict[str, object]:
        with Phase3DurableStateStore.open(self.database, read_only=True) as store:
            record = store.get(tenant_id=tenant_id, record_id=record_id)
        if record is None:
            raise HTTPException(status_code=404, detail="RECORD_NOT_FOUND")
        return self._response(
            record.record.record_id,
            inserted=False,
            read_only=True,
            tenant_id=record.record.tenant.tenant_id,
            value=record.record.payload.get("value"),
        )

    @staticmethod
    def _response(
        record_id: str,
        *,
        inserted: bool,
        read_only: bool = False,
        tenant_id: str | None = None,
        value: object = None,
    ) -> dict[str, object]:
        response = {
            "record_id": record_id,
            "inserted": inserted,
            "read_only": read_only,
            "execution_authorized": False,
            "production_mutation_authorized": False,
            "external_delivery_authorized": False,
        }
        if tenant_id is not None:
            response["tenant_id"] = tenant_id
            response["value"] = value
        return response


def _authorize(tenant_id: str, token: str | None) -> None:
    if token is None or TOKENS.get(token) != tenant_id:
        raise HTTPException(status_code=403, detail="TENANT_SCOPE_DENIED")


def _replica(name: str, coordinator: SyntheticReplicaCoordinator) -> FastAPI:
    app = FastAPI(title=f"ARMS Phase 5 synthetic replica {name}")

    @app.post("/api/phase5/staging/{tenant_id}/records")
    def write_record(
        tenant_id: str,
        payload: dict[str, str] = Body(...),
        x_synthetic_tenant_token: str | None = Header(default=None),
        x_request_id: str = Header(...),
        x_nonce: str = Header(...),
        x_idempotency_key: str = Header(...),
    ) -> dict[str, object]:
        _authorize(tenant_id, x_synthetic_tenant_token)
        if set(payload) != {"record_id", "account_id", "value"}:
            raise HTTPException(status_code=422, detail="INVALID_PAYLOAD")
        return coordinator.write(
            tenant_id,
            payload,
            request_id=x_request_id,
            nonce=x_nonce,
            idempotency_key=x_idempotency_key,
        )

    @app.get("/api/phase5/staging/{tenant_id}/records/{record_id}")
    def read_record(
        tenant_id: str,
        record_id: str,
        x_synthetic_tenant_token: str | None = Header(default=None),
    ) -> dict[str, object]:
        _authorize(tenant_id, x_synthetic_tenant_token)
        return coordinator.read(tenant_id, record_id)

    return app


def _headers(tenant: str, index: int, *, idempotency: str) -> dict[str, str]:
    return {
        "x-synthetic-tenant-token": f"synthetic-token-{tenant}",
        "x-request-id": f"request-{tenant}-{index:04d}",
        "x-nonce": f"nonce-{tenant}-{index:04d}",
        "x-idempotency-key": idempotency,
    }


def _payload(record_id: str = "record-shared", value: str = "alpha") -> dict[str, str]:
    return {"record_id": record_id, "account_id": "account-1", "value": value}


def _setup(tmp_path: Path):
    database = tmp_path / "replicas.sqlite3"
    with Phase3DurableStateStore.create(database):
        pass
    coordinator = SyntheticReplicaCoordinator(database)
    return database, coordinator, _replica("a", coordinator), _replica("b", coordinator)


def test_replicas_share_database_outbox_and_tenant_consistent_reads(tmp_path):
    database, coordinator, app_a, app_b = _setup(tmp_path)
    with TestClient(app_a) as replica_a, TestClient(app_b) as replica_b:
        first = replica_a.post(
            "/api/phase5/staging/tenant-a/records",
            json=_payload(),
            headers=_headers("tenant-a", 1, idempotency="idempotency-tenant-a"),
        )
        second = replica_b.post(
            "/api/phase5/staging/tenant-b/records",
            json=_payload(value="beta"),
            headers=_headers("tenant-b", 1, idempotency="idempotency-tenant-b"),
        )
        observed_a_from_b = replica_b.get(
            "/api/phase5/staging/tenant-a/records/record-shared",
            headers={"x-synthetic-tenant-token": "synthetic-token-tenant-a"},
        )
        observed_a_from_a = replica_a.get(
            "/api/phase5/staging/tenant-a/records/record-shared",
            headers={"x-synthetic-tenant-token": "synthetic-token-tenant-a"},
        )
        observed_b = replica_a.get(
            "/api/phase5/staging/tenant-b/records/record-shared",
            headers={"x-synthetic-tenant-token": "synthetic-token-tenant-b"},
        )
        denied = replica_b.get(
            "/api/phase5/staging/tenant-b/records/record-shared",
            headers={"x-synthetic-tenant-token": "synthetic-token-tenant-a"},
        )

    assert first.status_code == second.status_code == 200
    assert first.json()["inserted"] is True
    assert second.json()["inserted"] is True
    assert observed_a_from_b.status_code == observed_a_from_a.status_code == 200
    assert observed_a_from_b.json() == observed_a_from_a.json()
    assert observed_a_from_b.json()["value"] == "alpha"
    assert observed_b.status_code == 200 and observed_b.json()["value"] == "beta"
    assert observed_a_from_b.json()["read_only"] is True
    assert denied.status_code == 403
    assert coordinator.execution_authorized is False
    assert coordinator.external_delivery_authorized is False
    with Phase3DurableStateStore.open(database, read_only=True) as store:
        assert store.count(tenant_id="tenant-a") == 1
        assert store.count(tenant_id="tenant-b") == 1
        assert store._connection.execute(
            "SELECT tenant_id, COUNT(*) FROM phase3_outbox GROUP BY tenant_id ORDER BY tenant_id"
        ).fetchall() == [("tenant-a", 1), ("tenant-b", 1)]


def test_cross_replica_idempotence_and_replay_rejections_have_zero_new_writes(tmp_path):
    database, _, app_a, app_b = _setup(tmp_path)
    payload = _payload()
    first_headers = _headers("tenant-a", 1, idempotency="idempotency-shared")
    retry_headers = _headers("tenant-a", 2, idempotency="idempotency-shared")
    conflict_headers = _headers("tenant-a", 3, idempotency="idempotency-shared")

    with TestClient(app_a) as replica_a, TestClient(app_b) as replica_b:
        first = replica_a.post(
            "/api/phase5/staging/tenant-a/records",
            json=payload,
            headers=first_headers,
        )
        retry = replica_b.post(
            "/api/phase5/staging/tenant-a/records",
            json=payload,
            headers=retry_headers,
        )
        replay = replica_b.post(
            "/api/phase5/staging/tenant-a/records",
            json=payload,
            headers=first_headers,
        )
        conflict = replica_b.post(
            "/api/phase5/staging/tenant-a/records",
            json=_payload(value="changed"),
            headers=conflict_headers,
        )

    assert first.status_code == 200 and first.json()["inserted"] is True
    assert retry.status_code == 200 and retry.json()["inserted"] is False
    assert replay.status_code == 409
    assert replay.json()["detail"] == "REQUEST_ID_REPLAY"
    assert conflict.status_code == 409
    assert conflict.json()["detail"] == "IDEMPOTENCY_CONFLICT"
    with Phase3DurableStateStore.open(database, read_only=True) as store:
        assert store.count(tenant_id="tenant-a") == 1
        assert store._connection.execute(
            "SELECT COUNT(*) FROM phase3_outbox WHERE tenant_id = 'tenant-a'"
        ).fetchone() == (1,)


def test_concurrent_requests_across_both_replicas_create_one_durable_effect(tmp_path):
    database, _, app_a, app_b = _setup(tmp_path)
    apps = (app_a, app_b)

    def submit(index: int) -> dict[str, object]:
        with TestClient(apps[index % 2]) as client:
            response = client.post(
                "/api/phase5/staging/tenant-a/records",
                json=_payload(),
                headers=_headers(
                    "tenant-a",
                    index + 1,
                    idempotency="idempotency-concurrent",
                ),
            )
        assert response.status_code == 200
        return response.json()

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = tuple(executor.map(submit, range(8)))

    assert sum(item["inserted"] is True for item in results) == 1
    assert sum(item["inserted"] is False for item in results) == 7
    assert all(item["execution_authorized"] is False for item in results)
    with Phase3DurableStateStore.open(database, read_only=True) as store:
        assert store.count(tenant_id="tenant-a") == 1
        assert store._connection.execute(
            "SELECT COUNT(*) FROM phase3_outbox WHERE tenant_id = 'tenant-a'"
        ).fetchone() == (1,)
