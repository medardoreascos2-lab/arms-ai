"""F101C: ETF coverage and source-backed characteristics."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from backend.financial.etf import EtfHolding, EtfIntelligence

NOW = datetime(2026, 10, 4, tzinfo=timezone.utc)


def test_partial_holdings_are_not_presented_as_complete():
    etf = EtfIntelligence(
        "ARCA:TEST", "synthetic:holdings", NOW,
        (EtfHolding("NASDAQ:A", Decimal("0.3")), EtfHolding("NASDAQ:B", Decimal("0.2"))),
        {"Technology": Decimal("0.4")},
    )
    assert etf.holdings_coverage == Decimal("0.5")
    assert etf.known_top_holding_weight == Decimal("0.3")
    assert etf.expense_ratio is None
    assert etf.tracking_error is None


def test_invalid_weights_or_duplicate_holdings_rejected():
    with pytest.raises(ValueError, match="exceed"):
        EtfIntelligence("ARCA:TEST", "synthetic:holdings", NOW,
                        (EtfHolding("NASDAQ:A", Decimal("0.6")),
                         EtfHolding("NASDAQ:B", Decimal("0.5"))))
    with pytest.raises(ValueError, match="duplicate"):
        EtfIntelligence("ARCA:TEST", "synthetic:holdings", NOW,
                        (EtfHolding("NASDAQ:A", Decimal("0.2")),
                         EtfHolding("NASDAQ:A", Decimal("0.2"))))
