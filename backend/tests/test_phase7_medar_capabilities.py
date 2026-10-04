"""R81B MEDAR capability registry tests."""

import pytest

from backend.medar.capabilities import (
    Capability,
    CapabilityRegistry,
    MemoryPermission,
    default_capability_registry,
)
from backend.medar.request import CognitiveDomain, RiskClass


def test_default_registry_covers_safe_initial_capabilities_without_execution_authority():
    registry = default_capability_registry()

    assert registry.get("web_search").tool_requirements == ("web_search_stub",)
    assert registry.get("portfolio_analysis").confirmation_required is True
    assert all(item.execution_authority is False for item in registry.capabilities)
    assert registry.for_domain(CognitiveDomain.TRADING)[0].capability_id == "trading_analysis"


def test_unknown_capability_fails_closed():
    with pytest.raises(KeyError, match="unsupported capability"):
        default_capability_registry().get("broker_execution")


def test_high_risk_capability_requires_confirmation():
    with pytest.raises(ValueError, match="requires confirmation"):
        Capability(
            "unsafe",
            CognitiveDomain.FINANCIAL,
            "unsafe capability",
            RiskClass.HIGH,
            (),
            (MemoryPermission.NONE,),
            False,
        )


def test_duplicate_capability_is_rejected():
    item = Capability(
        "same",
        CognitiveDomain.GENERAL,
        "bounded analysis",
        RiskClass.LOW,
        (),
        (MemoryPermission.NONE,),
        False,
    )
    with pytest.raises(ValueError, match="duplicate"):
        CapabilityRegistry((item, item))
