"""Cross-exchange spread analysis with complete, explicit quote-currency costs."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from backend.financial.crypto_quote import CryptoVenueQuote
from backend.financial.market_snapshot import SnapshotState


@dataclass(frozen=True)
class ArbitrageCosts:
    buy_fee: Decimal
    sell_fee: Decimal
    withdraw_fee: Decimal
    network_fee: Decimal
    slippage: Decimal
    liquidity_cost: Decimal
    latency_penalty: Decimal

    @property
    def total(self) -> Decimal:
        return sum((
            self.buy_fee, self.sell_fee, self.withdraw_fee, self.network_fee,
            self.slippage, self.liquidity_cost, self.latency_penalty,
        ), Decimal(0))


@dataclass(frozen=True)
class CrossExchangeOpportunity:
    asset_id: str
    buy_venue: str
    sell_venue: str
    size_base: Decimal
    gross_spread_quote: Decimal
    costs: ArbitrageCosts
    net_expected_edge_quote: Decimal
    quote_currency: str
    buy_source: str
    sell_source: str
    analysis_only: bool = True


def analyze_cross_exchange(
    buy: CryptoVenueQuote,
    sell: CryptoVenueQuote,
    size_base: Decimal,
    now: datetime,
    maximum_age: timedelta,
    *,
    network_fee_quote: Decimal,
    slippage_quote: Decimal,
    liquidity_cost_quote: Decimal,
    latency_penalty_quote: Decimal,
) -> CrossExchangeOpportunity:
    if buy.asset.asset_id != sell.asset.asset_id or buy.venue_id == sell.venue_id:
        raise ValueError("opportunity requires one asset on distinct venues")
    if buy.snapshot.freshness(now, maximum_age) is not SnapshotState.FRESH or sell.snapshot.freshness(now, maximum_age) is not SnapshotState.FRESH:
        raise ValueError("both quotes must be fresh and complete")
    if not isinstance(size_base, Decimal) or not size_base.is_finite() or size_base <= 0:
        raise ValueError("size_base must be positive and finite")
    if buy.buy_fee_rate is None or sell.sell_fee_rate is None or buy.withdraw_fee_quote is None:
        raise ValueError("explicit venue fees are required")
    extras = (network_fee_quote, slippage_quote, liquidity_cost_quote, latency_penalty_quote)
    if any(not isinstance(cost, Decimal) or not cost.is_finite() or cost < 0 for cost in extras):
        raise ValueError("all estimated costs must be nonnegative and finite")
    costs = ArbitrageCosts(
        buy.snapshot.ask * size_base * buy.buy_fee_rate,
        sell.snapshot.bid * size_base * sell.sell_fee_rate,
        buy.withdraw_fee_quote,
        *extras,
    )
    gross = (sell.snapshot.bid - buy.snapshot.ask) * size_base
    return CrossExchangeOpportunity(
        buy.asset.asset_id, buy.venue_id, sell.venue_id, size_base,
        gross, costs, gross - costs.total, buy.asset.quote,
        buy.snapshot.source, sell.snapshot.source,
    )
