"""F104B: missing depth and transfer information never passes checks."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from backend.financial.cross_exchange import analyze_cross_exchange
from backend.financial.crypto_asset import CryptoAssetIdentity, CryptoAssetKind
from backend.financial.crypto_quote import CryptoVenueQuote, TransferStatus
from backend.financial.executability import ExecutabilityClass, assess_executability
from backend.financial.market_snapshot import MarketSnapshot

NOW = datetime(2026, 10, 4, tzinfo=timezone.utc)
AGE = timedelta(seconds=30)
ASSET = CryptoAssetIdentity("BTC:BITCOIN/USD", "BTC", "USD", "BITCOIN", CryptoAssetKind.NATIVE)


def quote(venue, bid, ask, *, complete=False):
    return CryptoVenueQuote(
        ASSET, venue, MarketSnapshot(ASSET.asset_id, f"synthetic:{venue}", NOW,
                                    bid=Decimal(bid), ask=Decimal(ask)),
        bid_depth_base=Decimal("2") if complete else None,
        ask_depth_base=Decimal("2") if complete else None,
        buy_fee_rate=Decimal("0"), sell_fee_rate=Decimal("0"),
        withdraw_fee_quote=Decimal("0"),
        withdraw_status=TransferStatus.AVAILABLE if complete else TransferStatus.UNKNOWN,
        deposit_status=TransferStatus.AVAILABLE if complete else TransferStatus.UNKNOWN,
        transfer_network="BITCOIN" if complete else None,
    )


def opportunity(buy, sell):
    return analyze_cross_exchange(
        buy, sell, Decimal("1"), NOW, AGE,
        network_fee_quote=Decimal("0"), slippage_quote=Decimal("0"),
        liquidity_cost_quote=Decimal("0"), latency_penalty_quote=Decimal("0"),
    )


def test_unknown_operational_data_cannot_be_actionable():
    buy, sell = quote("COINBASE", "99", "100"), quote("KRAKEN", "102", "103")
    result = assess_executability(opportunity(buy, sell), buy, sell, NOW, AGE, Decimal("1"))
    assert result.classification is ExecutabilityClass.INCOMPLETE_DATA
    assert not result.paper_execution_authority


def test_complete_paper_candidate_and_threshold_watch_are_advisory_only():
    buy, sell = quote("COINBASE", "99", "100", complete=True), quote("KRAKEN", "102", "103", complete=True)
    candidate = assess_executability(opportunity(buy, sell), buy, sell, NOW, AGE, Decimal("1"))
    assert candidate.classification is ExecutabilityClass.ACTIONABLE_PAPER
    assert candidate.analysis_only and not candidate.paper_execution_authority
    watch = assess_executability(opportunity(buy, sell), buy, sell, NOW, AGE, Decimal("3"))
    assert watch.classification is ExecutabilityClass.WATCH


def test_insufficient_depth_blocks_even_with_positive_net():
    buy, sell = quote("COINBASE", "99", "100", complete=True), quote("KRAKEN", "102", "103", complete=True)
    buy = replace(buy, ask_depth_base=Decimal("0.5"))
    result = assess_executability(opportunity(buy, sell), buy, sell, NOW, AGE, Decimal("1"))
    assert result.classification is ExecutabilityClass.NOT_ACTIONABLE
    assert "INSUFFICIENT_DEPTH" in result.reasons

