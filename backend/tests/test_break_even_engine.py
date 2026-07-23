from datetime import (
    datetime,
    timezone,
)

import pytest

from backend.execution.break_even_engine import (
    BreakEvenEngine,
)
from backend.execution.position_manager import (
    PositionManager,
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


def build_engine(
    *,
    action: str = "BUY",
    trigger_points: float = 20.0,
    offset_points: float = 0.0,
) -> tuple[
    PositionManager,
    BreakEvenEngine,
]:
    manager = PositionManager()

    manager.open_position(
        build_trade(
            action=action
        )
    )

    engine = BreakEvenEngine(
        position_manager=manager,
        trigger_points=trigger_points,
        offset_points=offset_points,
    )

    return manager, engine


def test_keeps_long_stop_before_trigger():
    manager, engine = build_engine(
        action="BUY"
    )

    result = engine.evaluate_price(
        symbol="NQ",
        timeframe="5m",
        current_price=21700.0,
    )

    assert result["moved"] is False
    assert result["status"] == "UNCHANGED"

    position = manager.get_open_position(
        symbol="NQ",
        timeframe="5m",
    )

    assert position is not None
    assert position["stop_loss"] == 21672.25


def test_moves_long_stop_to_break_even():
    manager, engine = build_engine(
        action="BUY"
    )

    result = engine.evaluate_price(
        symbol="NQ",
        timeframe="5m",
        current_price=21711.0,
    )

    assert result["moved"] is True
    assert result["status"] == "BREAK_EVEN"
    assert result["previous_stop_loss"] == 21672.25
    assert result["stop_loss"] == 21691.0

    position = manager.get_open_position(
        symbol="NQ",
        timeframe="5m",
    )

    assert position is not None
    assert position["stop_loss"] == 21691.0


def test_moves_short_stop_to_break_even():
    manager, engine = build_engine(
        action="SELL"
    )

    result = engine.evaluate_price(
        symbol="NQ",
        timeframe="5m",
        current_price=21671.0,
    )

    assert result["moved"] is True
    assert result["stop_loss"] == 21691.0

    position = manager.get_open_position(
        symbol="NQ",
        timeframe="5m",
    )

    assert position is not None
    assert position["stop_loss"] == 21691.0


def test_applies_positive_offset_for_long():
    _, engine = build_engine(
        action="BUY",
        offset_points=2.0,
    )

    result = engine.evaluate_price(
        symbol="NQ",
        timeframe="5m",
        current_price=21711.0,
    )

    assert result["stop_loss"] == 21693.0


def test_applies_positive_offset_for_short():
    _, engine = build_engine(
        action="SELL",
        offset_points=2.0,
    )

    result = engine.evaluate_price(
        symbol="NQ",
        timeframe="5m",
        current_price=21671.0,
    )

    assert result["stop_loss"] == 21689.0


def test_does_not_move_break_even_twice():
    _, engine = build_engine(
        action="BUY"
    )

    first = engine.evaluate_price(
        symbol="NQ",
        timeframe="5m",
        current_price=21711.0,
    )

    second = engine.evaluate_price(
        symbol="NQ",
        timeframe="5m",
        current_price=21720.0,
    )

    assert first["moved"] is True
    assert second["moved"] is False
    assert second["status"] == "ALREADY_PROTECTED"


def test_returns_no_position_when_missing():
    engine = BreakEvenEngine(
        position_manager=PositionManager(),
        trigger_points=20.0,
        offset_points=0.0,
    )

    result = engine.evaluate_price(
        symbol="NQ",
        timeframe="5m",
        current_price=21711.0,
    )

    assert result["status"] == "NO_POSITION"
    assert result["moved"] is False


def test_rejects_invalid_trigger_points():
    with pytest.raises(
        ValueError,
        match="trigger_points",
    ):
        BreakEvenEngine(
            position_manager=PositionManager(),
            trigger_points=0,
            offset_points=0.0,
        )


def test_rejects_negative_offset_points():
    with pytest.raises(
        ValueError,
        match="offset_points",
    ):
        BreakEvenEngine(
            position_manager=PositionManager(),
            trigger_points=20.0,
            offset_points=-1.0,
        )
