"""Hypothetical portfolio rebalance scenarios; no mutation or order API."""

from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType
from typing import Mapping

from backend.financial.portfolio import PortfolioSnapshot


@dataclass(frozen=True)
class HypotheticalTrade:
    asset_id: str
    value_delta: Decimal
    quantity_delta: Decimal
    label: str = "HYPOTHETICAL"


@dataclass(frozen=True)
class RebalanceScenario:
    before: Mapping[str, Decimal]
    after: Mapping[str, Decimal]
    estimated_cost: Decimal
    estimated_value_impact: Decimal
    trades: tuple[HypotheticalTrade, ...]
    label: str = "HYPOTHETICAL"


def propose_rebalance(
    portfolio: PortfolioSnapshot,
    target_weights: Mapping[str, Decimal],
    estimated_fee_rate: Decimal,
) -> RebalanceScenario:
    total = portfolio.current_value
    if total is None or total <= 0:
        raise ValueError("complete positive valuation is required")
    if not isinstance(estimated_fee_rate, Decimal) or not estimated_fee_rate.is_finite() or not 0 <= estimated_fee_rate < 1:
        raise ValueError("explicit finite estimated_fee_rate is required")
    ids = {p.asset_id for p in portfolio.positions}
    if set(target_weights) != ids | {"CASH"}:
        raise ValueError("target weights must cover all positions and CASH")
    if any(not isinstance(w, Decimal) or not w.is_finite() or w < 0 or w > 1 for w in target_weights.values()):
        raise ValueError("target weights must be finite fractions")
    if sum(target_weights.values(), Decimal(0)) != 1:
        raise ValueError("target weights must sum to one")
    current = {p.asset_id: p.current_value / total for p in portfolio.positions}
    cash_value = sum(portfolio.cash.values(), Decimal(0))
    current["CASH"] = cash_value / total
    trades = []
    for p in portfolio.positions:
        if p.current_price is None or p.current_price <= 0:
            raise ValueError("positive known prices are required to estimate quantities")
        delta = total * target_weights[p.asset_id] - p.current_value
        if delta:
            trades.append(HypotheticalTrade(p.asset_id, delta, delta / p.current_price))
    estimated_cost = sum((abs(t.value_delta) for t in trades), Decimal(0)) * estimated_fee_rate
    if total * target_weights["CASH"] < estimated_cost:
        raise ValueError("target cash cannot cover estimated costs")
    return RebalanceScenario(
        MappingProxyType(current),
        MappingProxyType(dict(target_weights)),
        estimated_cost,
        -estimated_cost,
        tuple(trades),
    )
