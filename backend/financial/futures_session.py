"""Source-labeled NQ/MNQ session cohorts and observed performance metrics."""

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from types import MappingProxyType
from typing import Mapping

from backend.financial.trade_record import FinancialTradeRecord, TradeOrigin


class FuturesRoot(str, Enum):
    NQ = "NQ"
    MNQ = "MNQ"


class SessionType(str, Enum):
    RTH = "RTH"
    ETH = "ETH"
    UNKNOWN = "UNKNOWN"


class SessionSegment(str, Enum):
    OPEN = "OPEN"
    MIDDAY = "MIDDAY"
    CLOSE = "CLOSE"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


class VolatilityLabel(str, Enum):
    HIGH_VOL = "HIGH_VOL"
    LOW_VOL = "LOW_VOL"
    NORMAL = "NORMAL"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class FuturesTradeContext:
    trade: FinancialTradeRecord
    root: FuturesRoot
    session: SessionType
    segment: SessionSegment
    news_window: bool | None
    volatility: VolatilityLabel
    source_reference: str
    dataset_reference: str
    result_currency: str
    setup_tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.trade.asset_id.startswith(f"CME:{self.root.value}:"):
            raise ValueError("futures root must match exact NQ or MNQ asset identity")
        if not self.source_reference.strip() or not self.dataset_reference.strip() or not self.result_currency.strip():
            raise ValueError("context requires source and dataset")
        if any(not isinstance(tag, str) or not tag.strip() for tag in self.setup_tags):
            raise ValueError("setup tags must be nonblank")
        object.__setattr__(self, "setup_tags", tuple(self.setup_tags))


@dataclass(frozen=True)
class PerformanceSummary:
    sample_size: int
    observed_result_count: int
    win_rate: Decimal | None
    expectancy_quote: Decimal | None
    max_drawdown_quote: Decimal | None
    source_references: tuple[str, ...]
    dataset_references: tuple[str, ...]
    result_currency: str


def summarize_observed(contexts: tuple[FuturesTradeContext, ...]) -> PerformanceSummary:
    if not contexts or len({item.root for item in contexts}) != 1 or len({item.trade.origin for item in contexts}) != 1 or len({item.result_currency for item in contexts}) != 1:
        raise ValueError("performance cohort must have one instrument, origin and currency")
    ordered = sorted(contexts, key=lambda context: context.trade.entry_at)
    results = [context.trade.result_pnl for context in ordered if context.trade.result_pnl is not None]
    count = len(results)
    win_rate = Decimal(sum(value > 0 for value in results)) / count if count else None
    expectancy = sum(results, Decimal(0)) / count if count else None
    drawdown = None
    if count:
        equity = Decimal(0)
        peak = Decimal(0)
        drawdown = Decimal(0)
        for value in results:
            equity += value
            peak = max(peak, equity)
            drawdown = max(drawdown, peak - equity)
    return PerformanceSummary(
        len(contexts), count, win_rate, expectancy, drawdown,
        tuple(sorted({context.source_reference for context in contexts})),
        tuple(sorted({context.dataset_reference for context in contexts})),
        contexts[0].result_currency,
    )


@dataclass(frozen=True)
class SessionAnalytics:
    root: FuturesRoot
    origin: TradeOrigin
    groups: Mapping[str, PerformanceSummary]
    analysis_only: bool = True


def analyze_futures_sessions(contexts: tuple[FuturesTradeContext, ...]) -> SessionAnalytics:
    if not contexts:
        raise ValueError("session analytics require trade contexts")
    if len({context.root for context in contexts}) != 1 or len({context.trade.origin for context in contexts}) != 1 or len({context.result_currency for context in contexts}) != 1:
        raise ValueError("NQ/MNQ and PAPER/actual cohorts must remain separate")
    groups: dict[str, list[FuturesTradeContext]] = defaultdict(list)
    for context in contexts:
        groups[f"SESSION:{context.session.value}"].append(context)
        groups[f"SEGMENT:{context.segment.value}"].append(context)
        groups[f"VOLATILITY:{context.volatility.value}"].append(context)
        news = "UNKNOWN" if context.news_window is None else "YES" if context.news_window else "NO"
        groups[f"NEWS_WINDOW:{news}"].append(context)
    return SessionAnalytics(
        contexts[0].root, contexts[0].trade.origin,
        MappingProxyType({key: summarize_observed(tuple(value)) for key, value in groups.items()}),
    )
