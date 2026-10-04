"""Paper-candidate classification only; never confers PAPER execution authority."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum

from backend.financial.cross_exchange import CrossExchangeOpportunity
from backend.financial.crypto_quote import CryptoVenueQuote, TransferStatus
from backend.financial.market_snapshot import SnapshotState


class ExecutabilityClass(str, Enum):
    ACTIONABLE_PAPER = "ACTIONABLE_PAPER"
    WATCH = "WATCH"
    NOT_ACTIONABLE = "NOT_ACTIONABLE"
    INCOMPLETE_DATA = "INCOMPLETE_DATA"


@dataclass(frozen=True)
class ExecutabilityAssessment:
    classification: ExecutabilityClass
    reasons: tuple[str, ...]
    analysis_only: bool = True
    paper_execution_authority: bool = False


def assess_executability(
    opportunity: CrossExchangeOpportunity,
    buy: CryptoVenueQuote,
    sell: CryptoVenueQuote,
    now: datetime,
    maximum_age: timedelta,
    minimum_net_edge_quote: Decimal,
) -> ExecutabilityAssessment:
    if (
        opportunity.asset_id != buy.asset.asset_id
        or opportunity.asset_id != sell.asset.asset_id
        or opportunity.buy_venue != buy.venue_id
        or opportunity.sell_venue != sell.venue_id
    ):
        raise ValueError("assessment quotes must match opportunity")
    if not isinstance(minimum_net_edge_quote, Decimal) or not minimum_net_edge_quote.is_finite() or minimum_net_edge_quote < 0:
        raise ValueError("minimum net edge must be nonnegative and finite")
    if buy.snapshot.freshness(now, maximum_age) is not SnapshotState.FRESH or sell.snapshot.freshness(now, maximum_age) is not SnapshotState.FRESH:
        return ExecutabilityAssessment(ExecutabilityClass.NOT_ACTIONABLE, ("QUOTE_NOT_FRESH",))
    unknown = []
    blocked = []
    if buy.ask_depth_base is None or sell.bid_depth_base is None:
        unknown.append("DEPTH_UNKNOWN")
    elif buy.ask_depth_base < opportunity.size_base or sell.bid_depth_base < opportunity.size_base:
        blocked.append("INSUFFICIENT_DEPTH")
    if buy.withdraw_status is TransferStatus.UNKNOWN or sell.deposit_status is TransferStatus.UNKNOWN:
        unknown.append("TRANSFER_STATUS_UNKNOWN")
    elif buy.withdraw_status is TransferStatus.UNAVAILABLE or sell.deposit_status is TransferStatus.UNAVAILABLE:
        blocked.append("TRANSFER_UNAVAILABLE")
    if buy.transfer_network is None or sell.transfer_network is None:
        unknown.append("NETWORK_UNKNOWN")
    elif buy.transfer_network != sell.transfer_network:
        blocked.append("NETWORK_MISMATCH")
    if opportunity.net_expected_edge_quote <= 0:
        blocked.append("NONPOSITIVE_NET_EDGE")
    if blocked:
        return ExecutabilityAssessment(ExecutabilityClass.NOT_ACTIONABLE, tuple(blocked + unknown))
    if unknown:
        return ExecutabilityAssessment(ExecutabilityClass.INCOMPLETE_DATA, tuple(unknown))
    if opportunity.net_expected_edge_quote < minimum_net_edge_quote:
        return ExecutabilityAssessment(ExecutabilityClass.WATCH, ("NET_EDGE_BELOW_THRESHOLD",))
    return ExecutabilityAssessment(ExecutabilityClass.ACTIONABLE_PAPER, ("HYPOTHETICAL_PAPER_CANDIDATE",))
