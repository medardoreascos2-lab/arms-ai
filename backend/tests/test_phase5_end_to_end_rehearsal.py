"""R62B end-to-end local staging rehearsal with zero external effects."""

from contextlib import closing
from datetime import timedelta
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sqlite3

from fastapi.testclient import TestClient

from backend.phase3 import (
    STORE_SCHEMA_VERSION,
    OutboxWorker,
    RuntimeStatus,
    WorkerStepStatus,
)
from backend.phase4 import (
    HealthState,
    OperationalMetricName,
    build_operational_metrics_snapshot,
)
from backend.phase5 import (
    StagingBackupPayload,
    compose_phase5_local_staging_runtime,
    create_encrypted_staging_backup,
    open_encrypted_staging_backup,
)
from backend.research.backtest_runner import ResearchBacktestRunner
from backend.research.challenger_registry import (
    ChallengerStatus,
    ProductionReferenceDefinition,
    StrategyChallengerRegistry,
)
from backend.research.research_scheduler import (
    ResearchJobKind,
    ResearchJobRequest,
    ResearchSchedulerMode,
)
from backend.tests.test_phase3_runtime import NOW, request as runtime_request
from backend.tests.test_phase5_staging_runtime import _composition
from backend.tests.test_research_backtest_runner import (
    EntryExitStrategy,
    registry_with_csv,
    request as backtest_request,
)


class LocalNotificationSink:
    external_delivery_authorized = False
    execution_authorized = False
    production_mutation_authorized = False

    def __init__(self):
        self.events = []

    def __call__(self, event):
        self.events.append(event)


