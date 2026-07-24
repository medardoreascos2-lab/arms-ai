import pytest

from backend.analytics.performance_analytics_v2 import (
    PerformanceAnalyticsV2,
)


def build_analytics() -> PerformanceAnalyticsV2:
    return PerformanceAnalyticsV2(
        risk_free_rate=0.0,
        trading_days_per_year=252,
    )


def build_trades() -> list[dict[str, object]]:
    return [
        {
            "trade_id": "trade-001",
            "symbol": "NQ",
            "timeframe": "5M",
            "session": "NEW_YORK",
            "strategy": "SMART_MONEY",
            "result": "WIN",
            "realized_pnl": 100.0,
        },
        {
            "trade_id": "trade-002",
            "symbol": "NQ",
            "timeframe": "5M",
            "session": "NEW_YORK",
            "strategy": "SMART_MONEY",
            "result": "LOSS",
            "realized_pnl": -50.0,
        },
        {
            "trade_id": "trade-003",
            "symbol": "ES",
            "timeframe": "15M",
            "session": "LONDON",
            "strategy": "BREAKOUT",
            "result": "WIN",
            "realized_pnl": 75.0,
        },
        {
            "trade_id": "trade-004",
            "symbol": "NQ",
            "timeframe": "1M",
            "session": "ASIA",
            "strategy": "SCALPING",
            "result": "BREAK_EVEN",
            "realized_pnl": 0.0,
        },
    ]


def test_calculates_basic_metrics():
    analytics = build_analytics()

    result = analytics.analyze(
        trades=build_trades(),
        starting_balance=1000.0,
    )

    assert result["total_trades"] == 4
    assert result["wins"] == 2
    assert result["losses"] == 1
    assert result["break_even"] == 1
    assert result["win_rate"] == 0.50
    assert result["gross_profit"] == 175.0
    assert result["gross_loss"] == 50.0
    assert result["net_pnl"] == 125.0
    assert result["ending_balance"] == 1125.0
    assert result["profit_factor"] == 3.5
    assert result["expectancy"] == 31.25


def test_builds_equity_curve():
    analytics = build_analytics()

    result = analytics.analyze(
        trades=build_trades(),
        starting_balance=1000.0,
    )

    assert result["equity_curve"] == [
        1000.0,
        1100.0,
        1050.0,
        1125.0,
        1125.0,
    ]


def test_calculates_maximum_drawdown():
    analytics = build_analytics()

    result = analytics.analyze(
        trades=build_trades(),
        starting_balance=1000.0,
    )

    assert result["maximum_drawdown"] == 50.0
    assert result["maximum_drawdown_percent"] == pytest.approx(
        50.0 / 1100.0,
        rel=1e-4,
    )


def test_calculates_recovery_factor():
    analytics = build_analytics()

    result = analytics.analyze(
        trades=build_trades(),
        starting_balance=1000.0,
    )

    assert result["recovery_factor"] == 2.5


def test_groups_metrics_by_symbol():
    analytics = build_analytics()

    result = analytics.analyze(
        trades=build_trades(),
        starting_balance=1000.0,
    )

    by_symbol = result["by_symbol"]

    assert by_symbol["NQ"]["total_trades"] == 3
    assert by_symbol["NQ"]["wins"] == 1
    assert by_symbol["NQ"]["losses"] == 1
    assert by_symbol["NQ"]["break_even"] == 1
    assert by_symbol["NQ"]["net_pnl"] == 50.0

    assert by_symbol["ES"]["total_trades"] == 1
    assert by_symbol["ES"]["wins"] == 1
    assert by_symbol["ES"]["net_pnl"] == 75.0


def test_groups_metrics_by_session():
    analytics = build_analytics()

    result = analytics.analyze(
        trades=build_trades(),
        starting_balance=1000.0,
    )

    by_session = result["by_session"]

    assert (
        by_session["NEW_YORK"]["total_trades"]
        == 2
    )
    assert (
        by_session["NEW_YORK"]["net_pnl"]
        == 50.0
    )

    assert (
        by_session["LONDON"]["win_rate"]
        == 1.0
    )

    assert (
        by_session["ASIA"]["break_even"]
        == 1
    )


def test_groups_metrics_by_timeframe():
    analytics = build_analytics()

    result = analytics.analyze(
        trades=build_trades(),
        starting_balance=1000.0,
    )

    by_timeframe = result["by_timeframe"]

    assert by_timeframe["5M"]["total_trades"] == 2
    assert by_timeframe["15M"]["net_pnl"] == 75.0
    assert by_timeframe["1M"]["net_pnl"] == 0.0


def test_groups_metrics_by_strategy():
    analytics = build_analytics()

    result = analytics.analyze(
        trades=build_trades(),
        starting_balance=1000.0,
    )

    by_strategy = result["by_strategy"]

    assert (
        by_strategy["SMART_MONEY"]["total_trades"]
        == 2
    )
    assert (
        by_strategy["SMART_MONEY"]["net_pnl"]
        == 50.0
    )

    assert (
        by_strategy["BREAKOUT"]["win_rate"]
        == 1.0
    )


def test_handles_no_trades():
    analytics = build_analytics()

    result = analytics.analyze(
        trades=[],
        starting_balance=1000.0,
    )

    assert result["total_trades"] == 0
    assert result["wins"] == 0
    assert result["losses"] == 0
    assert result["break_even"] == 0
    assert result["win_rate"] == 0.0
    assert result["gross_profit"] == 0.0
    assert result["gross_loss"] == 0.0
    assert result["net_pnl"] == 0.0
    assert result["profit_factor"] == 0.0
    assert result["expectancy"] == 0.0
    assert result["maximum_drawdown"] == 0.0
    assert result["ending_balance"] == 1000.0
    assert result["equity_curve"] == [
        1000.0,
    ]


def test_profit_factor_is_none_without_losses():
    analytics = build_analytics()

    trades = [
        {
            "trade_id": "trade-001",
            "symbol": "NQ",
            "timeframe": "5M",
            "session": "NEW_YORK",
            "strategy": "SMART_MONEY",
            "result": "WIN",
            "realized_pnl": 100.0,
        },
    ]

    result = analytics.analyze(
        trades=trades,
        starting_balance=1000.0,
    )

    assert result["profit_factor"] is None


def test_rejects_invalid_trades_type():
    analytics = build_analytics()

    with pytest.raises(
        TypeError,
        match="trades",
    ):
        analytics.analyze(
            trades=object(),
            starting_balance=1000.0,
        )


def test_rejects_invalid_trade_item():
    analytics = build_analytics()

    with pytest.raises(
        TypeError,
        match="trade",
    ):
        analytics.analyze(
            trades=[
                object(),
            ],
            starting_balance=1000.0,
        )


def test_rejects_missing_realized_pnl():
    analytics = build_analytics()

    trade = build_trades()[0]
    trade["realized_pnl"] = None

    with pytest.raises(
        ValueError,
        match="realized_pnl",
    ):
        analytics.analyze(
            trades=[
                trade,
            ],
            starting_balance=1000.0,
        )


def test_rejects_invalid_starting_balance():
    analytics = build_analytics()

    with pytest.raises(
        ValueError,
        match="starting_balance",
    ):
        analytics.analyze(
            trades=build_trades(),
            starting_balance=0.0,
        )


def test_rejects_invalid_trading_days():
    with pytest.raises(
        ValueError,
        match="trading_days_per_year",
    ):
        PerformanceAnalyticsV2(
            risk_free_rate=0.0,
            trading_days_per_year=0,
        )
