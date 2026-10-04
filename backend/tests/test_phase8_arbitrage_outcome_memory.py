"""R111E tests cost-complete arbitrage outcome calculations and authority bounds."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from backend.medar.arbitrage_outcome_memory import ArbitrageOutcomeMemory, PaperResultMode
from backend.medar.durable_memory_record import DurableMemoryDomain, DurableSensitivity


NOW = datetime(2026, 10, 4, 12, tzinfo=timezone.utc)


def _memory(**changes):
    values = dict(
        tenant_id="tenant-a", owner_id="owner-a", session_id="session-a",
        source_reference="synthetic-scan-1", dataset_reference="synthetic-quotes-1",
        opportunity_reference="synthetic-opportunity-1", measurement_currency="USD",
        gross_spread=Decimal("10.00"), fee_cost=Decimal("3.00"),
        slippage_cost=Decimal("2.50"), network_cost=Decimal("1.00"),
        liquidity_cost=Decimal("4.00"), paper_result_mode=PaperResultMode.NO_PAPER_FILL,
        paper_result="no paper fill observed", observed_at=NOW,
    )
    values.update(changes)
    return ArbitrageOutcomeMemory(**values)


def test_positive_gross_spread_is_not_profit_when_total_cost_exceeds_it():
    memory = _memory()
    assert memory.gross_spread == Decimal("10.00")
    assert memory.net_edge == Decimal("-0.50")
    assert not memory.profitable_on_stated_costs
    assert memory.paper_result_mode is PaperResultMode.NO_PAPER_FILL
    assert memory.domain is DurableMemoryDomain.CRYPTO_ARBITRAGE
    assert memory.sensitivity is DurableSensitivity.SENSITIVE
    assert memory.session_only and memory.analysis_only
    assert not memory.exchange_execution_authority
    assert not memory.paper_execution_authority
    assert not memory.live_execution_authority
    assert memory.paper_result not in repr(memory)


def test_each_cost_affects_net_edge_without_float_rounding():
    memory = _memory(liquidity_cost=Decimal("1.00"))
    assert memory.net_edge == Decimal("2.50")
    assert memory.profitable_on_stated_costs
    assert _memory(gross_spread=Decimal("6.50"), liquidity_cost=Decimal("0")).net_edge == Decimal("0.00")


@pytest.mark.parametrize("change", [
    {"fee_cost": Decimal("-1")}, {"network_cost": Decimal("NaN")},
    {"slippage_cost": 1.0}, {"liquidity_cost": Decimal("Infinity")},
    {"source_reference": ""}, {"dataset_reference": ""},
    {"observed_at": datetime(2026, 10, 4)},
    {"domain": DurableMemoryDomain.CRYPTO},
    {"sensitivity": DurableSensitivity.PUBLIC},
    {"session_only": False}, {"analysis_only": False},
    {"exchange_execution_authority": True}, {"paper_execution_authority": True},
    {"live_execution_authority": True},
])
def test_invalid_cost_trace_or_authority_is_rejected(change):
    with pytest.raises(ValueError):
        _memory(**change)


def test_paper_result_evidence_mode_and_secret_screen_are_enforced():
    with pytest.raises(TypeError):
        _memory(paper_result_mode="PAPER_OBSERVED")
    with pytest.raises(PermissionError):
        _memory(paper_result="api_key: synthetic")
