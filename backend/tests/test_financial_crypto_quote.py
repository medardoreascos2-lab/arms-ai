"""F103B: crypto venue quotes retain unknown fees, depth and transfer status."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from backend.financial.crypto_asset import CryptoAssetIdentity, CryptoAssetKind
from backend.financial.crypto_quote import CryptoVenueQuote, TransferStatus
from backend.financial.market_snapshot import MarketSnapshot

NOW = datetime(2026, 10, 4, tzinfo=timezone.utc)
ASSET = CryptoAssetIdentity("BTC:BITCOIN/USD", "BTC", "USD", "BITCOIN", CryptoAssetKind.NATIVE)


def test_quote_unknowns_are_explicit_and_not_executable():
    quote = CryptoVenueQuote(ASSET, "COINBASE",
                             MarketSnapshot(ASSET.asset_id, "synthetic:quote", NOW,
                                            bid=Decimal("100"), ask=Decimal("101")))
    assert quote.buy_fee_rate is None
    assert quote.deposit_status is TransferStatus.UNKNOWN
    assert quote.ask_depth_base is None
    assert not hasattr(quote, "submit_order")


def test_quote_rejects_mismatched_identity_or_invalid_fee():
    with pytest.raises(ValueError, match="identity mismatch"):
        CryptoVenueQuote(ASSET, "COINBASE", MarketSnapshot("OTHER", "synthetic:quote", NOW))
    with pytest.raises(ValueError, match="fee_rate"):
        CryptoVenueQuote(ASSET, "COINBASE", MarketSnapshot(ASSET.asset_id, "synthetic:quote", NOW),
                         buy_fee_rate=Decimal("NaN"))
