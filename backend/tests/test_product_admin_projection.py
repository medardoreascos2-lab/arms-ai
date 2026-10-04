"""P116A read-only Product admin projection tests."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from backend.product.admin_projection import (
    FeatureUsageAggregate,
    MembershipStateAggregate,
    ProductAdminAlert,
    ReadOnlyProductAdminProjection,
    ServiceHealthAggregate,
)


NOW = datetime(2026, 10, 4, tzinfo=timezone.utc)


def projection():
    return ReadOnlyProductAdminProjection(
        generated_at=NOW,
        beta_user_count=12,
        membership_states=(MembershipStateAggregate(status="ACTIVE", count=8),),
        feature_usage=(FeatureUsageAggregate(feature="MEDAR", uses=40, unique_users=9),),
        service_health=(ServiceHealthAggregate(service_id="medar", state="HEALTHY"),),
        alerts=(ProductAdminAlert(alert_reference="capacity-watch", severity="WATCH", category="CAPACITY"),),
    )


def test_admin_projection_contains_required_aggregates_and_is_read_only():
    value = projection()
    assert value.beta_user_count == 12
    assert value.membership_states[0].count == 8
    assert value.feature_usage[0].uses == 40
    assert value.service_health[0].state == "HEALTHY"
    assert value.alerts[0].severity == "WATCH"
    assert value.read_only is True
    assert value.trading_mutation_authorized is False
    assert value.financial_mutation_authorized is False


def test_admin_projection_rejects_mutation_controls_and_private_detail():
    body = projection().model_dump()
    for extra in ("place_order", "change_portfolio", "financial_positions", "conversation_content"):
        with pytest.raises(ValidationError):
            ReadOnlyProductAdminProjection.model_validate({**body, extra: True})
    with pytest.raises(ValidationError):
        ReadOnlyProductAdminProjection.model_validate({**body, "trading_mutation_authorized": True})