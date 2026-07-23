from datetime import (
    datetime,
    timezone,
)

import pytest

from backend.execution.position_manager import (
    PositionManager,
)
from backend.execution.trailing_stop_engine import (
    TrailingStopEngine,
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
            entry_price + 100.0
            if action == "BUY"
            else entry_price - 100.0
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
    activation_points: float = 30.0,
    distance_points: float = 20.0,
) -> tuple[
    PositionManager,
    TrailingStopEngine,
]:
    manager = PositionManager()

    manager.open_position(
        build_trade(
            action=action
        )
    )

    engine = TrailingStopEngine(
        position_manager=manager,
        activation_points=activation_points,
        distance_points=distance_points,
    )

    return manager, engine


def test_keeps_long_stop_before_activation():
    manager, engine = build_engine(
        action="BUY"
    )

    result = engine.evaluate_price(
        symbol="NQ",
        timeframe="5m",
        current_price=21710.0,
    )

    assert result["moved"] is False
    assert result["status"] == "INACTIVE"

    position = manager.get_open_position(
        symbol="NQ",
        timeframe="5m",
    )

    assert position is not None
    assert position["stop_loss"] == 21672.25


def test_moves_long_trailing_stop():
    manager, engine = build_engine(
        action="BUY"
    )

    result = engine.evaluate_price(
        symbol="NQ",
        timeframe="5m",
        current_price=21731.0,
    )

    assert result["moved"] is True
    assert result["status"] == "TRAILING_STOP"
    assert result["previous_stop_loss"] == 21672.25
    assert result["stop_loss"] == 21711.0

    position = manager.get_open_position(
        symbol="NQ",
        timeframe="5m",
    )

    assert position is not None
    assert position["stop_loss"] == 21711.0


def test_moves_short_trailing_stop():
    manager, engine = build_engine(
        action="SELL"
    )

    result = engine.evaluate_price(
        symbol="NQ",
        timeframe="5m",
        current_price=21651.0,
    )

    assert result["moved"] is True
    assert result["status"] == "TRAILING_STOP"
    assert result["stop_loss"] == 21671.0

    position = manager.get_open_position(
        symbol="NQ",
        timeframe="5m",
    )

    assert position is not None
    assert position["stop_loss"] == 21671.0


def test_long_trailing_stop_only_moves_forward():
    _, engine = build_engine(
        action="BUY"
    )

    first = engine.evaluate_price(
        symbol="NQ",
        timeframe="5m",
        current_price=21731.0,
    )

    second = engine.evaluate_price(
        symbol="NQ",
        timeframe="5m",
        current_price=21725.0,
    )

    assert first["moved"] is True
    assert second["moved"] is False
    assert second["status"] == "UNCHANGED"
    assert second["stop_loss"] == 21711.0


def test_short_trailing_stop_only_moves_forward():
    _, engine = build_engine(
        action="SELL"
    )

    first = engine.evaluate_price(
        symbol="NQ",
        timeframe="5m",
        current_price=21651.0,
    )

    second = engine.evaluate_price(
        symbol="NQ",
        timeframe="5m",
        current_price=21660.0,
    )

    assert first["moved"] is True
    assert second["moved"] is False
    assert second["status"] == "UNCHANGED"
    assert second["stop_loss"] == 21671.0


def test_moves_trailing_stop_again_when_price_advances():
    _, engine = build_engine(
        action="BUY"
    )

    first = engine.evaluate_price(
        symbol="NQ",
        timeframe="5m",
        current_price=21731.0,
    )

    second = engine.evaluate_price(
        symbol="NQ",
        timeframe="5m",
        current_price=21745.0,
    )

    assert first["stop_loss"] == 21711.0
    assert second["moved"] is True
    assert second["stop_loss"] == 21725.0


def test_returns_no_position_when_missing():
    engine = TrailingStopEngine(
        position_manager=PositionManager(),
        activation_points=30.0,
        distance_points=20.0,
    )

    result = engine.evaluate_price(
        symbol="NQ",
        timeframe="5m",
        current_price=21731.0,
    )

    assert result["status"] == "NO_POSITION"
    assert result["moved"] is False


def test_rejects_invalid_activation_points():
    with pytest.raises(
        ValueError,
        match="activation_points",
    ):
        TrailingStopEngine(
            position_manager=PositionManager(),
            activation_points=0,
            distance_points=20.0,
        )


def test_rejects_invalid_distance_points():
    with pytest.raises(
        ValueError,
        match="distance_points",
    ):
        TrailingStopEngine(
            position_manager=PositionManager(),
            activation_points=30.0,
            distance_points=0,
        )
