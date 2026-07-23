from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.account_risk.account_risk_guard import (
    AccountRiskGuard,
)


def build_trade(
    *,
    index: int,
    pnl: float,
) -> dict[str, object]:
    closed_at = (
        datetime(
            2026,
            7,
            22,
            9,
            30,
            tzinfo=timezone.utc,
        )
        + timedelta(
            minutes=index * 15
        )
    )

    return {
        "symbol": "NQ",
        "timeframe": "5m",
        "status": "CLOSED",
        "closed": True,
        "pnl": pnl,
        "closed_at": closed_at,
    }


def build_guard() -> AccountRiskGuard:
    return AccountRiskGuard(
        daily_loss_limit=3000.0,
        max_trades_per_day=4,
        max_consecutive_losses=3,
        max_open_positions=1,
        max_risk_per_trade=250.0,
    )


def test_allows_trade_when_limits_are_respected():
    guard = build_guard()

    result = guard.evaluate(
        trades_today=[
            build_trade(
                index=0,
                pnl=150.0,
            ),
            build_trade(
                index=1,
                pnl=-75.0,
            ),
        ],
        open_positions=0,
        proposed_risk=200.0,
    )

    assert result["approved"] is True
    assert result["status"] == "APPROVED"
    assert result["daily_pnl"] == 75.0
    assert result["trade_count"] == 2
    assert result["consecutive_losses"] == 1
    assert result["reasons"] == []


def test_blocks_when_daily_loss_limit_is_reached():
    guard = build_guard()

    result = guard.evaluate(
        trades_today=[
            build_trade(
                index=0,
                pnl=-1500.0,
            ),
            build_trade(
                index=1,
                pnl=-1500.0,
            ),
        ],
        open_positions=0,
        proposed_risk=100.0,
    )

    assert result["approved"] is False
    assert result["status"] == "BLOCKED"
    assert result["daily_pnl"] == -3000.0
    assert (
        "daily_loss_limit"
        in result["reasons"]
    )


def test_blocks_when_max_trades_is_reached():
    guard = build_guard()

    trades = [
        build_trade(
            index=index,
            pnl=25.0,
        )
        for index in range(4)
    ]

    result = guard.evaluate(
        trades_today=trades,
        open_positions=0,
        proposed_risk=100.0,
    )

    assert result["approved"] is False
    assert (
        "max_trades_per_day"
        in result["reasons"]
    )


def test_blocks_after_consecutive_losses():
    guard = build_guard()

    result = guard.evaluate(
        trades_today=[
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
                pnl=-75.0,
            ),
            build_trade(
                index=3,
                pnl=-100.0,
            ),
        ],
        open_positions=0,
        proposed_risk=100.0,
    )

    assert result["approved"] is False
    assert result["consecutive_losses"] == 3
    assert (
        "max_consecutive_losses"
        in result["reasons"]
    )


def test_resets_consecutive_losses_after_win():
    guard = build_guard()

    result = guard.evaluate(
        trades_today=[
            build_trade(
                index=0,
                pnl=-50.0,
            ),
            build_trade(
                index=1,
                pnl=-75.0,
            ),
            build_trade(
                index=2,
                pnl=100.0,
            ),
        ],
        open_positions=0,
        proposed_risk=100.0,
    )

    assert result["consecutive_losses"] == 0
    assert result["approved"] is True


def test_blocks_when_position_limit_is_reached():
    guard = build_guard()

    result = guard.evaluate(
        trades_today=[],
        open_positions=1,
        proposed_risk=100.0,
    )

    assert result["approved"] is False
    assert (
        "max_open_positions"
        in result["reasons"]
    )


def test_blocks_when_proposed_risk_is_too_high():
    guard = build_guard()

    result = guard.evaluate(
        trades_today=[],
        open_positions=0,
        proposed_risk=300.0,
    )

    assert result["approved"] is False
    assert (
        "max_risk_per_trade"
        in result["reasons"]
    )


def test_reports_multiple_blocking_reasons():
    guard = build_guard()

    trades = [
        build_trade(
            index=index,
            pnl=-1000.0,
        )
        for index in range(4)
    ]

    result = guard.evaluate(
        trades_today=trades,
        open_positions=1,
        proposed_risk=300.0,
    )

    assert result["approved"] is False
    assert len(
        result["reasons"]
    ) >= 4


def test_rejects_invalid_configuration():
    with pytest.raises(
        ValueError,
        match="daily_loss_limit",
    ):
        AccountRiskGuard(
            daily_loss_limit=0,
            max_trades_per_day=4,
            max_consecutive_losses=3,
            max_open_positions=1,
            max_risk_per_trade=250.0,
        )


def test_rejects_negative_proposed_risk():
    guard = build_guard()

    with pytest.raises(
        ValueError,
        match="proposed_risk",
    ):
        guard.evaluate(
            trades_today=[],
            open_positions=0,
            proposed_risk=-1.0,
        )
