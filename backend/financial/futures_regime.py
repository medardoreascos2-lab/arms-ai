"""Observed NQ/MNQ performance by explicit market regime."""

from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Mapping

from backend.financial.futures_session import (
    FuturesRoot, FuturesTradeContext, PerformanceSummary, summarize_observed,
)
from backend.financial.trade_record import TradeOrigin


class FuturesRegime(str, Enum):
    TREND = "TREND"
    RANGE = "RANGE"
    HIGH_VOL = "HIGH_VOL"
    LOW_VOL = "LOW_VOL"
    NEWS = "NEWS"
    NO_TRADE = "NO_TRADE"


@dataclass(frozen=True)
class RegimePerformance:
    root: FuturesRoot
    origin: TradeOrigin
    result_currency: str
    groups: Mapping[FuturesRegime, PerformanceSummary]
    unknown_regime_count: int
    analysis_only: bool = True


def analyze_regime_performance(contexts: tuple[FuturesTradeContext, ...]) -> RegimePerformance:
    summarize_observed(contexts)
    groups: dict[FuturesRegime, list[FuturesTradeContext]] = defaultdict(list)
    unknown = 0
    for context in contexts:
        raw = context.trade.market_regime
        if raw is None:
            unknown += 1
            continue
        try:
            regime = FuturesRegime(raw)
        except ValueError as exc:
            raise ValueError(f"unsupported market regime: {raw}") from exc
        groups[regime].append(context)
    return RegimePerformance(
        contexts[0].root, contexts[0].trade.origin, contexts[0].result_currency,
        MappingProxyType({key: summarize_observed(tuple(value)) for key, value in groups.items()}),
        unknown,
    )
