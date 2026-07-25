import pytest

from backend.analytics.trade_journal_analytics_v2 import (
    TradeJournalAnalyticsV2,
)


def build_analytics() -> TradeJournalAnalyticsV2:
    return TradeJournalAnalyticsV2()


def build_closed_trade(
    *,
    pnl: float,
    duration_seconds: int = 300,
):
    return {
        "status": "CLOSED",
        "realized_pnl": pnl,
        "duration_seconds": duration_seconds,
    }


def test_empty_journal():
    analytics = build_analytics()

    result = analytics.calculate(
        trades=[],
    )

    assert result["total_trades"] == 0
    assert result["winning_trades"] == 0
    assert result["losing_trades"] == 0
    assert result["breakeven_trades"] == 0
    assert result["net_profit"] == 0.0
    assert result["win_rate"] == 0.0


def test_basic_statistics():
    analytics = build_analytics()

    trades = [
        build_closed_trade(pnl=200.0),
        build_closed_trade(pnl=150.0),
        build_closed_trade(pnl=-100.0),
        build_closed_trade(pnl=0.0),
    ]

    result = analytics.calculate(
        trades=trades,
    )

    assert result["total_trades"] == 4
    assert result["winning_trades"] == 2
    assert result["losing_trades"] == 1
    assert result["breakeven_trades"] == 1

    assert result["gross_profit"] == 350.0
    assert result["gross_loss"] == 100.0
    assert result["net_profit"] == 250.0

    assert result["average_win"] == 175.0
    assert result["average_loss"] == 100.0

    assert result["largest_win"] == 200.0
    assert result["largest_loss"] == -100.0

    assert result["win_rate"] == 50.0

    assert result["profit_factor"] == 3.5

    assert round(
        result["expectancy"],
        2,
    ) == 62.5

    assert (
        result["average_duration_seconds"]
        == 300.0
    )


def test_invalid_trades_type():
    analytics = build_analytics()

    with pytest.raises(
        TypeError,
        match="trades",
    ):
        analytics.calculate(
            trades=object(),
        )
