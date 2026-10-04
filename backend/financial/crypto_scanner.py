"""Pure multi-venue crypto market scanner over supplied quote snapshots."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from backend.financial.crypto_quote import CryptoVenueQuote
from backend.financial.market_snapshot import SnapshotState


@dataclass(frozen=True)
class VenueScan:
    venue_id: str
    quote_state: SnapshotState
    bid: Decimal | None
    ask: Decimal | None
    bid_depth_base: Decimal | None
    ask_depth_base: Decimal | None
    source: str


@dataclass(frozen=True)
class CryptoScanResult:
    asset_id: str
    venues: tuple[VenueScan, ...]
    price_dispersion: Decimal | None
    cross_venue_spread: Decimal | None
    analysis_only: bool = True


def scan_crypto_market(
    quotes: tuple[CryptoVenueQuote, ...], now: datetime, maximum_age: timedelta,
) -> CryptoScanResult:
    if not quotes:
        raise ValueError("at least one quote is required")
    asset_ids = {q.asset.asset_id for q in quotes}
    if len(asset_ids) != 1 or len({q.venue_id for q in quotes}) != len(quotes):
        raise ValueError("scan requires one asset and unique venues")
    rows = []
    fresh = []
    for quote in quotes:
        state = quote.snapshot.freshness(now, maximum_age)
        rows.append(VenueScan(
            quote.venue_id, state, quote.snapshot.bid, quote.snapshot.ask,
            quote.bid_depth_base, quote.ask_depth_base, quote.snapshot.source,
        ))
        if state is SnapshotState.FRESH:
            fresh.append(quote)
    dispersion = None
    spread = None
    if len(fresh) >= 2:
        last_prices = [q.snapshot.last for q in fresh]
        if all(price is not None for price in last_prices):
            dispersion = max(last_prices) - min(last_prices)
        spread = max(q.snapshot.bid for q in fresh) - min(q.snapshot.ask for q in fresh)
    return CryptoScanResult(next(iter(asset_ids)), tuple(rows), dispersion, spread)
