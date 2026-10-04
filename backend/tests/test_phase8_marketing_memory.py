"""R112B campaign memory carries metadata without ad spend authority."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from backend.medar.durable_memory_record import DurableMemoryDomain, DurableSensitivity
from backend.medar.marketing_memory import MarketingMemory


NOW = datetime(2026, 10, 4, 12, tzinfo=timezone.utc)


def _memory(**changes):
    values = dict(
        tenant_id="tenant-a", owner_id="owner-a", session_id="session-a",
        campaign_reference="synthetic-campaign-a", source_reference="synthetic-report-1",
        dataset_reference="synthetic-campaign-data-1", audience="synthetic audience",
        creative="synthetic creative", channel="synthetic-channel",
        budget_amount=Decimal("100.00"), budget_currency="USD",
        result="synthetic result", lesson="synthetic lesson", observed_at=NOW,
    )
    values.update(changes)
    return MarketingMemory(**values)


def test_marketing_memory_tracks_campaign_budget_result_and_lesson_without_spend():
    memory = _memory()
    assert memory.domain is DurableMemoryDomain.MARKETING
    assert memory.sensitivity is DurableSensitivity.SENSITIVE
    assert memory.budget_amount == Decimal("100.00")
    assert memory.dataset_reference == "synthetic-campaign-data-1"
    assert memory.session_only and memory.analysis_only
    assert not memory.ad_spend_authority and not memory.campaign_mutation_authority
    assert memory.audience not in repr(memory)


@pytest.mark.parametrize("change", [
    {"source_reference": ""}, {"dataset_reference": ""},
    {"budget_amount": Decimal("-1")}, {"budget_amount": float("nan")},
    {"budget_amount": Decimal("Infinity")},
    {"observed_at": datetime(2026, 10, 4)},
    {"domain": DurableMemoryDomain.BUSINESS},
    {"sensitivity": DurableSensitivity.PUBLIC},
    {"session_only": False}, {"analysis_only": False},
    {"ad_spend_authority": True}, {"campaign_mutation_authority": True},
])
def test_marketing_memory_rejects_missing_trace_invalid_budget_or_authority(change):
    with pytest.raises(ValueError):
        _memory(**change)


def test_marketing_memory_rejects_secret_like_content():
    with pytest.raises(PermissionError):
        _memory(creative="api_key: synthetic")
