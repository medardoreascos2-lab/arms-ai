"""R48B end-to-end local staging rehearsal with no external sends or orders."""

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
import hashlib
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.phase3 import (
    AccountIdentity,
    OutboxStatus,
    OutboxWorker,
    Phase3ReadOnlyRuntime,
    ReadAuthorizationBoundary,
    RuntimeStatus,
    STORE_SCHEMA_VERSION,
    WorkerStepStatus,
)
from backend.phase4 import (
    AuthenticatedUserTransportPrincipal,
    HealthState,
    LocalBackupSources,
    OperationalMetricName,
    Phase4TransportAction,
    Phase4TransportAuthorizationBoundary,
    Phase4TransportRequest,
    RestoreTableExpectation,
    RestoreValidationPlan,
    TransportAuthorizationCode,
    build_operational_metrics_snapshot,
    compose_phase4_staging_runtime,
)
from backend.prop_firms import canonical_profile_registry
from backend.research.backtest_runner import ResearchBacktestRunner, ResearchParameterSet
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
from backend.tests.test_phase3_runtime import (
    NOW,
    ingestion as phase3_ingestion,
    request as phase3_request,
)
from backend.tests.test_phase4_staging_runtime import _dependencies
from backend.tests.test_research_backtest_runner import (
    EntryExitStrategy,
    registry_with_csv,
    request as backtest_request,
)


def _write_backup_metadata(root, runtime_result, challenger, backtest_result):
    root.mkdir()
    config = root / "config-identities.json"
    profiles = root / "profiles.json"
    audit = root / "audit-chain.json"
    research = root / "research-registry.json"
    config.write_text('{"service":"arms-phase4","tenant":"tenant-a"}', encoding="utf-8")
    profiles.write_text('{"profiles":["topstep/trading_combine"]}', encoding="utf-8")

    previous = None
    events = []
    for stored in runtime_result.audit:
        events.append({
            "event_hash": stored.storage_hash,
            "previous_event_hash": previous,
        })
        previous = stored.storage_hash
    audit.write_text(json.dumps({"events": events}, sort_keys=True), encoding="utf-8")
    research.write_text(
        json.dumps({
            "records": [{
                "record_hash": challenger.hash,
                "previous_record_hash": None,
                "source_hash": backtest_result.result_hash,
            }]
        }, sort_keys=True),
        encoding="utf-8",
    )
    return config, audit, research, profiles


