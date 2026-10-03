"""R59B measured local SMALL and MEDIUM staging load rehearsals."""

from __future__ import annotations

from collections import Counter
from contextlib import closing
from dataclasses import replace
from pathlib import Path
import sqlite3
import time

import pytest

from backend.phase4 import LoadDomain
from backend.phase5 import (
    STAGING_LOAD_PROFILES,
    StagingLoadObservation,
    StagingLoadOperation,
    StagingLoadProfileName,
    StagingLoadRehearsal,
)


def _identities(profile):
    return tuple(
        (f"tenant-{tenant:02d}", f"account-{account:03d}")
        for tenant in range(profile.tenant_count)
        for account in range(profile.accounts_per_tenant)
    )


def _database(path: Path) -> None:
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.executescript("""
            CREATE TABLE durable_writes (
                write_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                account_id TEXT NOT NULL,
                kind TEXT NOT NULL
            );
            CREATE TABLE outbox (
                event_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                account_id TEXT NOT NULL,
                notification INTEGER NOT NULL
            );
        """)


def _operations(profile, database: Path):
    identities = _identities(profile)
    operations = []
    sequence = 0
    notification_remaining = profile.notification_count

    for domain, count in profile.domain_counts.items():
        for index in range(count):
            tenant_id, account_id = identities[sequence % len(identities)]
            operation_id = f"{profile.name.value.lower()}-{domain.value.lower()}-{index:05d}"
            is_notification = domain is LoadDomain.OUTBOX and notification_remaining > 0
            if is_notification:
                notification_remaining -= 1

            def action(
                *, domain=domain, operation_id=operation_id, tenant_id=tenant_id,
                account_id=account_id, is_notification=is_notification,
            ):
                observed_at = time.perf_counter_ns()
                with closing(sqlite3.connect(database, timeout=5)) as connection, connection:
                    if domain in {
                        LoadDomain.SNAPSHOT_INGESTION,
                        LoadDomain.EVALUATION,
                        LoadDomain.RESEARCH_QUEUE,
                    }:
                        connection.execute(
                            "INSERT INTO durable_writes VALUES (?, ?, ?, ?)",
                            (operation_id, tenant_id, account_id, domain.value),
                        )
                    elif domain is LoadDomain.READ_API:
                        connection.execute(
                            "SELECT COUNT(*) FROM durable_writes "
                            "WHERE tenant_id = ? AND account_id = ?",
                            (tenant_id, account_id),
                        ).fetchone()
                    elif domain is LoadDomain.OUTBOX:
                        connection.execute(
                            "INSERT INTO outbox VALUES (?, ?, ?, ?)",
                            (operation_id, tenant_id, account_id, int(is_notification)),
                        )
                    outbox_depth = None
                    if domain is LoadDomain.OUTBOX:
                        outbox_depth = connection.execute(
                            "SELECT COUNT(*) FROM outbox"
                        ).fetchone()[0]
                completed_at = time.perf_counter_ns()
                return StagingLoadObservation(
                    tenant_id=tenant_id,
                    account_id=account_id,
                    durable_write_id=(
                        operation_id if domain in {
                            LoadDomain.SNAPSHOT_INGESTION,
                            LoadDomain.EVALUATION,
                            LoadDomain.RESEARCH_QUEUE,
                        } else None
                    ),
                    outbox_depth=outbox_depth,
                    worker_available_at_ns=(
                        observed_at if domain is LoadDomain.OUTBOX else None
                    ),
                    worker_claimed_at_ns=(
                        completed_at if domain is LoadDomain.OUTBOX else None
                    ),
                    scheduler_due_at_ns=(
                        observed_at if domain is LoadDomain.RESEARCH_QUEUE else None
                    ),
                    scheduler_claimed_at_ns=(
                        completed_at if domain is LoadDomain.RESEARCH_QUEUE else None
                    ),
                )

            operations.append(StagingLoadOperation(
                operation_id,
                domain,
                tenant_id,
                account_id,
                action,
                notification_event=is_notification,
            ))
            sequence += 1
    return tuple(operations)


def test_profile_counts_match_the_r59a_contract():
    small = STAGING_LOAD_PROFILES[StagingLoadProfileName.SMALL]
    medium = STAGING_LOAD_PROFILES[StagingLoadProfileName.MEDIUM]
    stress = STAGING_LOAD_PROFILES[StagingLoadProfileName.STRESS]

    assert (small.total_accounts, medium.total_accounts, stress.total_accounts) == (8, 200, 1000)
    assert (small.total_operations, medium.total_operations, stress.total_operations) == (261, 1552, 7810)
    assert (small.research_count, medium.research_count, stress.research_count) == (1, 2, 10)


