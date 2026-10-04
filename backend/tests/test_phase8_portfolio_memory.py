"""R111C portfolio evidence is analysis-only and nonmutating."""

from datetime import datetime, timezone

import pytest

from backend.medar.durable_memory_record import DurableMemoryDomain, DurableSensitivity
from backend.medar.portfolio_memory import PortfolioEvidenceMode, PortfolioMemory


NOW = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)


def _memory(**changes):
    values = dict(
        tenant_id="tenant-a", owner_id="owner-a", session_id="session-a",
        portfolio_reference="synthetic-portfolio-a", source_reference="synthetic-study-1",
        dataset_reference="synthetic-positions-1", evidence_mode=PortfolioEvidenceMode.SYNTHETIC_TEST,
        thesis="synthetic diversification thesis", risk_observation="synthetic concentration risk",
        allocation_decision="hold synthetic weights", rebalance_proposal="propose no change",
        outcome="no portfolio mutation", observed_at=NOW,
    )
    values.update(changes)
    return PortfolioMemory(**values)


def test_portfolio_memory_tracks_fields_without_mutation_authority():
    memory = _memory()
    assert memory.domain is DurableMemoryDomain.PORTFOLIO
    assert memory.sensitivity is DurableSensitivity.SENSITIVE
    assert memory.dataset_reference == "synthetic-positions-1"
    assert memory.evidence_mode is PortfolioEvidenceMode.SYNTHETIC_TEST
    assert memory.analysis_only and memory.session_only
    assert not memory.portfolio_mutation_authority and not memory.trading_authority
    assert memory.thesis not in repr(memory)


def test_portfolio_memory_rejects_missing_trace_or_authority_claim():
    with pytest.raises(ValueError):
        _memory(source_reference="")
    with pytest.raises(PermissionError):
        _memory(outcome="api_key: synthetic")
    with pytest.raises(ValueError):
        _memory(portfolio_mutation_authority=True)
    with pytest.raises(ValueError):
        _memory(domain=DurableMemoryDomain.FINANCIAL)
