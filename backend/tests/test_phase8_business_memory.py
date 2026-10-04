"""R112A business observations remain traceable, bounded, and advisory."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from backend.medar.business_memory import BusinessMemory
from backend.medar.durable_memory_record import DurableMemoryDomain, DurableSensitivity


NOW = datetime(2026, 10, 4, 12, tzinfo=timezone.utc)


def _memory(**changes):
    values = dict(
        tenant_id="tenant-a", owner_id="owner-a", session_id="session-a",
        company_reference="synthetic-company", source_reference="synthetic-report-1",
        dataset_reference="synthetic-kpis-1", goal="synthetic growth goal",
        kpi_name="synthetic retention", kpi_value=Decimal("0.81"), kpi_unit="fraction",
        strategy="test strategy", decision="hold", result="no action taken", observed_at=NOW,
    )
    values.update(changes)
    return BusinessMemory(**values)


def test_business_memory_tracks_goal_kpi_strategy_decision_result_without_authority():
    memory = _memory()
    assert memory.domain is DurableMemoryDomain.BUSINESS
    assert memory.sensitivity is DurableSensitivity.SENSITIVE
    assert memory.kpi_value == Decimal("0.81")
    assert memory.dataset_reference == "synthetic-kpis-1"
    assert memory.session_only and memory.analysis_only
    assert not memory.business_action_authority and not memory.trading_authority
    assert memory.goal not in repr(memory)


@pytest.mark.parametrize("change", [
    {"source_reference": ""}, {"dataset_reference": ""},
    {"kpi_value": float("nan")}, {"kpi_value": Decimal("Infinity")},
    {"observed_at": datetime(2026, 10, 4)},
    {"domain": DurableMemoryDomain.MARKETING},
    {"sensitivity": DurableSensitivity.PUBLIC},
    {"session_only": False}, {"analysis_only": False},
    {"business_action_authority": True}, {"trading_authority": True},
])
def test_business_memory_rejects_missing_trace_invalid_kpi_or_authority(change):
    with pytest.raises(ValueError):
        _memory(**change)


def test_business_memory_rejects_secret_like_content():
    with pytest.raises(PermissionError):
        _memory(strategy="api_key: synthetic")
