"""F104E: ranking refuses unknown venue risk and stale market evidence."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from backend.financial.arbitrage_ranking import ArbitrageCandidate, VenueRisk, rank_arbitrage
from backend.financial.cross_exchange import analyze_cross_exchange
from backend.financial.crypto_asset import CryptoAssetIdentity, CryptoAssetKind
from backend.financial.crypto_quote import CryptoVenueQuote, TransferStatus
from backend.financial.executability import assess_executability
from backend.financial.market_snapshot import MarketSnapshot

NOW = datetime(2026, 10, 4, tzinfo=timezone.utc)
AGE = timedelta(seconds=30)
ASSET = CryptoAssetIdentity("BTC:BITCOIN/USD", "BTC", "USD", "BITCOIN", CryptoAssetKind.NATIVE)


def quote(venue, bid, ask):
    return CryptoVenueQuote(
        ASSET, venue, MarketSnapshot(ASSET.asset_id, f"synthetic:{venue}", NOW,
                                    bid=Decimal(bid), ask=Decimal(ask)),
        bid_depth_base=Decimal("2"), ask_depth_base=Decimal("2"),
        buy_fee_rate=Decimal("0"), sell_fee_rate=Decimal("0"),
        withdraw_fee_quote=Decimal("0"), deposit_status=TransferStatus.AVAILABLE,
        withdraw_status=TransferStatus.AVAILABLE, transfer_network="BITCOIN",
    )


def candidate(buy_risk):
    buy, sell = quote("COINBASE", "99", "100"), quote("KRAKEN", "103", "104")
    opportunity = analyze_cross_exchange(
        buy, sell, Decimal("1"), NOW, AGE,
        network_fee_quote=Decimal("0"), slippage_quote=Decimal("0"),
        liquidity_cost_quote=Decimal("0"), latency_penalty_quote=Decimal("0"),
    )
    assessment = assess_executability(opportunity, buy, sell, NOW, AGE, Decimal("1"))
    return ArbitrageCandidate(opportunity, assessment, buy, sell, buy_risk, VenueRisk.LOW)


def test_ranking_requires_venue_risk_and_rechecks_freshness():
    unknown = rank_arbitrage((candidate(VenueRisk.UNKNOWN),), NOW, AGE)
    assert not unknown.ranked
    assert unknown.excluded[0][1] == "VENUE_RISK_UNKNOWN"
    ranked = rank_arbitrage((candidate(VenueRisk.MEDIUM),), NOW, AGE)
    assert len(ranked.ranked) == 1
    assert ranked.ranked[0].rank == 1
    assert ranked.ranked[0].analysis_only
    stale = rank_arbitrage((candidate(VenueRisk.MEDIUM),), NOW + timedelta(minutes=1), AGE)
    assert not stale.ranked


def test_forged_paper_assessment_cannot_bypass_transfer_check():
    item = candidate(VenueRisk.LOW)
    item = replace(item, buy_quote=replace(item.buy_quote, transfer_network=None))
    result = rank_arbitrage((item,), NOW, AGE)
    assert not result.ranked
    assert result.excluded[0][1] == "TRANSFER_OR_LIQUIDITY_NOT_VERIFIED"