def _canonical(document) -> bytes:
    return json.dumps(
        document,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _audit_evidence(records) -> bytes:
    previous = "0" * 64
    entries = []
    for sequence, record in enumerate(records, start=1):
        evidence = {
            "event": record.event.kind.value,
            "previous_hash": previous,
            "sequence": sequence,
            "tenant_id": record.event.tenant.tenant_id,
        }
        current = hashlib.sha256(_canonical(evidence)).hexdigest()
        entries.append({**evidence, "hash": current})
        previous = current
    return _canonical({"entries": entries, "tip": previous})


def _health_values():
    return {
        OperationalMetricName.API_HEALTH: 1,
        OperationalMetricName.DB_HEALTH: 1,
        OperationalMetricName.WORKER_HEALTH: 1,
        OperationalMetricName.QUEUE_DEPTH: 0,
        OperationalMetricName.OUTBOX_FAILURES: 0,
        OperationalMetricName.SNAPSHOT_LAG_SECONDS: Decimal("1"),
        OperationalMetricName.EVALUATION_LAG_SECONDS: Decimal("1"),
        OperationalMetricName.RESEARCH_QUEUE: 1,
        OperationalMetricName.SCHEDULER_HEARTBEAT: 1,
        OperationalMetricName.AUTH_DENIALS: 0,
        OperationalMetricName.MIGRATION_STATE: 1,
    }


def test_full_local_staging_flow_preserves_traceability_and_zero_authority(tmp_path):
    dependencies, counters, key = _composition(tmp_path)
    store = dependencies.local_database
    runtime = compose_phase5_local_staging_runtime(dependencies)
    local_sink = LocalNotificationSink()
    try:
        with TestClient(runtime.api) as client:
            assert client.get("/api/phase3/status").status_code == 200

        result = dependencies.api_runtime.dependencies.application_runtime.process(
            runtime_request(),
            now=NOW + timedelta(seconds=2),
        )
        assert result.status is RuntimeStatus.COMPLETED
        assert all(decision.allowed for decision in result.authorization)
        assert result.snapshot.inserted is True
        assert result.evaluation.inserted is True
        assert result.portfolio.accounts.total_accounts == 1
        assert result.journal.performance.net_pnl == Decimal("200")
        assert len(result.notifications) == len(result.outbox) == 1

        worker = OutboxWorker(
            store,
            tenant_id="tenant-a",
            worker_id="phase5-r62b-worker",
            clock=lambda: NOW + timedelta(seconds=2),
            transport=local_sink,
            token_factory=lambda: "phase5-r62b-lease-token",
        )
        worker_result = worker.process_one()
        assert worker_result.status is WorkerStepStatus.DELIVERED
        assert local_sink.events == [result.outbox[0].record.event]

        research_root = tmp_path / "research"
        research_root.mkdir()
        dataset_registry, _ = registry_with_csv(research_root)
        backtest_input = backtest_request()
        research_job = ResearchJobRequest(
            strategy_id="candidate-r62b",
            kind=ResearchJobKind.BACKTEST,
            evidence_ids=(backtest_input.dataset_id, "r62b-experiment"),
            eligible_modes=(ResearchSchedulerMode.WEEKEND_RESEARCH,),
            estimated_cpu_percent=Decimal("10"),
            estimated_storage_bytes=4096,
            priority=10,
        )
        queued = dependencies.api_runtime.dependencies.research_queue.enqueue(
            research_job
        )
        assert queued.inserted is True

        backtest = ResearchBacktestRunner(dataset_registry).run(
            backtest_input,
            lambda context: EntryExitStrategy(),
        )
        challenger_registry = StrategyChallengerRegistry(
            ProductionReferenceDefinition(
                strategy_id="prod-v8",
                strategy_hash="a" * 64,
                parameters=backtest_input.parameters,
                evidence_ids=("v8-freeze",),
                registered_at=NOW - timedelta(days=1),
            )
        )
        challenger = challenger_registry.register_research(
            strategy_id="candidate-r62b",
            strategy_hash=backtest.strategy.sha256,
            parameters=backtest_input.parameters,
            evidence_ids=(backtest.dataset_id, backtest.result_hash),
            registered_at=NOW,
            reason="R62B_LOCAL_RESEARCH_EVIDENCE",
        ).record
        assert backtest.deterministic_replay_verified is True
        assert challenger.status is ChallengerStatus.RESEARCH

        metrics = build_operational_metrics_snapshot(_health_values(), observed_at=NOW)
        health = dependencies.api_runtime.dependencies.health_model.from_metrics(
            metrics,
            evaluated_at=NOW,
        )
        assert health.state is HealthState.HEALTHY

        audit_records = dependencies.api_runtime.dependencies.application_runtime.audit_log.history(
            tenant_id="tenant-a"
        )
        assert {item.event.kind.value for item in audit_records} == {
            "SNAPSHOT_RECEIVED",
            "PROFILE_RESOLVED",
            "EVALUATION_COMPLETED",
            "NOTIFICATION_QUEUED",
        }
        audit = _audit_evidence(audit_records)
        research = _canonical({
            "dataset_sha256": backtest.dataset_sha256,
            "evaluation_id": backtest.run_id,
            "strategy_sha256": backtest.strategy.sha256,
        })

        database_copy = tmp_path / "database-copy.sqlite3"
        with closing(sqlite3.connect(database_copy)) as destination:
            store._connection.backup(destination)
            destination.execute(f"PRAGMA user_version = {STORE_SCHEMA_VERSION}")
            destination.commit()
        database_bytes = database_copy.read_bytes()
        payload = StagingBackupPayload(
            database=database_bytes,
            database_schema_version=STORE_SCHEMA_VERSION,
            audit_continuity=audit,
            research_provenance=research,
            created_at=NOW,
        )
        archive = create_encrypted_staging_backup(
            payload,
            dependencies.backup_cipher,
        )
        restored_payload = open_encrypted_staging_backup(
            archive,
            dependencies.backup_cipher,
        )
        restored_database = tmp_path / "isolated-restore" / "restored.sqlite3"
        restored_database.parent.mkdir()
        restored_database.write_bytes(restored_payload.database)
        with closing(sqlite3.connect(
            restored_database.as_uri() + "?mode=ro",
            uri=True,
        )) as restored:
            restored.execute("PRAGMA query_only = ON")
            assert restored.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert restored.execute(
                "SELECT COUNT(*) FROM phase3_account_snapshots WHERE tenant_id = ?",
                ("tenant-a",),
            ).fetchone() == (1,)
            assert restored.execute(
                "SELECT COUNT(*) FROM phase3_audit_events WHERE tenant_id = ?",
                ("tenant-a",),
            ).fetchone() == (4,)

        assert restored_payload.payload_id == payload.payload_id
        assert counters.calls == 0
        guarded = (
            runtime,
            result,
            worker_result,
            local_sink,
            queued,
            backtest,
            challenger,
            health,
            payload,
            restored_payload,
        )
        for item in guarded:
            assert getattr(item, "execution_authorized", False) is False
            assert getattr(item, "production_mutation_authorized", False) is False
        assert runtime.external_traffic_authorized is False
        assert runtime.broker_authorized is False
        assert runtime.paper_trading_authorized is False
        assert runtime.live_trading_authorized is False
        assert local_sink.external_delivery_authorized is False
        assert backtest.live_execution_authorized is False
        assert challenger.paper_execution_authorized is False
        assert challenger.live_execution_authorized is False
    finally:
        store.close()
        key.close()


def test_rejected_tenant_has_zero_execution_and_operational_side_effects(tmp_path):
    dependencies, counters, key = _composition(tmp_path)
    store = dependencies.local_database
    try:
        denied = runtime_request(auth=None)
        result = dependencies.api_runtime.dependencies.application_runtime.process(
            denied,
            now=NOW + timedelta(seconds=2),
        )

        assert result.status is RuntimeStatus.DENIED
        assert result.execution_authorized is False
        assert result.production_mutation_authorized is False
        assert result.external_delivery_authorized is False
        assert tuple(
            store._connection.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0]
            for table in (
                "phase3_accounts",
                "phase3_account_snapshots",
                "phase3_evaluations",
                "phase3_outbox",
            )
        ) == (0, 0, 0, 0)
        assert counters.calls == 0
    finally:
        store.close()
        key.close()
