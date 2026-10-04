"""R111D crypto research tracks evidence without exchange execution."""

from datetime import datetime, timezone

import pytest

from backend.medar.crypto_research_memory import CryptoEvidenceMode, CryptoResearchMemory
from backend.medar.durable_memory_record import DurableMemoryDomain, DurableSensitivity


NOW = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)


def _memory(**changes):
    values = dict(
        tenant_id="tenant-a", owner_id="owner-a", session_id="session-a",
        asset_symbol="BTC", exchange_reference="synthetic-exchange-a",
        source_reference="synthetic-study-1", dataset_reference="synthetic-quotes-1",
        evidence_mode=CryptoEvidenceMode.SYNTHETIC_TEST,
        asset_research="synthetic asset observation", exchange_observation="synthetic bid/ask observation",
        fee_assumption="synthetic fee schedule", network_condition="synthetic network condition",
        arbitrage_opportunity="unverified hypothetical spread", paper_outcome="no paper fill observed",
        observed_at=NOW,
    )
    values.update(changes)
    return CryptoResearchMemory(**values)


def test_crypto_research_keeps_all_observations_session_only():
    memory = _memory()
    assert memory.domain is DurableMemoryDomain.CRYPTO
    assert memory.sensitivity is DurableSensitivity.SENSITIVE
    assert memory.evidence_mode is CryptoEvidenceMode.SYNTHETIC_TEST
    assert memory.dataset_reference == "synthetic-quotes-1"
    assert memory.session_only and memory.analysis_only
    assert not memory.exchange_execution_authority
    assert not memory.paper_execution_authority
    assert not memory.live_execution_authority
    assert memory.asset_research not in repr(memory)


@pytest.mark.parametrize("change", [
    {"source_reference": ""}, {"dataset_reference": ""},
    {"observed_at": datetime(2026, 10, 3)},
    {"domain": DurableMemoryDomain.CRYPTO_ARBITRAGE},
    {"sensitivity": DurableSensitivity.PUBLIC},
    {"session_only": False}, {"analysis_only": False},
    {"exchange_execution_authority": True}, {"paper_execution_authority": True},
    {"live_execution_authority": True},
])
def test_crypto_research_rejects_missing_trace_or_execution_authority(change):
    with pytest.raises(ValueError):
        _memory(**change)


def test_crypto_research_rejects_secret_like_content():
    with pytest.raises(PermissionError):
        _memory(exchange_observation="api_key: synthetic")
