"""F107B: setup stats retain sample size and exact NQ/MNQ cohort identity."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from backend.financial.futures_session import FuturesRoot, FuturesTradeContext, SessionSegment, SessionType, VolatilityLabel
from backend.financial.futures_setup import SetupTag, analyze_setup_performance
from backend.financial.trade_record import FinancialTradeRecord, TradeOrigin, TradeSide

NOW = datetime(2026, 10, 4, tzinfo=timezone.utc)


def context(pnl, tags=("BOS", "FVG")):
    trade = FinancialTradeRecord(
        f"synthetic:{pnl}", "synthetic:journal", TradeOrigin.PAPER_OBSERVED,
        "CME:NQ:2026-12", TradeSide.LONG, Decimal("100"), Decimal("101"),
        Decimal("1"), Decimal("99"), Decimal("102"), NOW, NOW + timedelta(minutes=1),
        "setup-a", "TREND", (), pnl, Decimal("0"), Decimal("0"),
    )
    return FuturesTradeContext(trade, FuturesRoot.NQ, SessionType.RTH, SessionSegment.OPEN,
                               None, VolatilityLabel.NORMAL, "synthetic:classification",
                               "synthetic:dataset", "USD", tags)


def test_setup_performance_reports_win_rate_expectancy_drawdown_and_sample():
    report = analyze_setup_performance((context(Decimal("10")), context(Decimal("-5"))))
    stats = report.groups[SetupTag.BOS]
    assert stats.sample_size == 2
    assert stats.win_rate == Decimal("0.5")
    assert stats.expectancy_quote == Decimal("2.5")
    assert stats.max_drawdown_quote == Decimal("5")
    assert report.result_currency == "USD"


def test_unknown_setup_tag_is_not_silently_accepted():
    with pytest.raises(ValueError, match="unsupported"):
        analyze_setup_performance((context(Decimal("1"), ("NOT_A_SETUP",)),))
