"""R94B MEDAR business management contract tests."""

import pytest

from backend.medar.business import BusinessArea, BusinessManagementRequest


def test_business_contract_supports_all_roadmap_areas():
    assert tuple(item.value for item in BusinessArea) == (
        "KPI", "OPERATIONS", "SALES", "COSTS", "STRATEGY", "RISK", "PLANNING",
    )
    request = BusinessManagementRequest(
        "request", "Plan growth", tuple(BusinessArea), {"revenue": 100.0}, ("budget",),
    )
    assert request.advisory_only is True


def test_business_contract_cannot_claim_management_authority():
    with pytest.raises(ValueError, match="advisory"):
        BusinessManagementRequest(
            "request", "goal", (BusinessArea.STRATEGY,), {}, (), advisory_only=False,
        )
