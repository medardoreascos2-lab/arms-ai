"""Rank only fully evidenced, fresh arbitrage paper candidates."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum

from backend.financial.cross_exchange import CrossExchangeOpportunity
from backend.financial.crypto_quote import CryptoVenueQuote
from backend.financial.executability import ExecutabilityAssessment, ExecutabilityClass, assess_executability
from backend.financial.market_snapshot import SnapshotState


class VenueRisk(str, Enum):
    UNKNOWN = "UNKNOWN"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


@dataclass(frozen=True)
class ArbitrageCandidate:
    opportunity: CrossExchangeOpportunity
    assessment: ExecutabilityAssessment
    buy_quote: CryptoVenueQuote
    sell_quote: CryptoVenueQuote
    buy_venue_risk: VenueRisk
    sell_venue_risk: VenueRisk


@dataclass(frozen=True)
class RankedOpportunity:
    rank: int
    opportunity: CrossExchangeOpportunity
    liquidity_headroom_base: Decimal
    highest_venue_risk: VenueRisk
    analysis_only: bool = True


@dataclass(frozen=True)
class RankingResult:
    ranked: tuple[RankedOpportunity, ...]
    excluded: tuple[tuple[str, str], ...]
    analysis_only: bool = True


def rank_arbitrage(
    candidates: tuple[ArbitrageCandidate, ...], now: datetime, maximum_age: timedelta,
) -> RankingResult:
    accepted = []
    excluded = []
    risk_order = {VenueRisk.LOW: 0, VenueRisk.MEDIUM: 1, VenueRisk.HIGH: 2}
    for item in candidates:
        opportunity = item.opportunity
        key = f"{opportunity.asset_id}:{opportunity.buy_venue}:{opportunity.sell_venue}"
        if item.assessment.classification is not ExecutabilityClass.ACTIONABLE_PAPER:
            excluded.append((key, "EXECUTABILITY_NOT_PASSED"))
            continue
        if (
            opportunity.buy_venue != item.buy_quote.venue_id
            or opportunity.sell_venue != item.sell_quote.venue_id
            or opportunity.asset_id != item.buy_quote.asset.asset_id
            or opportunity.asset_id != item.sell_quote.asset.asset_id
        ):
            excluded.append((key, "OPPORTUNITY_QUOTE_MISMATCH"))
            continue
        if assess_executability(
            opportunity, item.buy_quote, item.sell_quote, now, maximum_age, Decimal(0)
        ).classification is not ExecutabilityClass.ACTIONABLE_PAPER:
            excluded.append((key, "TRANSFER_OR_LIQUIDITY_NOT_VERIFIED"))
            continue
        if item.buy_venue_risk is VenueRisk.UNKNOWN or item.sell_venue_risk is VenueRisk.UNKNOWN:
            excluded.append((key, "VENUE_RISK_UNKNOWN"))
            continue
        if opportunity.net_expected_edge_quote <= 0:
            excluded.append((key, "NONPOSITIVE_NET_EDGE"))
            continue
        if (
            item.buy_quote.snapshot.freshness(now, maximum_age) is not SnapshotState.FRESH
            or item.sell_quote.snapshot.freshness(now, maximum_age) is not SnapshotState.FRESH
        ):
            excluded.append((key, "QUOTE_NOT_FRESH"))
            continue
        if (
            item.buy_quote.ask_depth_base is None
            or item.sell_quote.bid_depth_base is None
            or item.buy_quote.ask_depth_base < opportunity.size_base
            or item.sell_quote.bid_depth_base < opportunity.size_base
        ):
            excluded.append((key, "LIQUIDITY_NOT_VERIFIED"))
            continue
        headroom = min(item.buy_quote.ask_depth_base, item.sell_quote.bid_depth_base) - opportunity.size_base
        highest_risk = max((item.buy_venue_risk, item.sell_venue_risk), key=lambda risk: risk_order[risk])
        accepted.append((opportunity, headroom, highest_risk))
    accepted.sort(key=lambda row: (
        -row[0].net_expected_edge_quote,
        risk_order[row[2]],
        -row[1],
    ))
    ranked = tuple(
        RankedOpportunity(index, opportunity, headroom, risk)
        for index, (opportunity, headroom, risk) in enumerate(accepted, 1)
    )
    return RankingResult(ranked, tuple(excluded))
