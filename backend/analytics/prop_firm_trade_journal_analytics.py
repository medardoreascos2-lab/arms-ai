"""Pure, decimal-safe analytics for identified closed journal trades."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Callable


def _text(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a nonempty string")


def _decimal(value: Decimal, name: str, *, positive: bool = False) -> None:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise ValueError(f"{name} must be a finite Decimal")
    if positive and value <= 0:
        raise ValueError(f"{name} must be positive")


@dataclass(frozen=True)
class ClosedJournalTrade:
    trade_id: str
    realized_pnl: Decimal
    instrument: str
    session: str
    account_id: str
    firm_id: str
    initial_risk: Decimal | None = None

    def __post_init__(self) -> None:
        for name in ("trade_id", "instrument", "session", "account_id", "firm_id"):
            _text(getattr(self, name), name)
        _decimal(self.realized_pnl, "realized_pnl")
        if self.initial_risk is not None:
            _decimal(self.initial_risk, "initial_risk", positive=True)

    @property
    def r_multiple(self) -> Decimal | None:
        return (
            None
            if self.initial_risk is None
            else self.realized_pnl / self.initial_risk
        )


class ProfitFactorState(str, Enum):
    AVAILABLE = "AVAILABLE"
    NO_GROSS_LOSS = "NO_GROSS_LOSS"
    NO_PROFIT_OR_LOSS = "NO_PROFIT_OR_LOSS"


@dataclass(frozen=True)
class TradePerformanceMetrics:
    total_trades: int
    winning_trades: int
    losing_trades: int
    breakeven_trades: int
    gross_profit: Decimal
    gross_loss: Decimal
    net_pnl: Decimal
    win_rate: Decimal
    average_win: Decimal
    average_loss: Decimal
    expectancy: Decimal
    profit_factor: Decimal | None
    profit_factor_state: ProfitFactorState


@dataclass(frozen=True)
class RDistribution:
    observed_trades: int
    missing_risk_trade_ids: tuple[str, ...]
    mean_r: Decimal | None
    median_r: Decimal | None
    minimum_r: Decimal | None
    maximum_r: Decimal | None
    buckets: tuple[tuple[str, int], ...]
    values: tuple[tuple[str, Decimal], ...]

    @property
    def complete(self) -> bool:
        return not self.missing_risk_trade_ids


@dataclass(frozen=True)
class JournalDistributionRow:
    key: str
    performance: TradePerformanceMetrics


@dataclass(frozen=True)
class TradeJournalAnalyticsReport:
    performance: TradePerformanceMetrics
    r_distribution: RDistribution
    session_distribution: tuple[JournalDistributionRow, ...]
    instrument_distribution: tuple[JournalDistributionRow, ...]
    account_distribution: tuple[JournalDistributionRow, ...]
    firm_distribution: tuple[JournalDistributionRow, ...]
    execution_authorized: bool = field(default=False, init=False)


def _performance(trades: tuple[ClosedJournalTrade, ...]) -> TradePerformanceMetrics:
    wins = tuple(item.realized_pnl for item in trades if item.realized_pnl > 0)
    losses = tuple(item.realized_pnl for item in trades if item.realized_pnl < 0)
    breakeven = sum(item.realized_pnl == 0 for item in trades)
    gross_profit = sum(wins, Decimal("0"))
    gross_loss = abs(sum(losses, Decimal("0")))
    total = len(trades)
    net = gross_profit - gross_loss
    if gross_loss > 0:
        profit_factor = gross_profit / gross_loss
        profit_factor_state = ProfitFactorState.AVAILABLE
    elif gross_profit > 0:
        profit_factor = None
        profit_factor_state = ProfitFactorState.NO_GROSS_LOSS
    else:
        profit_factor = None
        profit_factor_state = ProfitFactorState.NO_PROFIT_OR_LOSS
    return TradePerformanceMetrics(
        total_trades=total,
        winning_trades=len(wins),
        losing_trades=len(losses),
        breakeven_trades=breakeven,
        gross_profit=gross_profit,
        gross_loss=gross_loss,
        net_pnl=net,
        win_rate=Decimal(len(wins)) / total if total else Decimal("0"),
        average_win=gross_profit / len(wins) if wins else Decimal("0"),
        average_loss=gross_loss / len(losses) if losses else Decimal("0"),
        expectancy=net / total if total else Decimal("0"),
        profit_factor=profit_factor,
        profit_factor_state=profit_factor_state,
    )


def _median(values: tuple[Decimal, ...]) -> Decimal | None:
    if not values:
        return None
    ordered = tuple(sorted(values))
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / Decimal("2")


def _r_bucket(value: Decimal) -> str:
    if value <= -2:
        return "LOSS_2R_OR_WORSE"
    if value <= -1:
        return "LOSS_1_TO_2R"
    if value < 0:
        return "LOSS_UNDER_1R"
    if value == 0:
        return "BREAKEVEN"
    if value < 1:
        return "WIN_UNDER_1R"
    if value < 2:
        return "WIN_1_TO_2R"
    return "WIN_2R_OR_BETTER"


def _r_distribution(trades: tuple[ClosedJournalTrade, ...]) -> RDistribution:
    observed = tuple(
        (item.trade_id, item.r_multiple)
        for item in trades
        if item.r_multiple is not None
    )
    values = tuple(value for _, value in observed)
    bucket_names = (
        "LOSS_2R_OR_WORSE",
        "LOSS_1_TO_2R",
        "LOSS_UNDER_1R",
        "BREAKEVEN",
        "WIN_UNDER_1R",
        "WIN_1_TO_2R",
        "WIN_2R_OR_BETTER",
    )
    counts = {name: 0 for name in bucket_names}
    for value in values:
        counts[_r_bucket(value)] += 1
    return RDistribution(
        observed_trades=len(values),
        missing_risk_trade_ids=tuple(
            item.trade_id for item in trades if item.initial_risk is None
        ),
        mean_r=(sum(values, Decimal("0")) / len(values) if values else None),
        median_r=_median(values),
        minimum_r=min(values) if values else None,
        maximum_r=max(values) if values else None,
        buckets=tuple((name, counts[name]) for name in bucket_names),
        values=observed,
    )


def _distribution(
    trades: tuple[ClosedJournalTrade, ...],
    getter: Callable[[ClosedJournalTrade], str],
) -> tuple[JournalDistributionRow, ...]:
    grouped: dict[str, list[ClosedJournalTrade]] = defaultdict(list)
    for trade in trades:
        grouped[getter(trade)].append(trade)
    return tuple(
        JournalDistributionRow(key, _performance(tuple(grouped[key])))
        for key in sorted(grouped)
    )


def analyze_trade_journal(
    trades: tuple[ClosedJournalTrade, ...],
) -> TradeJournalAnalyticsReport:
    """Calculate immutable journal diagnostics with no journal or trade mutation."""
    if not isinstance(trades, tuple) or any(
        not isinstance(item, ClosedJournalTrade) for item in trades
    ):
        raise ValueError("trades must be an immutable tuple of ClosedJournalTrade values")
    trade_ids = tuple(item.trade_id for item in trades)
    if len(trade_ids) != len(set(trade_ids)):
        raise ValueError("trade_id values must be unique")
    return TradeJournalAnalyticsReport(
        performance=_performance(trades),
        r_distribution=_r_distribution(trades),
        session_distribution=_distribution(trades, lambda item: item.session),
        instrument_distribution=_distribution(trades, lambda item: item.instrument),
        account_distribution=_distribution(trades, lambda item: item.account_id),
        firm_distribution=_distribution(trades, lambda item: item.firm_id),
    )
