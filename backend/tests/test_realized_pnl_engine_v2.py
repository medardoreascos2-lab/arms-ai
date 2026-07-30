import pytest

from backend.execution.realized_pnl_engine_v2 import (
    RealizedPnLEngineV2,
)


def build_engine() -> RealizedPnLEngineV2:
    return RealizedPnLEngineV2(
        point_value=2.0,
    )


def build_long_position() -> dict[str, object]:
    return {
        "status": "OPEN",
        "position_id": "pos-long",
        "symbol": "NQ",
        "direction": "LONG",
        "entry_price": 100.0,
        "current_price": 100.0,
        "quantity": 1.0,
        "original_quantity": 2.0,
        "partial_taken": True,
        "partial_exit_price": 110.0,
        "partial_closed_quantity": 1.0,
        "realized_pnl": 0.0,
        "unrealized_pnl": 0.0,
    }


def build_short_position() -> dict[str, object]:
    return {
        "status": "OPEN",
        "position_id": "pos-short",
        "symbol": "NQ",
        "direction": "SHORT",
        "entry_price": 100.0,
        "current_price": 100.0,
        "quantity": 1.0,
        "original_quantity": 2.0,
        "partial_taken": True,
        "partial_exit_price": 90.0,
        "partial_closed_quantity": 1.0,
        "realized_pnl": 0.0,
        "unrealized_pnl": 0.0,
    }


def test_calculates_realized_pnl_for_long_partial():
    engine = build_engine()

    result = engine.calculate(
        position=build_long_position(),
    )

    assert result["calculated"] is True
    assert result["direction"] == "LONG"
    assert result["realized_points"] == 10.0
    assert result["realized_pnl"] == 20.0
    assert (
        result["position"]["realized_pnl"]
        == 20.0
    )


def test_calculates_realized_pnl_for_short_partial():
    engine = build_engine()

    result = engine.calculate(
        position=build_short_position(),
    )

    assert result["calculated"] is True
    assert result["direction"] == "SHORT"
    assert result["realized_points"] == 10.0
    assert result["realized_pnl"] == 20.0
    assert (
        result["position"]["realized_pnl"]
        == 20.0
    )


def test_adds_to_existing_realized_pnl():
    engine = build_engine()

    position = build_long_position()
    position["realized_pnl"] = 10.0

    result = engine.calculate(
        position=position,
    )

    assert (
        result["previous_realized_pnl"]
        == 10.0
    )

    assert result["realized_pnl"] == 20.0

    assert (
        result["total_realized_pnl"]
        == 30.0
    )

    assert (
        result["position"]["realized_pnl"]
        == 30.0
    )


def test_calculates_unrealized_pnl_for_long():
    engine = build_engine()

    position = build_long_position()
    position["current_price"] = 116.0

    result = engine.calculate(
        position=position,
    )

    assert result["unrealized_points"] == 16.0
    assert result["unrealized_pnl"] == 32.0
    assert result["total_pnl"] == 52.0


def test_calculates_unrealized_pnl_for_short():
    engine = build_engine()

    position = build_short_position()
    position["current_price"] = 84.0

    result = engine.calculate(
        position=position,
    )

    assert result["unrealized_points"] == 16.0
    assert result["unrealized_pnl"] == 32.0
    assert result["total_pnl"] == 52.0


def test_returns_waiting_without_partial():
    engine = build_engine()

    position = build_long_position()
    position["partial_taken"] = False

    result = engine.calculate(
        position=position,
    )

    assert result["calculated"] is False
    assert result["status"] == "WAITING"
    assert result["reason"] == "partial_not_taken"


def test_does_not_calculate_same_partial_twice():
    engine = build_engine()

    position = build_long_position()
    position["partial_pnl_recorded"] = True

    result = engine.calculate(
        position=position,
    )

    assert result["calculated"] is False
    assert result["status"] == "ALREADY_RECORDED"
    assert result["reason"] == "partial_pnl_already_recorded"


