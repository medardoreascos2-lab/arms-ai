import pytest

from backend.execution.trailing_stop_engine_v2 import (
    TrailingStopEngineV2,
)


def build_engine() -> TrailingStopEngineV2:
    return TrailingStopEngineV2(
        activation_profit_points=5.0,
        trailing_distance_points=3.0,
    )


def build_long_position() -> dict[str, object]:
    return {
        "opened": True,
        "status": "OPEN",
        "position_id": "position-long",
        "symbol": "NQ",
        "direction": "LONG",
        "quantity": 2,
        "entry_price": 100.0,
        "current_price": 100.0,
        "stop_loss": 95.0,
        "take_profit": 120.0,
        "unrealized_points": 0.0,
        "unrealized_pnl": 0.0,
        "point_value": 2.0,
    }


def build_short_position() -> dict[str, object]:
    return {
        "opened": True,
        "status": "OPEN",
        "position_id": "position-short",
        "symbol": "NQ",
        "direction": "SHORT",
        "quantity": 2,
        "entry_price": 100.0,
        "current_price": 100.0,
        "stop_loss": 105.0,
        "take_profit": 80.0,
        "unrealized_points": 0.0,
        "unrealized_pnl": 0.0,
        "point_value": 2.0,
    }


def test_activates_trailing_stop_for_long():
    engine = build_engine()

    result = engine.apply(
        position=build_long_position(),
        current_price=108.0,
    )

    assert result["activated"] is True
    assert result["status"] == "TRAILING_ACTIVE"
    assert result["direction"] == "LONG"
    assert result["previous_stop_loss"] == 95.0
    assert result["new_stop_loss"] == 105.0
    assert result["favorable_points"] == 8.0
    assert (
        result["position"]["stop_loss"]
        == 105.0
    )


def test_activates_trailing_stop_for_short():
    engine = build_engine()

    result = engine.apply(
        position=build_short_position(),
        current_price=92.0,
    )

    assert result["activated"] is True
    assert result["status"] == "TRAILING_ACTIVE"
    assert result["direction"] == "SHORT"
    assert result["previous_stop_loss"] == 105.0
    assert result["new_stop_loss"] == 95.0
    assert result["favorable_points"] == 8.0
    assert (
        result["position"]["stop_loss"]
        == 95.0
    )


def test_waits_before_activation_for_long():
    engine = build_engine()

    result = engine.apply(
        position=build_long_position(),
        current_price=104.99,
    )

    assert result["activated"] is False
    assert result["status"] == "WAITING"
    assert result["reason"] == "activation_not_reached"
    assert result["position"]["stop_loss"] == 95.0


def test_waits_before_activation_for_short():
    engine = build_engine()

    result = engine.apply(
        position=build_short_position(),
        current_price=95.01,
    )

    assert result["activated"] is False
    assert result["status"] == "WAITING"
    assert result["reason"] == "activation_not_reached"
    assert result["position"]["stop_loss"] == 105.0


def test_does_not_move_long_stop_backward():
    engine = build_engine()

    position = build_long_position()
    position["stop_loss"] = 106.0

    result = engine.apply(
        position=position,
        current_price=108.0,
    )

    assert result["activated"] is False
    assert result["status"] == "ALREADY_PROTECTED"
    assert result["reason"] == "stop_would_move_backward"
    assert result["position"]["stop_loss"] == 106.0


def test_does_not_move_short_stop_backward():
    engine = build_engine()

    position = build_short_position()
    position["stop_loss"] = 94.0

    result = engine.apply(
        position=position,
        current_price=92.0,
    )

    assert result["activated"] is False
    assert result["status"] == "ALREADY_PROTECTED"
    assert result["reason"] == "stop_would_move_backward"
    assert result["position"]["stop_loss"] == 94.0


def test_updates_trailing_stop_as_price_advances_long():
    engine = build_engine()

    first = engine.apply(
        position=build_long_position(),
        current_price=108.0,
    )

    second = engine.apply(
        position=first["position"],
        current_price=111.0,
    )

    assert first["new_stop_loss"] == 105.0
    assert second["new_stop_loss"] == 108.0
    assert second["activated"] is True


def test_updates_trailing_stop_as_price_advances_short():
    engine = build_engine()

    first = engine.apply(
        position=build_short_position(),
        current_price=92.0,
    )

    second = engine.apply(
        position=first["position"],
        current_price=89.0,
    )

    assert first["new_stop_loss"] == 95.0
    assert second["new_stop_loss"] == 92.0
    assert second["activated"] is True


def test_returns_inactive_for_closed_position():
    engine = build_engine()

    position = build_long_position()
    position["status"] = "CLOSED"

    result = engine.apply(
        position=position,
        current_price=108.0,
    )

    assert result["activated"] is False
    assert result["status"] == "INACTIVE"
    assert result["reason"] == "position_not_open"


def test_does_not_mutate_original_position():
    engine = build_engine()

    position = build_long_position()

    result = engine.apply(
        position=position,
        current_price=108.0,
    )

    assert position["stop_loss"] == 95.0
    assert result["position"]["stop_loss"] == 105.0
    assert result["position"] is not position


def test_rejects_invalid_position_type():
    engine = build_engine()

    with pytest.raises(
        TypeError,
        match="position",
    ):
        engine.apply(
            position=object(),
            current_price=108.0,
        )


def test_rejects_invalid_direction():
    engine = build_engine()

    position = build_long_position()
    position["direction"] = "SIDEWAYS"

    with pytest.raises(
        ValueError,
        match="direction",
    ):
        engine.apply(
            position=position,
            current_price=108.0,
        )


def test_rejects_invalid_current_price():
    engine = build_engine()

    with pytest.raises(
        ValueError,
        match="current_price",
    ):
        engine.apply(
            position=build_long_position(),
            current_price=0.0,
        )


def test_rejects_invalid_entry_price():
    engine = build_engine()

    position = build_long_position()
    position["entry_price"] = 0.0

    with pytest.raises(
        ValueError,
        match="entry_price",
    ):
        engine.apply(
            position=position,
            current_price=108.0,
        )


def test_rejects_invalid_stop_loss():
    engine = build_engine()

    position = build_long_position()
    position["stop_loss"] = None

    with pytest.raises(
        ValueError,
        match="stop_loss",
    ):
        engine.apply(
            position=position,
            current_price=108.0,
        )


def test_rejects_invalid_activation_profit_points():
    with pytest.raises(
        ValueError,
        match="activation_profit_points",
    ):
        TrailingStopEngineV2(
            activation_profit_points=0.0,
            trailing_distance_points=3.0,
        )


def test_rejects_invalid_trailing_distance_points():
    with pytest.raises(
        ValueError,
        match="trailing_distance_points",
    ):
        TrailingStopEngineV2(
            activation_profit_points=5.0,
            trailing_distance_points=0.0,
        )
