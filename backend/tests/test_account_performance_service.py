from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.services.account_performance_service import (
    AccountPerformanceService,
)


def build_trade(
    *,
    index: int,
    pnl: float,
) -> dict[str, object]:
    opened_at = datetime(
        2026,
        7,
        22,
        9,
        30,
        tzinfo=timezone.utc,
    )

    return {
        "symbol": "NQ",
        "timeframe": "5m",
        "side": (
            "LONG"
            if index % 2 == 0
            else "SHORT"
        ),
        "status": "CLOSED",
        "closed": True,
        "entry_price": 21691.0 + index,
        "exit_price": 21695.0 + index,
        "contracts": 2,
        "opened_at": opened_at,
        "closed_at": (
            opened_at
            + timedelta(
                minutes=30 + index
            )
        ),
        "close_reason": "MANUAL",
        "pnl_points": pnl / 4.0,
        "pnl": pnl,
    }


def test_calculates_empty_performance():
    result = AccountPerformanceService().calculate(
        trades=[],
        starting_balance=17000.0,
    )

    assert result["starting_balance"] == 17000.0
    assert result["current_balance"] == 17000.0
    assert result["realized_pnl"] == 0.0
    assert result["total_trades"] == 0
    assert result["winning_trades"] == 0
    assert result["losing_trades"] == 0
    assert result["win_rate"] == 0.0
    assert result["profit_factor"] == 0.0
    assert result["average_trade"] == 0.0
    assert result["max_drawdown"] == 0.0


def test_calculates_realized_pnl_and_balance():
    trades = [
        build_trade(
            index=0,
            pnl=150.0,
        ),
        build_trade(
            index=1,
            pnl=-75.0,
        ),
        build_trade(
            index=2,
            pnl=100.0,
        ),
    ]

    result = AccountPerformanceService().calculate(
        trades=trades,
        starting_balance=17000.0,
    )

    assert result["realized_pnl"] == 175.0
    assert result["current_balance"] == 17175.0
    assert result["total_trades"] == 3


def test_calculates_win_rate():
    trades = [
        build_trade(
            index=0,
            pnl=150.0,
        ),
        build_trade(
            index=1,
            pnl=-75.0,
        ),
        build_trade(
            index=2,
            pnl=100.0,
        ),
        build_trade(
            index=3,
            pnl=-25.0,
        ),
    ]

    result = AccountPerformanceService().calculate(
        trades=trades,
        starting_balance=17000.0,
    )

    assert result["winning_trades"] == 2
    assert result["losing_trades"] == 2
    assert result["breakeven_trades"] == 0
    assert result["win_rate"] == 50.0


def test_calculates_profit_factor():
    trades = [
        build_trade(
            index=0,
            pnl=150.0,
        ),
        build_trade(
            index=1,
            pnl=-75.0,
        ),
        build_trade(
            index=2,
            pnl=100.0,
        ),
        build_trade(
            index=3,
            pnl=-25.0,
        ),
    ]

    result = AccountPerformanceService().calculate(
        trades=trades,
        starting_balance=17000.0,
    )

    assert result["gross_profit"] == 250.0
    assert result["gross_loss"] == 100.0
    assert result["profit_factor"] == 2.5


def test_profit_factor_when_no_losses():
    trades = [
        build_trade(
            index=0,
            pnl=150.0,
        ),
        build_trade(
            index=1,
            pnl=100.0,
        ),
    ]

    result = AccountPerformanceService().calculate(
        trades=trades,
        starting_balance=17000.0,
    )

    assert result["profit_factor"] is None


def test_calculates_average_trade():
    trades = [
        build_trade(
            index=0,
            pnl=150.0,
        ),
        build_trade(
            index=1,
            pnl=-50.0,
        ),
    ]

    result = AccountPerformanceService().calculate(
        trades=trades,
        starting_balance=17000.0,
    )

    assert result["average_trade"] == 50.0


def test_calculates_max_drawdown():
    trades = [
        build_trade(
            index=0,
            pnl=100.0,
        ),
        build_trade(
            index=1,
            pnl=-50.0,
        ),
        build_trade(
            index=2,
            pnl=-100.0,
        ),
        build_trade(
            index=3,
            pnl=200.0,
        ),
    ]

    result = AccountPerformanceService().calculate(
        trades=trades,
        starting_balance=1000.0,
    )

    assert result["max_drawdown"] == 150.0
    assert result["max_drawdown_percent"] == pytest.approx(
        13.6363636364
    )


def test_rejects_invalid_starting_balance():
    with pytest.raises(
        ValueError,
        match="starting_balance",
    ):
        AccountPerformanceService().calculate(
            trades=[],
            starting_balance=0,
        )


def test_rejects_open_trade():
    trade = build_trade(
        index=0,
        pnl=100.0,
    )

    trade["status"] = "OPEN"
    trade["closed"] = False

    with pytest.raises(
        ValueError,
        match="CLOSED",
    ):
        AccountPerformanceService().calculate(
            trades=[trade],
            starting_balance=17000.0,
        )
