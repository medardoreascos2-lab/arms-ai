"""F107A: NQ and MNQ session evidence never mixes."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from backend.financial.futures_session import (
    FuturesRoot, FuturesTradeContext, SessionSegment, SessionType,
    VolatilityLabel, analyze_futures_sessions,
)
from backend.financial.trade_record import FinancialTradeRecord, TradeOrigin, TradeSide

NOW = datetime(2026, 10, 4, tzinfo=timezone.utc)


def context(root, pnl):
    trade = FinancialTradeRecord(
        f"synthetic:{root.value}:{pnl}", "synthetic:journal", TradeOrigin.PAPER_OBSERVED,
        f"CME:{root.value}:2026-12", TradeSide.LONG, Decimal("100"), Decimal("101"),
        Decimal("1"), Decimal("99"), Decimal("102"), NOW, NOW + timedelta(minutes=1),
        "setup-a", "TREND", (), pnl, Decimal("0"), Decimal("0"),
    )
    return FuturesTradeContext(trade, root, SessionType.RTH, SessionSegment.OPEN, None,
                               VolatilityLabel.HIGH_VOL, "synthetic:classification", "synthetic:dataset", "USD")


def test_session_stats_include_unknown_news_and_traceable_sample():
    report = analyze_futures_sessions((context(FuturesRoot.NQ, Decimal("10")),))
    assert report.groups["SESSION:RTH"].sample_size == 1
    assert report.groups["SESSION:RTH"].win_rate == Decimal("1")
    assert report.groups["NEWS_WINDOW:UNKNOWN"].sample_size == 1
    assert report.groups["VOLATILITY:HIGH_VOL"].dataset_references == ("synthetic:dataset",)


def test_mixed_nq_mnq_cohort_rejected():
    with pytest.raises(ValueError, match="separate"):
        analyze_futures_sessions((context(FuturesRoot.NQ, Decimal("10")),
                                  context(FuturesRoot.MNQ, Decimal("-2"))))


def test_mixed_result_currency_rejected():
    nq = context(FuturesRoot.NQ, Decimal("10"))
    with pytest.raises(ValueError, match="separate"):
        analyze_futures_sessions((nq, replace(nq, result_currency="EUR")))
