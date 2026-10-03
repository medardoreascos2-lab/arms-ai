"""R47B concurrent synthetic tenant/account isolation tests."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from backend.entitlements import FeatureEntitlement, UserIdentity, UserRole
from backend.phase3 import (
    AccountIdentity,
    AccountReadScope,
    AccountScopeMode,
    AuthorizationCode,
    AuthorizationPrincipal,
    DecimalUnit,
    DurableDecimal,
    DurableStateKind,
    DurableStatePayload,
    DurableStateRecord,
    PropFirmProfileIdentity,
    ReadAction,
    ReadAuthorizationBoundary,
    ReadRequest,
    SchemaIdentity,
    SourceIdentity,
    TenantIdentity,
)
from backend.phase4 import (
    DatabaseAccessMode,
    DatabaseBackend,
    DatabaseTarget,
    DatabaseTenantIsolationError,
    IsolatedLoadHarness,
    LoadDomain,
    LoadHarnessConfig,
    LoadOperation,
    SQLiteDatabaseAdapter,
)


OBSERVED = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)
COMMITTED = OBSERVED + timedelta(seconds=1)
TENANTS = tuple(f"tenant-{index}" for index in range(6))


def record(tenant_id: str, account_id: str, record_id: str) -> DurableStateRecord:
    return DurableStateRecord(
        record_id=record_id,
        schema=SchemaIdentity("arms.phase3", "account_snapshot", 1),
        kind=DurableStateKind.ACCOUNT_SNAPSHOT,
        observed_at=OBSERVED,
        tenant=TenantIdentity(tenant_id),
        source=SourceIdentity(
            f"runtime://paper/{tenant_id}/{account_id}",
            "synthetic-load-v1",
            True,
        ),
        payload=DurableStatePayload((
            (
                "balance",
                DurableDecimal(
                    Decimal("50000.00"),
                    DecimalUnit.CURRENCY,
                    "USD",
                ),
            ),
            ("risk_complete", True),
        )),
        account=AccountIdentity(tenant_id, account_id),
        profile=PropFirmProfileIdentity(
            "synthetic",
            "concurrent_isolation",
            "evaluation",
            DurableDecimal(Decimal("50000.00"), DecimalUnit.CURRENCY, "USD"),
            "2026-10-04",
            "b" * 64,
        ),
    )


def target(path) -> DatabaseTarget:
    return DatabaseTarget(
        DatabaseBackend.SQLITE,
        "arms_phase4",
        DatabaseAccessMode.READ_WRITE,
        sqlite_path=path,
    )


def harness() -> IsolatedLoadHarness:
    return IsolatedLoadHarness(
        LoadHarnessConfig(maximum_workers=6, maximum_in_flight=6)
    )


def test_concurrent_same_record_ids_never_cross_tenant_reads_or_writes(tmp_path):
    database = tmp_path / "tenant-load.sqlite3"
    adapter = SQLiteDatabaseAdapter()
    with adapter.connect(target(database)):
        pass

    writes = tuple(
        LoadOperation(
            f"write-{tenant_id}",
            LoadDomain.SNAPSHOT_INGESTION,
            lambda tenant_id=tenant_id: _write_own_record(adapter, database, tenant_id),
        )
        for tenant_id in TENANTS
    )
    write_report = harness().run(writes)
    assert all(sample.succeeded for sample in write_report.samples)

    reads = tuple(
        LoadOperation(
            f"read-{tenant_id}",
            LoadDomain.READ_API,
            lambda tenant_id=tenant_id: _assert_own_record(adapter, database, tenant_id),
        )
        for tenant_id in TENANTS
    )
    read_report = harness().run(reads)
    assert all(sample.succeeded for sample in read_report.samples)

    with adapter.connect(target(database)) as connection:
        assert sum(connection.tenant(item).count() for item in TENANTS) == len(TENANTS)


def _write_own_record(adapter, database, tenant_id):
    account_id = f"account-{tenant_id}"
    with adapter.connect(target(database)) as connection:
        result = connection.tenant(tenant_id).append(
            record(tenant_id, account_id, "shared-record"),
            committed_at=COMMITTED,
        )
        assert result.inserted is True


def _assert_own_record(adapter, database, tenant_id):
    with adapter.connect(target(database)) as connection:
        restored = connection.tenant(tenant_id).get(record_id="shared-record")
        assert restored is not None
        assert restored.record.tenant.tenant_id == tenant_id
        assert restored.record.account.account_id == f"account-{tenant_id}"


def test_concurrent_cross_tenant_write_attempts_all_fail_before_storage(tmp_path):
    database = tmp_path / "tenant-denials.sqlite3"
    adapter = SQLiteDatabaseAdapter()
    with adapter.connect(target(database)):
        pass

    def rejected(source_tenant: str, session_tenant: str):
        with adapter.connect(target(database)) as connection:
            try:
                connection.tenant(session_tenant).append(
                    record(source_tenant, f"account-{source_tenant}", "forbidden-record"),
                    committed_at=COMMITTED,
                )
            except DatabaseTenantIsolationError:
                return
            raise AssertionError("cross-tenant write was accepted")

    operations = tuple(
        LoadOperation(
            f"denied-{index}",
            LoadDomain.SNAPSHOT_INGESTION,
            lambda source=tenant_id, session=TENANTS[(index + 1) % len(TENANTS)]: rejected(
                source, session
            ),
        )
        for index, tenant_id in enumerate(TENANTS)
    )
    report = harness().run(operations)
    assert all(sample.succeeded for sample in report.samples)
    with adapter.connect(target(database)) as connection:
        assert all(connection.tenant(item).count() == 0 for item in TENANTS)


def test_shared_authorization_boundary_has_no_concurrent_scope_or_cache_bleed():
    known = frozenset(
        AccountIdentity(tenant_id, f"account-{tenant_id}") for tenant_id in TENANTS
    )
    boundary = ReadAuthorizationBoundary(known)

    def authorize(tenant_id: str, foreign_tenant: str):
        account_id = f"account-{tenant_id}"
        principal = AuthorizationPrincipal(
            identity=UserIdentity(f"user-{tenant_id}", tenant_id),
            roles=frozenset({UserRole.OPERATOR}),
            entitlements=frozenset(FeatureEntitlement),
            account_scope=AccountReadScope(
                tenant_id,
                AccountScopeMode.EXPLICIT,
                frozenset({account_id}),
            ),
        )
        allowed = boundary.evaluate(
            principal,
            ReadRequest(ReadAction.ACCOUNT_STATE, tenant_id, account_id),
        )
        denied = boundary.evaluate(
            principal,
            ReadRequest(
                ReadAction.ACCOUNT_STATE,
                foreign_tenant,
                f"account-{foreign_tenant}",
            ),
        )
        assert allowed.code is AuthorizationCode.ALLOWED
        assert allowed.authorized_account_ids == (account_id,)
        assert denied.code is AuthorizationCode.TENANT_MISMATCH
        assert denied.authorized_account_ids == ()

    operations = tuple(
        LoadOperation(
            f"authorization-{round_index}-{tenant_id}",
            LoadDomain.READ_API,
            lambda tenant_id=tenant_id, foreign=TENANTS[(index + 1) % len(TENANTS)]: authorize(
                tenant_id, foreign
            ),
        )
        for round_index in range(10)
        for index, tenant_id in enumerate(TENANTS)
    )
    report = harness().run(operations)
    assert len(report.samples) == 60
    assert all(sample.succeeded for sample in report.samples)
    assert boundary.known_accounts == known
