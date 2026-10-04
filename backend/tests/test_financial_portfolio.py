"""F102A: portfolio valuation never substitutes missing prices or FX."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from backend.financial.asset import AssetType
from backend.financial.portfolio import PortfolioPosition, PortfolioSnapshot

NOW = datetime(2026, 10, 4, tzinfo=timezone.utc)


def position(price=None, currency="USD"):
    return PortfolioPosition("NASDAQ:TEST", AssetType.STOCK, currency,
                             Decimal("2"), Decimal("10"), price)


def test_known_valuation_and_allocation_are_derived_without_mutation():
    portfolio = PortfolioSnapshot("synthetic:p", "USD", "synthetic:positions", NOW,
                                  (position(Decimal("6")),), {"USD": Decimal("8")})
    assert portfolio.current_value == Decimal("20")
    assert portfolio.unrealized_pnl == Decimal("2")
    assert portfolio.allocation()["NASDAQ:TEST"] == Decimal("0.6")
    assert portfolio.realized_pnl is None


def test_missing_price_and_fx_fail_closed():
    portfolio = PortfolioSnapshot("synthetic:p", "USD", "synthetic:positions", NOW,
                                  (position(),), {"USD": Decimal("8")})
    assert portfolio.current_value is None
    assert portfolio.unrealized_pnl is None
    assert portfolio.allocation() is None
    with pytest.raises(ValueError, match="cross-currency"):
        PortfolioSnapshot("synthetic:p", "USD", "synthetic:positions", NOW,
                          (position(Decimal("6"), "EUR"),))