def test_end_to_end_local_staging_rehearsal(tmp_path):
    dependencies, external_calls = _dependencies(tmp_path)
    store = dependencies.application_runtime.store
    account = AccountIdentity("tenant-a", "account-1")
    application_runtime = Phase3ReadOnlyRuntime(
        store,
        authorization=ReadAuthorizationBoundary(frozenset({account})),
        registry=canonical_profile_registry(),
    )
    dependencies = replace(
        dependencies,
        application_runtime=application_runtime,
        authorization=Phase4TransportAuthorizationBoundary(frozenset({account})),
    )

    try:
        staging = compose_phase4_staging_runtime(dependencies)
        ingestion = phase3_ingestion(failed=True)
        request = phase3_request(item=ingestion)
        transport_principal = AuthenticatedUserTransportPrincipal(
            request.principal,
            "tenant-a",
            NOW,
        )
        transport_decision = dependencies.authorization.evaluate(
            transport_principal,
            Phase4TransportRequest(
                Phase4TransportAction.ACCOUNT_OPERATIONS_READ,
                "tenant-a",
                "account-1",
            ),
            evaluated_at=NOW,
        )
        assert transport_decision.code is TransportAuthorizationCode.ALLOWED

        runtime_result = application_runtime.process(
            request,
            now=NOW + timedelta(seconds=2),
        )
        assert runtime_result.status is RuntimeStatus.COMPLETED
        assert runtime_result.snapshot.inserted is True
        assert runtime_result.evaluation.inserted is True
        assert runtime_result.diagnostics.total_accounts == 1
        assert runtime_result.portfolio.accounts.total_accounts == 1
        assert runtime_result.journal.performance.net_pnl == Decimal("200")
        assert len(runtime_result.notifications) == 1
        assert runtime_result.outbox[0].record.status is OutboxStatus.PENDING
        assert len(runtime_result.audit) == 4

        local_delivery_sink = []
        worker = OutboxWorker(
            store,
            tenant_id="tenant-a",
            worker_id="local-rehearsal-worker",
            clock=lambda: NOW + timedelta(seconds=3),
            transport=lambda item: local_delivery_sink.append(item.event_id),
            token_factory=lambda: "local-worker-token-0001",
        )
        worker_result = worker.process_one()
        assert worker_result.status is WorkerStepStatus.DELIVERED
        assert local_delivery_sink == [runtime_result.outbox[0].record.event.event_id]
        assert worker.external_delivery_authorized is False

        research_job = ResearchJobRequest(
            strategy_id="challenger-local",
            kind=ResearchJobKind.BACKTEST,
            evidence_ids=("dataset-local", "experiment-local"),
            eligible_modes=(ResearchSchedulerMode.WEEKEND_RESEARCH,),
            estimated_cpu_percent=Decimal("10"),
            estimated_storage_bytes=1_024,
            priority=10,
        )
        enqueue_result = dependencies.research_queue.enqueue(research_job)
        assert enqueue_result.inserted is True
        assert dependencies.research_queue.list() == (research_job,)

        research_root = tmp_path / "research"
        research_root.mkdir()
        dataset_registry, _ = registry_with_csv(research_root)
        research_request = backtest_request()
        backtest_result = ResearchBacktestRunner(dataset_registry).run(
            research_request,
            lambda context: EntryExitStrategy(),
        )
        assert backtest_result.deterministic_replay_verified is True
        assert backtest_result.metrics.total_trades == 1
        assert backtest_result.live_execution_authorized is False

        production_hash = hashlib.sha256(b"frozen-production-reference").hexdigest()
        challenger_registry = StrategyChallengerRegistry(
            ProductionReferenceDefinition(
                strategy_id="prod-v8",
                strategy_hash=production_hash,
                parameters=ResearchParameterSet.from_mapping({"risk": 1}),
                evidence_ids=("v8-freeze",),
                registered_at=NOW,
            )
        )
        challenger = challenger_registry.register_research(
            strategy_id="challenger-local",
            strategy_hash=backtest_result.strategy.sha256,
            parameters=research_request.parameters,
            evidence_ids=(backtest_result.result_hash, backtest_result.run_id),
            registered_at=NOW + timedelta(seconds=4),
            reason="LOCAL_STAGING_BACKTEST_COMPLETE",
        ).record
        challenger = challenger_registry.transition(
            challenger.strategy_id,
            ChallengerStatus.CHALLENGER,
            evidence_ids=("local-review",),
            reason="LOCAL_STAGING_REVIEW_ONLY",
            occurred_at=NOW + timedelta(seconds=5),
        )
        assert challenger.status is ChallengerStatus.CHALLENGER
        assert challenger.live_execution_authorized is False
        assert challenger.production_mutation_authorized is False

        metric_values = {name: 0 for name in OperationalMetricName}
        for name in (
            OperationalMetricName.API_HEALTH,
            OperationalMetricName.DB_HEALTH,
            OperationalMetricName.WORKER_HEALTH,
            OperationalMetricName.SCHEDULER_HEARTBEAT,
        ):
            metric_values[name] = 1
        metric_values[OperationalMetricName.RESEARCH_QUEUE] = 1
        metric_values[OperationalMetricName.MIGRATION_STATE] = 1
        metrics = build_operational_metrics_snapshot(
            metric_values,
            observed_at=NOW + timedelta(seconds=6),
        )
        export_result = dependencies.metrics_exporter.export(metrics)
        health = dependencies.health_model.from_metrics(
            metrics,
            evaluated_at=NOW + timedelta(seconds=6),
        )
        assert export_result.exported is True
        assert health.state is HealthState.HEALTHY

        app = FastAPI()
        app.include_router(staging.status_router)
        app.include_router(staging.research_router)
        client = TestClient(app)
        assert client.get("/api/phase3/status").status_code == 200
        assert client.get("/api/phase3/research/challengers").status_code == 200

        metadata = _write_backup_metadata(
            tmp_path / "backup-sources",
            runtime_result,
            challenger,
            backtest_result,
        )
        backup = dependencies.backup_runner.run(
            LocalBackupSources(
                database=tmp_path / "phase3.sqlite3",
                config_identities=metadata[0],
                audit_chain=metadata[1],
                research_registry=metadata[2],
                profile_registry=metadata[3],
            ),
            database_schema_version=STORE_SCHEMA_VERSION,
        )
        expectations = tuple(
            RestoreTableExpectation(
                table,
                store._connection.execute(
                    f'SELECT COUNT(*) FROM "{table}"'
                ).fetchone()[0],
                "tenant_id",
                ("tenant-a",),
            )
            for table in (
                "phase3_account_snapshots",
                "phase3_evaluations",
                "phase3_audit_events",
                "phase3_outbox",
            )
        )
        restore = dependencies.restore_validator.restore_and_validate(
            backup.backup_directory,
            RestoreValidationPlan(STORE_SCHEMA_VERSION, expectations),
        )
        assert restore.checksums_verified is True
        assert restore.tenant_isolation_verified is True
        assert restore.audit_continuity_verified is True
        assert restore.research_provenance_verified is True
        assert restore.audit_event_count == len(runtime_result.audit)
        assert restore.research_record_count == 1

        assert external_calls.calls == 0
        assert staging.execution_authorized is False
        assert staging.external_delivery_authorized is False
        assert staging.live_trading_authorized is False
        assert staging.deployment_authorized is False
    finally:
        store.close()