@pytest.mark.parametrize("profile_name", [StagingLoadProfileName.SMALL, StagingLoadProfileName.MEDIUM])
def test_local_achievable_load_is_measured_and_tenant_isolated(tmp_path, profile_name):
    profile = STAGING_LOAD_PROFILES[profile_name]
    database = tmp_path / f"r59b-{profile_name.value.lower()}.sqlite3"
    _database(database)

    report = StagingLoadRehearsal().run(profile, _operations(profile, database))

    assert report.passed
    assert (report.attempted, report.succeeded, report.failed) == (
        profile.total_operations, profile.total_operations, 0
    )
    assert report.throughput_per_second > 0
    assert 0 <= report.latency.p50_ns <= report.latency.p95_ns <= report.latency.p99_ns
    assert report.error_rate == 0
    assert report.maximum_queue_depth <= profile.maximum_in_flight
    assert report.maximum_queue_lag_ns >= 0
    assert report.database_busy_failures == 0
    assert 1 <= report.peak_database_occupancy <= profile.maximum_workers
    assert report.maximum_worker_lag_ns > 0
    assert report.maximum_scheduler_lag_ns > 0
    assert report.final_outbox_depth == profile.domain_counts[LoadDomain.OUTBOX]
    assert report.maximum_outbox_depth == profile.domain_counts[LoadDomain.OUTBOX]
    assert report.tenant_isolation_violations == 0
    assert report.duplicate_durable_writes == 0
    assert report.external_traffic_authorized is False
    assert report.execution_authorized is False
    assert report.production_mutation_authorized is False
    assert report.live_trading_authorized is False

    with closing(sqlite3.connect(database)) as connection:
        writes = connection.execute(
            "SELECT tenant_id, account_id, COUNT(*) FROM durable_writes "
            "GROUP BY tenant_id, account_id"
        ).fetchall()
        outbox = connection.execute(
            "SELECT tenant_id, account_id, notification FROM outbox"
        ).fetchall()
    allowed = set(_identities(profile))
    assert {(tenant, account) for tenant, account, _ in writes} <= allowed
    assert {(tenant, account) for tenant, account, _ in outbox} <= allowed
    assert Counter(item[2] for item in outbox)[1] == profile.notification_count


def test_invalid_profile_shape_fails_before_any_action_runs():
    profile = STAGING_LOAD_PROFILES[StagingLoadProfileName.SMALL]
    effects = []
    operations = _operations(profile, Path("unused.sqlite3"))[:-1]
    operations = tuple(replace(item, action=lambda: effects.append("unsafe")) for item in operations)

    with pytest.raises(ValueError, match="operation counts"):
        StagingLoadRehearsal().run(profile, operations)

    assert effects == []


def test_cross_tenant_result_is_a_failed_operation_with_no_execution_authority(tmp_path):
    profile = STAGING_LOAD_PROFILES[StagingLoadProfileName.SMALL]
    database = tmp_path / "r59b-isolation.sqlite3"
    _database(database)
    operations = list(_operations(profile, database))
    target = operations[0]
    operations[0] = replace(
        target,
        action=lambda: StagingLoadObservation("tenant-outside-scope", target.account_id),
    )

    report = StagingLoadRehearsal().run(profile, tuple(operations))

    assert report.failed == 1
    assert report.tenant_isolation_violations == 1
    assert report.passed is False
    failed = [sample for sample in report.samples.samples if not sample.succeeded]
    assert len(failed) == 1
    assert failed[0].operation_id == target.operation_id
    assert failed[0].error_code == "TenantIsolationViolation"
    assert report.execution_authorized is False
    assert report.production_mutation_authorized is False
    assert report.live_trading_authorized is False

    expected_writes = (
        profile.domain_counts[LoadDomain.SNAPSHOT_INGESTION]
        + profile.domain_counts[LoadDomain.EVALUATION]
        + profile.domain_counts[LoadDomain.RESEARCH_QUEUE]
        - 1
    )
    with closing(sqlite3.connect(database)) as connection:
        actual_writes = connection.execute(
            "SELECT COUNT(*) FROM durable_writes"
        ).fetchone()[0]
    assert actual_writes == expected_writes
