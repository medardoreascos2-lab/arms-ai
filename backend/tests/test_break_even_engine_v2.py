import pytest

from backend.execution.break_even_engine_v2 import (
    BreakEvenEngineV2,
)


def build_engine() -> BreakEvenEngineV2:
    return BreakEvenEngineV2(
        trigger_profit_points=5.0,
        offset_points=0.0,
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
        "take_profit": 110.0,
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
        "take_profit": 90.0,
        "unrealized_points": 0.0,
        "unrealized_pnl": 0.0,
        "point_value": 2.0,
    }


def test_activates_break_even_for_long():
    engine = build_engine()

    result = engine.apply(
        position=build_long_position(),
        current_price=105.0,
    )

    assert result["activated"] is True
    assert result["status"] == "BREAK_EVEN_ACTIVE"
    assert result["direction"] == "LONG"
    assert result["previous_stop_loss"] == 95.0
    assert result["new_stop_loss"] == 100.0
    assert result["trigger_profit_points"] == 5.0
    assert result["favorable_points"] == 5.0

    assert (
        result["position"]["stop_loss"]
        == 100.0
    )


def test_activates_break_even_for_short():
    engine = build_engine()

    result = engine.apply(
        position=build_short_position(),
        current_price=95.0,
    )

    assert result["activated"] is True
    assert result["status"] == "BREAK_EVEN_ACTIVE"
    assert result["direction"] == "SHORT"
    assert result["previous_stop_loss"] == 105.0
    assert result["new_stop_loss"] == 100.0
    assert result["favorable_points"] == 5.0

    assert (
        result["position"]["stop_loss"]
        == 100.0
    )


def test_does_not_activate_long_before_trigger():
    engine = build_engine()

    result = engine.apply(
        position=build_long_position(),
        current_price=104.99,
    )

    assert result["activated"] is False
    assert result["status"] == "WAITING"
    assert result["reason"] == "trigger_not_reached"
    assert result["new_stop_loss"] == 95.0
    assert result["position"]["stop_loss"] == 95.0


def test_does_not_activate_short_before_trigger():
    engine = build_engine()

    result = engine.apply(
        position=build_short_position(),
        current_price=95.01,
    )

    assert result["activated"] is False
    assert result["status"] == "WAITING"
    assert result["reason"] == "trigger_not_reached"
    assert result["position"]["stop_loss"] == 105.0


def test_applies_positive_offset_for_long():
    engine = BreakEvenEngineV2(
        trigger_profit_points=5.0,
        offset_points=1.0,
    )

    result = engine.apply(
        position=build_long_position(),
        current_price=105.0,
    )

    assert result["activated"] is True
    assert result["new_stop_loss"] == 101.0
    assert result["position"]["stop_loss"] == 101.0


def test_applies_positive_offset_for_short():
    engine = BreakEvenEngineV2(
        trigger_profit_points=5.0,
        offset_points=1.0,
    )

    result = engine.apply(
        position=build_short_position(),
        current_price=95.0,
    )

    assert result["activated"] is True
    assert result["new_stop_loss"] == 99.0
    assert result["position"]["stop_loss"] == 99.0


def test_does_not_move_long_stop_backward():
    engine = build_engine()

    position = build_long_position()
    position["stop_loss"] = 101.0

    result = engine.apply(
        position=position,
        current_price=106.0,
    )

    assert result["activated"] is False
    assert result["status"] == "ALREADY_PROTECTED"
    assert result["reason"] == "stop_already_at_or_beyond_break_even"
    assert result["position"]["stop_loss"] == 101.0


def test_does_not_move_short_stop_backward():
    engine = build_engine()

    position = build_short_position()
    position["stop_loss"] = 99.0

    result = engine.apply(
        position=position,
        current_price=94.0,
    )

    assert result["activated"] is False
    assert result["status"] == "ALREADY_PROTECTED"
    assert result["reason"] == "stop_already_at_or_beyond_break_even"
    assert result["position"]["stop_loss"] == 99.0


def test_returns_inactive_for_closed_position():
    engine = build_engine()

    position = build_long_position()
    position["status"] = "CLOSED"

    result = engine.apply(
        position=position,
        current_price=105.0,
    )

    assert result["activated"] is False
    assert result["status"] == "INACTIVE"
    assert result["reason"] == "position_not_open"


def test_does_not_mutate_original_position():
    engine = build_engine()

    position = build_long_position()

    result = engine.apply(
        position=position,
        current_price=105.0,
    )

    assert position["stop_loss"] == 95.0
    assert result["position"]["stop_loss"] == 100.0
    assert result["position"] is not position


def test_rejects_invalid_position_type():
    engine = build_engine()

    with pytest.raises(
        TypeError,
        match="position",
    ):
        engine.apply(
            position=object(),
            current_price=105.0,
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
            current_price=105.0,
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
            current_price=105.0,
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
            current_price=105.0,
        )


def test_rejects_invalid_trigger_profit_points():
    with pytest.raises(
        ValueError,
        match="trigger_profit_points",
    ):
        BreakEvenEngineV2(
            trigger_profit_points=0.0,
            offset_points=0.0,
        )


def test_rejects_negative_offset_points():
    with pytest.raises(
        ValueError,
        match="offset_points",
    ):
        BreakEvenEngineV2(
            trigger_profit_points=5.0,
            offset_points=-1.0,
        )
