"""F104A: gross spread is never mislabeled as net opportunity."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from backend.financial.cross_exchange import analyze_cross_exchange
from backend.financial.crypto_asset import CryptoAssetIdentity, CryptoAssetKind
from backend.financial.crypto_quote import CryptoVenueQuote
from backend.financial.market_snapshot import MarketSnapshot

NOW = datetime(2026, 10, 4, tzinfo=timezone.utc)
ASSET = CryptoAssetIdentity("BTC:BITCOIN/USD", "BTC", "USD", "BITCOIN", CryptoAssetKind.NATIVE)


def quote(venue, bid, ask, timestamp=NOW):
    return CryptoVenueQuote(
        ASSET, venue, MarketSnapshot(ASSET.asset_id, f"synthetic:{venue}", timestamp,
                                    bid=Decimal(bid), ask=Decimal(ask)),
        buy_fee_rate=Decimal("0.01"), sell_fee_rate=Decimal("0.01"),
        withdraw_fee_quote=Decimal("1"),
    )


def analyze(buy, sell):
    return analyze_cross_exchange(
        buy, sell, Decimal("1"), NOW, timedelta(seconds=30),
        network_fee_quote=Decimal("1"), slippage_quote=Decimal("1"),
        liquidity_cost_quote=Decimal("1"), latency_penalty_quote=Decimal("1"),
    )


def test_positive_gross_can_have_negative_net_after_all_costs():
    result = analyze(quote("COINBASE", "99", "100"), quote("KRAKEN", "103", "104"))
    assert result.gross_spread_quote == Decimal("3")
    assert result.costs.total == Decimal("7.03")
    assert result.net_expected_edge_quote == Decimal("-4.03")
    assert result.analysis_only
    assert not hasattr(result, "execute")


def test_stale_quote_or_unknown_fee_rejected():
    with pytest.raises(ValueError, match="fresh"):
        analyze(quote("COINBASE", "99", "100", NOW - timedelta(minutes=1)),
                quote("KRAKEN", "103", "104"))
    buy = CryptoVenueQuote(ASSET, "COINBASE", MarketSnapshot(
        ASSET.asset_id, "synthetic:COINBASE", NOW, bid=Decimal("99"), ask=Decimal("100")))
    with pytest.raises(ValueError, match="fees"):
        analyze(buy, quote("KRAKEN", "103", "104"))
