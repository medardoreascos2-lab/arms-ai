import pytest

from backend.analytics.trade_journal_analytics_v2 import (
    TradeJournalAnalyticsV2,
)
from backend.journal.trade_journal_v2 import (
    TradeJournalV2,
)


def build_journal(
    *,
    analytics=None,
) -> TradeJournalV2:
    return TradeJournalV2(
        analytics_v2=analytics,
    )


def test_accepts_none_analytics():
    journal = build_journal(
        analytics=None,
    )

    assert journal.analytics_v2 is None


def test_accepts_valid_analytics():
    analytics = TradeJournalAnalyticsV2()

    journal = build_journal(
        analytics=analytics,
    )

    assert journal.analytics_v2 is analytics


def test_rejects_invalid_analytics():
    with pytest.raises(
        TypeError,
        match="analytics_v2",
    ):
        build_journal(
            analytics=object(),
        )


def test_get_analytics_returns_none_without_engine():
    journal = build_journal(
        analytics=None,
    )

    assert journal.get_analytics() is None


def test_get_analytics_uses_closed_trades():
    analytics = TradeJournalAnalyticsV2()

    journal = build_journal(
        analytics=analytics,
    )

    journal._closed_trades = [
        {
            "status": "CLOSED",
            "realized_pnl": 200.0,
            "duration_seconds": 300.0,
        },
        {
            "status": "CLOSED",
            "realized_pnl": -100.0,
            "duration_seconds": 600.0,
        },
        {
            "status": "CLOSED",
            "realized_pnl": 0.0,
            "duration_seconds": 900.0,
        },
    ]

    result = journal.get_analytics()

    assert result["total_trades"] == 3
    assert result["winning_trades"] == 1
    assert result["losing_trades"] == 1
    assert result["breakeven_trades"] == 1
    assert result["net_profit"] == 100.0
    assert result["win_rate"] == pytest.approx(
        33.3333333333
    )
    assert (
        result["average_duration_seconds"]
        == 600.0
    )


def test_summary_includes_analytics():
    analytics = TradeJournalAnalyticsV2()

    journal = build_journal(
        analytics=analytics,
    )

    journal._closed_trades = [
        {
            "status": "CLOSED",
            "realized_pnl": 150.0,
            "duration_seconds": 300.0,
        }
    ]

    summary = journal.get_summary()

    assert "analytics" in summary
    assert summary["analytics"]["total_trades"] == 1
    assert summary["analytics"]["net_profit"] == 150.0


def test_summary_analytics_is_none_without_engine():
    journal = build_journal(
        analytics=None,
    )

    summary = journal.get_summary()

    assert summary["analytics"] is None
