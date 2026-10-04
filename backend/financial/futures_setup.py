"""Observed NQ/MNQ setup performance with exact setup tags."""

from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Mapping

from backend.financial.futures_session import (
    FuturesRoot, FuturesTradeContext, PerformanceSummary, summarize_observed,
)
from backend.financial.trade_record import TradeOrigin


class SetupTag(str, Enum):
    BOS = "BOS"
    CHOCH = "CHOCH"
    FVG = "FVG"
    LIQUIDITY = "LIQUIDITY"
    TREND = "TREND"
    PULLBACK = "PULLBACK"
    CONFLUENCE = "CONFLUENCE"


@dataclass(frozen=True)
class SetupPerformance:
    root: FuturesRoot
    origin: TradeOrigin
    result_currency: str
    groups: Mapping[SetupTag, PerformanceSummary]
    unclassified_count: int
    analysis_only: bool = True


def analyze_setup_performance(contexts: tuple[FuturesTradeContext, ...]) -> SetupPerformance:
    summarize_observed(contexts)
    groups: dict[SetupTag, list[FuturesTradeContext]] = defaultdict(list)
    unclassified = 0
    for context in contexts:
        if not context.setup_tags:
            unclassified += 1
        for raw_tag in set(context.setup_tags):
            try:
                tag = SetupTag(raw_tag)
            except ValueError as exc:
                raise ValueError(f"unsupported setup tag: {raw_tag}") from exc
            groups[tag].append(context)
    return SetupPerformance(
        contexts[0].root, contexts[0].trade.origin, contexts[0].result_currency,
        MappingProxyType({key: summarize_observed(tuple(value)) for key, value in groups.items()}),
        unclassified,
    )
