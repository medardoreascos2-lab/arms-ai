"""R89C MEDAR crypto arbitrage capability seam tests."""

from decimal import Decimal

import pytest

from backend.medar.crypto_arbitrage import ArbitrageCosts, ExchangeQuote, analyze_opportunity


def test_arbitrage_analysis_includes_fees_slippage_liquidity_network_and_net_edge():
    buy = ExchangeQuote("A", "BTC", Decimal("99"), Decimal("100"), Decimal("3"))
    sell = ExchangeQuote("B", "BTC", Decimal("104"), Decimal("105"), Decimal("2"))
    costs = ArbitrageCosts(Decimal("1"), Decimal("0.5"), Decimal("0.25"))
    result = analyze_opportunity(buy, sell, costs)
    assert result.gross_edge == Decimal("4")
    assert result.costs.total == Decimal("1.75")
    assert result.net_edge == Decimal("2.25")
    assert result.buy_quote.available_liquidity == Decimal("3")
    assert result.executable is False


def test_arbitrage_analysis_rejects_same_exchange_or_different_asset():
    quote = ExchangeQuote("A", "BTC", Decimal("99"), Decimal("100"), Decimal("3"))
    costs = ArbitrageCosts(Decimal("0"), Decimal("0"), Decimal("0"))
    with pytest.raises(ValueError, match="distinct"):
        analyze_opportunity(quote, quote, costs)
    other = ExchangeQuote("B", "ETH", Decimal("99"), Decimal("100"), Decimal("3"))
    with pytest.raises(ValueError, match="one asset"):
        analyze_opportunity(quote, other, costs)
