"""F103C: stale quotes never enter cross-venue spread calculations."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from backend.financial.crypto_asset import CryptoAssetIdentity, CryptoAssetKind
from backend.financial.crypto_quote import CryptoVenueQuote
from backend.financial.crypto_scanner import scan_crypto_market
from backend.financial.market_snapshot import MarketSnapshot, SnapshotState

NOW = datetime(2026, 10, 4, tzinfo=timezone.utc)
ASSET = CryptoAssetIdentity("BTC:BITCOIN/USD", "BTC", "USD", "BITCOIN", CryptoAssetKind.NATIVE)


def quote(venue, bid, ask, timestamp=NOW):
    return CryptoVenueQuote(ASSET, venue, MarketSnapshot(
        ASSET.asset_id, f"synthetic:{venue}", timestamp,
        bid=Decimal(bid), ask=Decimal(ask), last=Decimal(bid),
    ))


def test_scanner_uses_only_fresh_quotes_and_keeps_sources():
    result = scan_crypto_market((quote("COINBASE", "100", "101"),
                                 quote("KRAKEN", "103", "104")), NOW, timedelta(seconds=30))
    assert result.cross_venue_spread == Decimal("2")
    assert result.price_dispersion == Decimal("3")
    assert result.venues[0].source == "synthetic:COINBASE"
    assert result.analysis_only
    stale = scan_crypto_market((quote("COINBASE", "100", "101"),
                                quote("KRAKEN", "103", "104", NOW - timedelta(minutes=1))),
                               NOW, timedelta(seconds=30))
    assert stale.cross_venue_spread is None
    assert stale.venues[1].quote_state is SnapshotState.STALE


def test_scanner_rejects_duplicate_venue():
    with pytest.raises(ValueError, match="unique venues"):
        scan_crypto_market((quote("COINBASE", "100", "101"),
                            quote("COINBASE", "100", "101")), NOW, timedelta(seconds=30))
