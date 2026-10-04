"""F102D: rebalance scenarios have no execution authority."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from backend.financial.asset import AssetType
from backend.financial.portfolio import PortfolioPosition, PortfolioSnapshot
from backend.financial.rebalance import propose_rebalance

NOW = datetime(2026, 10, 4, tzinfo=timezone.utc)


def test_rebalance_is_explicitly_hypothetical_and_does_not_mutate_snapshot():
    portfolio = PortfolioSnapshot(
        "synthetic:p", "USD", "synthetic:positions", NOW,
        (PortfolioPosition("A", AssetType.STOCK, "USD", Decimal("1"), Decimal("50"), Decimal("60")),),
        {"USD": Decimal("40")},
    )
    target = {"A": Decimal("0.5"), "CASH": Decimal("0.5")}
    scenario = propose_rebalance(portfolio, target, Decimal("0.01"))
    assert scenario.label == "HYPOTHETICAL"
    assert scenario.before["A"] == Decimal("0.6")
    assert scenario.after["A"] == Decimal("0.5")
    assert scenario.trades[0].label == "HYPOTHETICAL"
    assert scenario.trades[0].value_delta == Decimal("-10")
    assert scenario.estimated_cost == Decimal("0.10")
    assert scenario.estimated_value_impact == Decimal("-0.10")
    assert portfolio.positions[0].quantity == Decimal("1")
    assert portfolio.cash["USD"] == Decimal("40")
    assert not hasattr(scenario, "execute")


def test_rebalance_rejects_incomplete_valuation():
    portfolio = PortfolioSnapshot(
        "synthetic:p", "USD", "synthetic:positions", NOW,
        (PortfolioPosition("A", AssetType.STOCK, "USD", Decimal("1"), Decimal("50")),),
    )
    with pytest.raises(ValueError, match="complete"):
        propose_rebalance(portfolio, {"A": Decimal("1"), "CASH": Decimal("0")}, Decimal("0"))
