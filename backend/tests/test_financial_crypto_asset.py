"""F103A: ticker alone never identifies a crypto chain or token."""

import pytest

from backend.financial.crypto_asset import CryptoAssetIdentity, CryptoAssetKind, StablecoinStatus


def test_same_ticker_on_different_networks_has_distinct_identity():
    a = CryptoAssetIdentity("USDC:ETHEREUM/USD", "USDC", "USD", "ETHEREUM", CryptoAssetKind.TOKEN, "0xabc")
    b = CryptoAssetIdentity("USDC:SOLANA/USD", "USDC", "USD", "SOLANA", CryptoAssetKind.TOKEN, "Soabc")
    assert a.base == b.base and a.asset_id != b.asset_id
    assert a.stablecoin_status is StablecoinStatus.UNKNOWN


def test_token_without_network_or_contract_is_rejected():
    with pytest.raises(ValueError, match="network"):
        CryptoAssetIdentity("X/USD", "X", "USD", None, CryptoAssetKind.TOKEN, "0xabc")
    with pytest.raises(ValueError, match="contract"):
        CryptoAssetIdentity("X/USD", "X", "USD", "ETHEREUM", CryptoAssetKind.TOKEN)
    with pytest.raises(ValueError, match="source"):
        CryptoAssetIdentity("BTC/USD", "BTC", "USD", "BITCOIN", CryptoAssetKind.NATIVE,
                            venue_support=("COINBASE",))
