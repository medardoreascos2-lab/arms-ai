import pytest

from backend.analytics.trade_journal_breakdown_analytics_v2 import (
    TradeJournalBreakdownAnalyticsV2,
)
from backend.journal.trade_journal_v2 import (
    TradeJournalV2,
)


def build_journal(
    *,
    breakdown_analytics=None,
) -> TradeJournalV2:
    return TradeJournalV2(
        breakdown_analytics_v2=(
            breakdown_analytics
        ),
    )


def test_accepts_none_breakdown_analytics():
    journal = build_journal(
        breakdown_analytics=None,
    )

    assert (
        journal.breakdown_analytics_v2
        is None
    )


def test_accepts_valid_breakdown_analytics():
    analytics = (
        TradeJournalBreakdownAnalyticsV2()
    )

    journal = build_journal(
        breakdown_analytics=analytics,
    )

    assert (
        journal.breakdown_analytics_v2
        is analytics
    )


def test_rejects_invalid_breakdown_analytics():
    with pytest.raises(
        TypeError,
        match="breakdown_analytics_v2",
    ):
        build_journal(
            breakdown_analytics=object(),
        )


def test_get_breakdown_returns_none_without_engine():
    journal = build_journal(
        breakdown_analytics=None,
    )

    assert journal.get_breakdown() is None


def test_get_breakdown_uses_closed_trades():
    analytics = (
        TradeJournalBreakdownAnalyticsV2()
    )

    journal = build_journal(
        breakdown_analytics=analytics,
    )

    journal._closed_trades = [
        {
            "status": "CLOSED",
            "symbol": "NQ",
            "direction": "LONG",
            "session": "ASIA",
            "strategy": "EMA_PULLBACK",
            "timeframe": "5M",
            "exit_reason": "TAKE_PROFIT",
            "realized_pnl": 200.0,
        },
        {
            "status": "CLOSED",
            "symbol": "NQ",
            "direction": "SHORT",
            "session": "NEW_YORK",
            "strategy": "FVG_REVERSAL",
            "timeframe": "1M",
            "exit_reason": "STOP_LOSS",
            "realized_pnl": -100.0,
        },
        {
            "status": "CLOSED",
            "symbol": "ES",
            "direction": "LONG",
            "session": "NEW_YORK",
            "strategy": "EMA_PULLBACK",
            "timeframe": "5M",
            "exit_reason": "TAKE_PROFIT",
            "realized_pnl": 50.0,
        },
    ]

    result = journal.get_breakdown()

    assert (
        result["by_symbol"]["NQ"][
            "total_trades"
        ]
        == 2
    )

    assert (
        result["by_symbol"]["NQ"][
            "net_profit"
        ]
        == 100.0
    )

    assert (
        result["by_symbol"]["ES"][
            "net_profit"
        ]
        == 50.0
    )

    assert (
        result["by_session"]["ASIA"][
            "winning_trades"
        ]
        == 1
    )

    assert (
        result["by_strategy"]["FVG_REVERSAL"][
            "losing_trades"
        ]
        == 1
    )


def test_summary_includes_breakdown():
    analytics = (
        TradeJournalBreakdownAnalyticsV2()
    )

    journal = build_journal(
        breakdown_analytics=analytics,
    )

    journal._closed_trades = [
        {
            "status": "CLOSED",
            "symbol": "NQ",
            "direction": "LONG",
            "session": "ASIA",
            "strategy": "EMA_PULLBACK",
            "timeframe": "5M",
            "exit_reason": "TAKE_PROFIT",
            "realized_pnl": 150.0,
        }
    ]

    summary = journal.get_summary()

    assert "breakdown" in summary

    assert (
        summary["breakdown"][
            "by_symbol"
        ]["NQ"]["net_profit"]
        == 150.0
    )


def test_summary_breakdown_is_none_without_engine():
    journal = build_journal(
        breakdown_analytics=None,
    )

    summary = journal.get_summary()

    assert summary["breakdown"] is None
