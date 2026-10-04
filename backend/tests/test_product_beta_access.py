"""P111A closed-beta access model tests."""

from datetime import datetime, timedelta, timezone

import pytest

from backend.product.beta_access import (
    BetaAccessRecord,
    BetaAccessStatus,
    LocalSqliteBetaAccessStore,
)


NOW = datetime(2026, 10, 4, tzinfo=timezone.utc)


def record(tenant, user, status="INVITED", version=1):
    return BetaAccessRecord(
        access_id=f"access-{tenant}-{user}", tenant_id=tenant, user_id=user,
        status=status, invited_at=NOW, updated_at=NOW, version=version,
    )


def test_beta_statuses_match_contract():
    assert {item.value for item in BetaAccessStatus} == {
        "INVITED", "ACTIVE", "PAUSED", "REVOKED", "EXPIRED",
    }


def test_store_isolates_tenants_and_users_and_enforces_versions():
    store = LocalSqliteBetaAccessStore()
    store.save(record("tenant-a", "user-1"))
    store.save(record("tenant-b", "user-1", "ACTIVE"))
    assert store.get("tenant-a", "user-1").status == BetaAccessStatus.INVITED
    assert store.get("tenant-b", "user-1").status == BetaAccessStatus.ACTIVE
    assert store.get("tenant-a", "missing") is None
    assert len(store.list_records("tenant-a")) == 1
    with pytest.raises(ValueError):
        store.save(record("tenant-a", "user-1", "ACTIVE", 2), expected_version=99)
    store.save(record("tenant-a", "user-1", "ACTIVE", 2), expected_version=1)
    assert store.get("tenant-a", "user-1").version == 2


def test_beta_access_requires_utc_timestamps():
    with pytest.raises(ValueError):
        BetaAccessRecord(
            access_id="access-1", tenant_id="tenant", user_id="user",
            status="INVITED", invited_at=datetime(2026, 10, 4),
            updated_at=NOW + timedelta(minutes=1), version=1,
        )