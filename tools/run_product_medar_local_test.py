"""Run Product MEDAR synthetic preview on loopback only.

Usage:
  PRODUCT_MEDAR_LOCAL_TEST_ENABLED=true
  PRODUCT_MEDAR_ENVIRONMENT=LOCAL
  python -m tools.run_product_medar_local_test
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os

import uvicorn

from backend.api.product_medar_local_test import (
    ProductMedarLocalTestConfig,
    create_local_test_product_medar_app,
)
from backend.entitlements import (
    AccountEntitlementLimits, DashboardAccess, FeatureEntitlement,
    SignalEntitlementLimits,
)
from backend.medar.core import MedarCognitiveCore
from backend.memberships import MembershipPlan, MembershipRecord, MembershipStatus
from backend.product.customer_session import (
    LocalSyntheticSessionProvider, synthetic_customer_session,
)
from backend.product.medar_adapter import CanonicalCoreProductRuntime


class SyntheticMembershipAdapter:
    def __init__(self, record: MembershipRecord) -> None:
        self._record = record

    def get_membership(self, tenant_id: str, user_id: str) -> MembershipRecord | None:
        if (tenant_id, user_id) != (self._record.tenant_id, self._record.user_id):
            return None
        return self._record


def build_local_test_app(
    config: ProductMedarLocalTestConfig,
    *, at: datetime | None = None,
):
    if not config.enabled:
        return create_local_test_product_medar_app(config=config)
    now = at or datetime.now(timezone.utc)
    session = synthetic_customer_session(
        issued_at=now - timedelta(minutes=1),
        expires_at=now + timedelta(hours=8),
    )
    plan = MembershipPlan(
        plan_id="PREMIUM", version="LOCAL_TEST_ONLY",
        features=frozenset({
            FeatureEntitlement.DASHBOARD,
            FeatureEntitlement.MEDAR_CONVERSATION,
        }),
        account_limits=AccountEntitlementLimits(0, 0),
        signal_limits=SignalEntitlementLimits(0),
        dashboard_access=DashboardAccess.READ_ONLY,
    )
    membership = MembershipRecord(
        membership_id="synthetic-membership-1",
        tenant_id=session.tenant_id, user_id=session.user_id,
        plan=plan, status=MembershipStatus.ACTIVE,
        effective_from=now - timedelta(days=1),
        effective_until=now + timedelta(hours=8),
        grace_ends_at=now + timedelta(hours=8),
    )
    return create_local_test_product_medar_app(
        config=config,
        session_provider=LocalSyntheticSessionProvider((session,)),
        membership_adapter=SyntheticMembershipAdapter(membership),
        runtime=CanonicalCoreProductRuntime(MedarCognitiveCore()),
    )


if __name__ == "__main__":
    configuration = ProductMedarLocalTestConfig.from_environment(os.environ)
    if not configuration.enabled:
        raise SystemExit("Set PRODUCT_MEDAR_LOCAL_TEST_ENABLED=true and PRODUCT_MEDAR_ENVIRONMENT=LOCAL")
    uvicorn.run(build_local_test_app(configuration), host="127.0.0.1", port=8001)
