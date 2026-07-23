from datetime import (
    datetime,
    timezone,
)

import pytest

from backend.execution.position_manager import (
    PositionManager,
)


def build_trade(
    *,
    symbol: str = "NQ",
    timeframe: str = "5m",
    action: str = "BUY",
    entry_price: float = 21691.0,
) -> dict[str, object]:
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "action": action,
        "entry_price": entry_price,
        "stop_loss": (
            entry_price - 18.75
            if action == "BUY"
            else entry_price + 18.75
        ),
        "take_profit": (
            entry_price + 37.50
            if action == "BUY"
            else entry_price - 37.50
        ),
        "contracts": 2,
        "executed": True,
        "status": "SIMULATED",
        "mode": "SIMULATED",
        "executed_at": datetime(
            2026,
            7,
            22,
            9,
            30,
            tzinfo=timezone.utc,
        ),
    }


def test_opens_long_position():
    manager = PositionManager()

    result = manager.open_position(
        build_trade(
            action="BUY"
        )
    )

    assert result["symbol"] == "NQ"
    assert result["timeframe"] == "5m"
    assert result["side"] == "LONG"
    assert result["status"] == "OPEN"
    assert result["entry_price"] == 21691.0
    assert result["contracts"] == 2


def test_opens_short_position():
    manager = PositionManager()

    result = manager.open_position(
        build_trade(
            action="SELL"
        )
    )

    assert result["side"] == "SHORT"
    assert result["status"] == "OPEN"


def test_returns_open_position():
    manager = PositionManager()

    manager.open_position(
        build_trade()
    )

    position = manager.get_open_position(
        symbol="NQ",
        timeframe="5m",
    )

    assert position is not None
    assert position["side"] == "LONG"


def test_prevents_second_position_same_market():
    manager = PositionManager()

    manager.open_position(
        build_trade()
    )

    with pytest.raises(
        ValueError,
        match="posición abierta",
    ):
        manager.open_position(
            build_trade(
                action="SELL"
            )
        )


def test_keeps_markets_separated():
    manager = PositionManager()

    manager.open_position(
        build_trade(
            symbol="NQ",
            timeframe="5m",
        )
    )

    manager.open_position(
        build_trade(
            symbol="ES",
            timeframe="1m",
        )
    )

    nq = manager.get_open_position(
        symbol="NQ",
        timeframe="5m",
    )

    es = manager.get_open_position(
        symbol="ES",
        timeframe="1m",
    )

    assert nq is not None
    assert es is not None
    assert nq["symbol"] == "NQ"
    assert es["symbol"] == "ES"


def test_closes_long_position_with_profit():
    manager = PositionManager()

    manager.open_position(
        build_trade(
            action="BUY",
            entry_price=21691.0,
        )
    )

    result = manager.close_position(
        symbol="NQ",
        timeframe="5m",
        exit_price=21701.0,
        closed_at=datetime(
            2026,
            7,
            22,
            10,
            0,
            tzinfo=timezone.utc,
        ),
        reason="MANUAL",
    )

    assert result["status"] == "CLOSED"
    assert result["exit_price"] == 21701.0
    assert result["pnl_points"] == 10.0
    assert result["pnl"] == 40.0
    assert result["close_reason"] == "MANUAL"


def test_closes_short_position_with_profit():
    manager = PositionManager()

    manager.open_position(
        build_trade(
            action="SELL",
            entry_price=21691.0,
        )
    )

    result = manager.close_position(
        symbol="NQ",
        timeframe="5m",
        exit_price=21681.0,
        closed_at=datetime(
            2026,
            7,
            22,
            10,
            0,
            tzinfo=timezone.utc,
        ),
        reason="TAKE_PROFIT",
    )

    assert result["pnl_points"] == 10.0
    assert result["pnl"] == 40.0


def test_removes_position_after_close():
    manager = PositionManager()

    manager.open_position(
        build_trade()
    )

    manager.close_position(
        symbol="NQ",
        timeframe="5m",
        exit_price=21701.0,
        closed_at=datetime.now(
            timezone.utc
        ),
        reason="MANUAL",
    )

    assert (
        manager.get_open_position(
            symbol="NQ",
            timeframe="5m",
        )
        is None
    )


def test_rejects_closing_missing_position():
    manager = PositionManager()

    with pytest.raises(
        ValueError,
        match="No existe",
    ):
        manager.close_position(
            symbol="NQ",
            timeframe="5m",
            exit_price=21701.0,
            closed_at=datetime.now(
                timezone.utc
            ),
            reason="MANUAL",
        )


def test_rejects_invalid_trade_action():
    manager = PositionManager()

    with pytest.raises(
        ValueError,
        match="action",
    ):
        manager.open_position(
            build_trade(
                action="WAIT"
            )
        )