def test_marks_partial_pnl_as_recorded():
    engine = build_engine()

    result = engine.calculate(
        position=build_long_position(),
    )

    assert (
        result["position"][
            "partial_pnl_recorded"
        ]
        is True
    )


def test_does_not_mutate_original_position():
    engine = build_engine()

    position = build_long_position()

    result = engine.calculate(
        position=position,
    )

    assert position["realized_pnl"] == 0.0
    assert (
        result["position"]["realized_pnl"]
        == 20.0
    )
    assert result["position"] is not position


def test_rejects_invalid_position_type():
    engine = build_engine()

    with pytest.raises(
        TypeError,
        match="position",
    ):
        engine.calculate(
            position=object(),
        )


def test_rejects_invalid_direction():
    engine = build_engine()

    position = build_long_position()
    position["direction"] = "SIDEWAYS"

    with pytest.raises(
        ValueError,
        match="direction",
    ):
        engine.calculate(
            position=position,
        )


def test_rejects_invalid_entry_price():
    engine = build_engine()

    position = build_long_position()
    position["entry_price"] = 0.0

    with pytest.raises(
        ValueError,
        match="entry_price",
    ):
        engine.calculate(
            position=position,
        )


def test_rejects_invalid_partial_exit_price():
    engine = build_engine()

    position = build_long_position()
    position["partial_exit_price"] = None

    with pytest.raises(
        ValueError,
        match="partial_exit_price",
    ):
        engine.calculate(
            position=position,
        )


def test_rejects_invalid_partial_closed_quantity():
    engine = build_engine()

    position = build_long_position()
    position["partial_closed_quantity"] = 0.0

    with pytest.raises(
        ValueError,
        match="partial_closed_quantity",
    ):
        engine.calculate(
            position=position,
        )


def test_rejects_invalid_current_price():
    engine = build_engine()

    position = build_long_position()
    position["current_price"] = 0.0

    with pytest.raises(
        ValueError,
        match="current_price",
    ):
        engine.calculate(
            position=position,
        )


def test_rejects_invalid_remaining_quantity():
    engine = build_engine()

    position = build_long_position()
    position["quantity"] = 0.0

    with pytest.raises(
        ValueError,
        match="quantity",
    ):
        engine.calculate(
            position=position,
        )


def test_rejects_invalid_point_value():
    with pytest.raises(
        ValueError,
        match="point_value",
    ):
        RealizedPnLEngineV2(
            point_value=0.0,
        )


def test_accepts_none_previous_realized_pnl():
    engine = RealizedPnLEngineV2(
        point_value=2.0,
    )

    position = {
        "position_id": "pos-none-pnl",
        "symbol": "NQ",
        "status": "OPEN",
        "direction": "LONG",
        "entry_price": 100.0,
        "current_price": 110.0,
        "quantity": 1.0,
        "original_quantity": 2.0,
        "partial_taken": True,
        "partial_closed_quantity": 1.0,
        "partial_exit_price": 110.0,
        "partial_pnl_recorded": False,
        "realized_pnl": None,
    }

    result = engine.calculate(
        position=position,
    )

    assert result["calculated"] is True
    assert result["realized_pnl"] == 20.0
    assert (
        result["position"]["realized_pnl"]
        == 20.0
    )


def test_accepts_none_previous_realized_pnl():
    engine = RealizedPnLEngineV2(
        point_value=2.0,
    )

    position = {
        "position_id": "pos-none-pnl",
        "symbol": "NQ",
        "status": "OPEN",
        "direction": "LONG",
        "entry_price": 100.0,
        "current_price": 110.0,
        "quantity": 1.0,
        "original_quantity": 2.0,
        "partial_taken": True,
        "partial_closed_quantity": 1.0,
        "partial_exit_price": 110.0,
        "partial_pnl_recorded": False,
        "realized_pnl": None,
    }

    result = engine.calculate(
        position=position,
    )

    assert result["calculated"] is True
    assert result["realized_pnl"] == 20.0
    assert (
        result["position"]["realized_pnl"]
        == 20.0
    )
