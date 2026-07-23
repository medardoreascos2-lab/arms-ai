from datetime import (
    datetime,
    timezone,
)

import pytest

from backend.execution.position_manager import (
    PositionManager,
)
from backend.execution.position_monitor import (
    PositionMonitor,
)


def build_trade(
    *,
    action: str = "BUY",
    entry_price: float = 21691.0,
) -> dict[str, object]:
    return {
        "symbol": "NQ",
        "timeframe": "5m",
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


def build_monitor(
    *,
    action: str = "BUY",
) -> tuple[
    PositionManager,
    PositionMonitor,
]:
    manager = PositionManager()

    manager.open_position(
        build_trade(
            action=action
        )
    )

    monitor = PositionMonitor(
        position_manager=manager,
        point_value=2.0,
    )

    return manager, monitor


def test_keeps_long_position_open_inside_levels():
    manager, monitor = build_monitor(
        action="BUY"
    )

    result = monitor.evaluate_price(
        symbol="NQ",
        timeframe="5m",
        current_price=21700.0,
        evaluated_at=datetime.now(
            timezone.utc
        ),
    )

    assert result["status"] == "OPEN"
    assert result["closed"] is False

    position = manager.get_open_position(
        symbol="NQ",
        timeframe="5m",
    )

    assert position is not None


def test_closes_long_position_at_take_profit():
    manager, monitor = build_monitor(
        action="BUY"
    )

    result = monitor.evaluate_price(
        symbol="NQ",
        timeframe="5m",
        current_price=21730.0,
        evaluated_at=datetime.now(
            timezone.utc
        ),
    )

    assert result["status"] == "CLOSED"
    assert result["closed"] is True
    assert result["close_reason"] == "TAKE_PROFIT"
    assert result["exit_price"] == 21728.50
    assert result["pnl_points"] == 37.50
    assert result["pnl"] == 150.0

    assert (
        manager.get_open_position(
            symbol="NQ",
            timeframe="5m",
        )
        is None
    )


def test_closes_long_position_at_stop_loss():
    _, monitor = build_monitor(
        action="BUY"
    )

    result = monitor.evaluate_price(
        symbol="NQ",
        timeframe="5m",
        current_price=21670.0,
        evaluated_at=datetime.now(
            timezone.utc
        ),
    )

    assert result["status"] == "CLOSED"
    assert result["close_reason"] == "STOP_LOSS"
    assert result["exit_price"] == 21672.25
    assert result["pnl_points"] == -18.75
    assert result["pnl"] == -75.0


def test_closes_short_position_at_take_profit():
    _, monitor = build_monitor(
        action="SELL"
    )

    result = monitor.evaluate_price(
        symbol="NQ",
        timeframe="5m",
        current_price=21650.0,
        evaluated_at=datetime.now(
            timezone.utc
        ),
    )

    assert result["status"] == "CLOSED"
    assert result["close_reason"] == "TAKE_PROFIT"
    assert result["exit_price"] == 21653.50
    assert result["pnl_points"] == 37.50
    assert result["pnl"] == 150.0


def test_closes_short_position_at_stop_loss():
    _, monitor = build_monitor(
        action="SELL"
    )

    result = monitor.evaluate_price(
        symbol="NQ",
        timeframe="5m",
        current_price=21715.0,
        evaluated_at=datetime.now(
            timezone.utc
        ),
    )

    assert result["status"] == "CLOSED"
    assert result["close_reason"] == "STOP_LOSS"
    assert result["exit_price"] == 21709.75
    assert result["pnl_points"] == -18.75
    assert result["pnl"] == -75.0


def test_returns_no_position_when_missing():
    manager = PositionManager()

    monitor = PositionMonitor(
        position_manager=manager,
        point_value=2.0,
    )

    result = monitor.evaluate_price(
        symbol="NQ",
        timeframe="5m",
        current_price=21691.0,
        evaluated_at=datetime.now(
            timezone.utc
        ),
    )

    assert result["status"] == "NO_POSITION"
    assert result["closed"] is False


def test_rejects_invalid_point_value():
    with pytest.raises(
        ValueError,
        match="point_value",
    ):
        PositionMonitor(
            position_manager=PositionManager(),
            point_value=0,
        )


def test_saves_closed_trade_in_history():
    from backend.services.trade_history_store import (
        TradeHistoryStore,
    )

    manager = PositionManager()
    history_store = TradeHistoryStore()

    manager.open_position(
        build_trade(
            action="BUY"
        )
    )

    monitor = PositionMonitor(
        position_manager=manager,
        point_value=2.0,
        trade_history_store=history_store,
    )

    result = monitor.evaluate_price(
        symbol="NQ",
        timeframe="5m",
        current_price=21730.0,
        evaluated_at=datetime.now(
            timezone.utc
        ),
    )

    history = history_store.get_history(
        symbol="NQ",
        timeframe="5m",
        limit=10,
    )

    assert result["status"] == "CLOSED"
    assert len(history) == 1
    assert history[0] == result
    assert history[0]["close_reason"] == "TAKE_PROFIT"


def test_does_not_save_open_position_in_history():
    from backend.services.trade_history_store import (
        TradeHistoryStore,
    )

    manager = PositionManager()
    history_store = TradeHistoryStore()

    manager.open_position(
        build_trade(
            action="BUY"
        )
    )

    monitor = PositionMonitor(
        position_manager=manager,
        point_value=2.0,
        trade_history_store=history_store,
    )

    result = monitor.evaluate_price(
        symbol="NQ",
        timeframe="5m",
        current_price=21700.0,
        evaluated_at=datetime.now(
            timezone.utc
        ),
    )

    history = history_store.get_history(
        symbol="NQ",
        timeframe="5m",
        limit=10,
    )

    assert result["status"] == "OPEN"
    assert history == []


def test_moves_stop_to_break_even_before_monitoring_exit():
    from backend.execution.break_even_engine import (
        BreakEvenEngine,
    )

    manager = PositionManager()

    manager.open_position(
        build_trade(
            action="BUY"
        )
    )

    break_even_engine = BreakEvenEngine(
        position_manager=manager,
        trigger_points=20.0,
        offset_points=0.0,
    )

    monitor = PositionMonitor(
        position_manager=manager,
        point_value=2.0,
        break_even_engine=break_even_engine,
    )

    result = monitor.evaluate_price(
        symbol="NQ",
        timeframe="5m",
        current_price=21711.0,
        evaluated_at=datetime.now(
            timezone.utc
        ),
    )

    assert result["status"] == "OPEN"
    assert result["closed"] is False
    assert "break_even" in result
    assert result["break_even"]["moved"] is True
    assert (
        result["break_even"]["stop_loss"]
        == 21691.0
    )

    position = manager.get_open_position(
        symbol="NQ",
        timeframe="5m",
    )

    assert position is not None
    assert position["stop_loss"] == 21691.0


def test_closes_at_break_even_after_stop_was_moved():
    from backend.execution.break_even_engine import (
        BreakEvenEngine,
    )

    manager = PositionManager()

    manager.open_position(
        build_trade(
            action="BUY"
        )
    )

    break_even_engine = BreakEvenEngine(
        position_manager=manager,
        trigger_points=20.0,
        offset_points=0.0,
    )

    monitor = PositionMonitor(
        position_manager=manager,
        point_value=2.0,
        break_even_engine=break_even_engine,
    )

    first = monitor.evaluate_price(
        symbol="NQ",
        timeframe="5m",
        current_price=21711.0,
        evaluated_at=datetime.now(
            timezone.utc
        ),
    )

    assert first["status"] == "OPEN"

    second = monitor.evaluate_price(
        symbol="NQ",
        timeframe="5m",
        current_price=21690.0,
        evaluated_at=datetime.now(
            timezone.utc
        ),
    )

    assert second["status"] == "CLOSED"
    assert second["close_reason"] == "STOP_LOSS"
    assert second["exit_price"] == 21691.0
    assert second["pnl_points"] == 0.0
    assert second["pnl"] == 0.0
