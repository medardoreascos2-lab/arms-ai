"""Analysis-only capability seam for future crypto arbitrage research."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True)
class ExchangeQuote:
    exchange: str
    asset: str
    bid: Decimal
    ask: Decimal
    available_liquidity: Decimal

    def __post_init__(self) -> None:
        if self.bid <= 0 or self.ask <= 0 or self.ask < self.bid:
            raise ValueError("quote prices are invalid")
        if self.available_liquidity < 0:
            raise ValueError("liquidity cannot be negative")


@dataclass(frozen=True)
class ArbitrageCosts:
    fees: Decimal
    slippage: Decimal
    network_costs: Decimal

    @property
    def total(self) -> Decimal:
        return self.fees + self.slippage + self.network_costs


@dataclass(frozen=True)
class ArbitrageOpportunity:
    buy_quote: ExchangeQuote
    sell_quote: ExchangeQuote
    gross_edge: Decimal
    costs: ArbitrageCosts
    net_edge: Decimal
    executable: bool = False

    def __post_init__(self) -> None:
        if self.executable:
            raise ValueError("Phase 7 arbitrage analysis cannot be executable")
        if self.net_edge != self.gross_edge - self.costs.total:
            raise ValueError("net edge must include all modeled costs")


class ExchangeScanner(Protocol):
    def scan(self, asset: str) -> tuple[ExchangeQuote, ...]: ...


class PriceComparator(Protocol):
    def compare(self, quotes: tuple[ExchangeQuote, ...]) -> tuple[ExchangeQuote, ExchangeQuote]: ...


class CostModel(Protocol):
    def estimate(self, buy: ExchangeQuote, sell: ExchangeQuote) -> ArbitrageCosts: ...


def analyze_opportunity(
    buy: ExchangeQuote,
    sell: ExchangeQuote,
    costs: ArbitrageCosts,
) -> ArbitrageOpportunity:
    if buy.asset != sell.asset or buy.exchange == sell.exchange:
        raise ValueError("arbitrage quotes require one asset on distinct exchanges")
    gross_edge = sell.bid - buy.ask
    return ArbitrageOpportunity(buy, sell, gross_edge, costs, gross_edge - costs.total)
