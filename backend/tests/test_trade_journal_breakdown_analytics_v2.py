import pytest

from backend.analytics.trade_journal_breakdown_analytics_v2 import (
    TradeJournalBreakdownAnalyticsV2,
)


def build_analytics():
    return TradeJournalBreakdownAnalyticsV2()


def build_trade(
    *,
    symbol="NQ",
    direction="LONG",
    session="NEW_YORK",
    strategy="EMA_PULLBACK",
    timeframe="5M",
    exit_reason="TAKE_PROFIT",
    realized_pnl=100.0,
):
    return {
        "status": "CLOSED",
        "symbol": symbol,
        "direction": direction,
        "session": session,
        "strategy": strategy,
        "timeframe": timeframe,
        "exit_reason": exit_reason,
        "realized_pnl": realized_pnl,
    }


def test_empty_breakdown():
    analytics = build_analytics()

    result = analytics.calculate(
        trades=[],
    )

    assert result["by_symbol"] == {}
    assert result["by_direction"] == {}
    assert result["by_session"] == {}
    assert result["by_strategy"] == {}
    assert result["by_timeframe"] == {}
    assert result["by_exit_reason"] == {}


def test_breakdown_by_symbol():
    analytics = build_analytics()

    trades = [
        build_trade(
            symbol="NQ",
            realized_pnl=200.0,
        ),
        build_trade(
            symbol="NQ",
            realized_pnl=-100.0,
        ),
        build_trade(
            symbol="ES",
            realized_pnl=50.0,
        ),
    ]

    result = analytics.calculate(
        trades=trades,
    )

    nq = result["by_symbol"]["NQ"]
    es = result["by_symbol"]["ES"]

    assert nq["total_trades"] == 2
    assert nq["winning_trades"] == 1
    assert nq["losing_trades"] == 1
    assert nq["net_profit"] == 100.0
    assert nq["win_rate"] == 50.0

    assert es["total_trades"] == 1
    assert es["net_profit"] == 50.0
    assert es["win_rate"] == 100.0


def test_breakdown_by_multiple_dimensions():
    analytics = build_analytics()

    trades = [
        build_trade(
            direction="LONG",
            session="ASIA",
            strategy="EMA_PULLBACK",
            timeframe="5M",
            exit_reason="TAKE_PROFIT",
            realized_pnl=150.0,
        ),
        build_trade(
            direction="SHORT",
            session="NEW_YORK",
            strategy="FVG_REVERSAL",
            timeframe="1M",
            exit_reason="STOP_LOSS",
            realized_pnl=-75.0,
        ),
    ]

    result = analytics.calculate(
        trades=trades,
    )

    assert (
        result["by_direction"]["LONG"][
            "net_profit"
        ]
        == 150.0
    )

    assert (
        result["by_direction"]["SHORT"][
            "net_profit"
        ]
        == -75.0
    )

    assert (
        result["by_session"]["ASIA"][
            "total_trades"
        ]
        == 1
    )

    assert (
        result["by_strategy"]["FVG_REVERSAL"][
            "losing_trades"
        ]
        == 1
    )

    assert (
        result["by_timeframe"]["5M"][
            "winning_trades"
        ]
        == 1
    )

    assert (
        result["by_exit_reason"]["STOP_LOSS"][
            "net_profit"
        ]
        == -75.0
    )


def test_ignores_open_trades():
    analytics = build_analytics()

    trade = build_trade()
    trade["status"] = "OPEN"

    result = analytics.calculate(
        trades=[trade],
    )

    assert result["by_symbol"] == {}


def test_normalizes_text_values():
    analytics = build_analytics()

    trade = build_trade(
        symbol=" nq ",
        direction=" long ",
        session=" asia ",
        strategy=" ema_pullback ",
        timeframe=" 5m ",
        exit_reason=" take_profit ",
    )

    result = analytics.calculate(
        trades=[trade],
    )

    assert "NQ" in result["by_symbol"]
    assert "LONG" in result["by_direction"]
    assert "ASIA" in result["by_session"]
    assert "EMA_PULLBACK" in result["by_strategy"]
    assert "5M" in result["by_timeframe"]
    assert (
        "TAKE_PROFIT"
        in result["by_exit_reason"]
    )


def test_rejects_invalid_trades_type():
    analytics = build_analytics()

    with pytest.raises(
        TypeError,
        match="trades",
    ):
        analytics.calculate(
            trades=object(),
        )
