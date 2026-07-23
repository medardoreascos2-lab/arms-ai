from datetime import (
    datetime,
    timezone,
)

import pytest

from backend.execution.position_manager import (
    PositionManager,
)
from backend.execution.trade_management_engine import (
    TradeManagementEngine,
)
from backend.services.trade_history_store import (
    TradeHistoryStore,
)


def build_trade(
    *,
    action: str = "BUY",
    entry_price: float = 21691.0,
    take_profit: float | None = None,
) -> dict[str, object]:
    if take_profit is None:
        take_profit = (
            entry_price + 100.0
            if action == "BUY"
            else entry_price - 100.0
        )

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
        "take_profit": take_profit,
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


def build_engine(
    *,
    action: str = "BUY",
) -> tuple[
    PositionManager,
    TradeHistoryStore,
    TradeManagementEngine,
]:
    manager = PositionManager()
    history_store = TradeHistoryStore()

    manager.open_position(
        build_trade(
            action=action
        )
    )

    engine = TradeManagementEngine(
        position_manager=manager,
        trade_history_store=history_store,
        point_value=2.0,
        break_even_trigger_points=20.0,
        break_even_offset_points=0.0,
        trailing_activation_points=30.0,
        trailing_distance_points=20.0,
    )

    return (
        manager,
        history_store,
        engine,
    )


def test_returns_no_position():
    engine = TradeManagementEngine(
        position_manager=PositionManager(),
        trade_history_store=TradeHistoryStore(),
        point_value=2.0,
        break_even_trigger_points=20.0,
        break_even_offset_points=0.0,
        trailing_activation_points=30.0,
        trailing_distance_points=20.0,
    )

    result = engine.evaluate_candle(
        symbol="NQ",
        timeframe="5m",
        high=21700.0,
        low=21690.0,
        close=21695.0,
        evaluated_at=datetime.now(
            timezone.utc
        ),
    )

    assert result["status"] == "NO_POSITION"
    assert result["closed"] is False


def test_moves_break_even():
    manager, _, engine = build_engine()

    result = engine.evaluate_candle(
        symbol="NQ",
        timeframe="5m",
        high=21715.0,
        low=21700.0,
        close=21711.0,
        evaluated_at=datetime.now(
            timezone.utc
        ),
    )

    assert result["status"] == "OPEN"
    assert result["break_even"]["moved"] is True

    position = manager.get_open_position(
        symbol="NQ",
        timeframe="5m",
    )

    assert position is not None
    assert position["stop_loss"] == 21691.0


def test_moves_trailing_stop():
    manager, _, engine = build_engine()

    result = engine.evaluate_candle(
        symbol="NQ",
        timeframe="5m",
        high=21735.0,
        low=21725.0,
        close=21731.0,
        evaluated_at=datetime.now(
            timezone.utc
        ),
    )

    assert result["status"] == "OPEN"
    assert result["trailing_stop"]["moved"] is True
    assert result["trailing_stop"]["stop_loss"] == 21711.0

    position = manager.get_open_position(
        symbol="NQ",
        timeframe="5m",
    )

    assert position is not None
    assert position["stop_loss"] == 21711.0


def test_closes_at_take_profit_and_saves_history():
    manager, history_store, engine = build_engine()

    result = engine.evaluate_candle(
        symbol="NQ",
        timeframe="5m",
        high=21800.0,
        low=21790.0,
        close=21795.0,
        evaluated_at=datetime.now(
            timezone.utc
        ),
    )

    assert result["status"] == "CLOSED"
    assert result["close_reason"] == "TAKE_PROFIT"

    assert (
        manager.get_open_position(
            symbol="NQ",
            timeframe="5m",
        )
        is None
    )

    history = history_store.get_history(
        symbol="NQ",
        timeframe="5m",
        limit=10,
    )

    assert len(history) == 1
    assert history[0] == result


def test_closes_at_stop_loss_and_saves_history():
    _, history_store, engine = build_engine()

    result = engine.evaluate_candle(
        symbol="NQ",
        timeframe="5m",
        high=21680.0,
        low=21670.0,
        close=21675.0,
        evaluated_at=datetime.now(
            timezone.utc
        ),
    )

    assert result["status"] == "CLOSED"
    assert result["close_reason"] == "STOP_LOSS"

    history = history_store.get_history(
        symbol="NQ",
        timeframe="5m",
        limit=10,
    )

    assert len(history) == 1


def test_supports_short_position():
    manager, _, engine = build_engine(
        action="SELL"
    )

    result = engine.evaluate_candle(
        symbol="NQ",
        timeframe="5m",
        high=21660.0,
        low=21645.0,
        close=21651.0,
        evaluated_at=datetime.now(
            timezone.utc
        ),
    )

    assert result["status"] == "OPEN"
    assert result["trailing_stop"]["moved"] is True

    position = manager.get_open_position(
        symbol="NQ",
        timeframe="5m",
    )

    assert position is not None
    assert position["stop_loss"] == 21671.0


def test_rejects_invalid_point_value():
    with pytest.raises(
        ValueError,
        match="point_value",
    ):
        TradeManagementEngine(
            position_manager=PositionManager(),
            trade_history_store=TradeHistoryStore(),
            point_value=0,
            break_even_trigger_points=20.0,
            break_even_offset_points=0.0,
            trailing_activation_points=30.0,
            trailing_distance_points=20.0,
        )
