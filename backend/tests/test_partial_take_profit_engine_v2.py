import pytest

from backend.execution.partial_take_profit_engine_v2 import (
    PartialTakeProfitEngineV2,
)


def build_engine():
    return PartialTakeProfitEngineV2(
        trigger_profit_points=10.0,
        close_fraction=0.50,
    )


def build_position():
    return {
        "status": "OPEN",
        "position_id": "pos-1",
        "symbol": "NQ",
        "direction": "LONG",
        "quantity": 2.0,
        "entry_price": 100.0,
        "current_price": 100.0,
        "stop_loss": 95.0,
        "take_profit": 120.0,
        "partial_taken": False,
    }


def test_executes_partial_profit():
    engine = build_engine()

    result = engine.apply(
        position=build_position(),
        current_price=110.0,
    )

    assert result["executed"] is True
    assert result["closed_quantity"] == 1.0
    assert result["remaining_quantity"] == 1.0
    assert result["position"]["partial_taken"] is True


def test_waits_before_trigger():
    engine = build_engine()

    result = engine.apply(
        position=build_position(),
        current_price=108.0,
    )

    assert result["executed"] is False
    assert result["reason"] == "trigger_not_reached"


def test_does_not_execute_twice():
    engine = build_engine()

    position = build_position()
    position["partial_taken"] = True

    result = engine.apply(
        position=position,
        current_price=110.0,
    )

    assert result["executed"] is False
    assert result["reason"] == "partial_already_taken"


def test_rejects_invalid_position():
    engine = build_engine()

    with pytest.raises(TypeError):
        engine.apply(
            position=object(),
            current_price=110.0,
        )


def test_rejects_invalid_trigger():
    with pytest.raises(ValueError):
        PartialTakeProfitEngineV2(
            trigger_profit_points=0.0,
            close_fraction=0.5,
        )


def test_rejects_invalid_fraction():
    with pytest.raises(ValueError):
        PartialTakeProfitEngineV2(
            trigger_profit_points=10.0,
            close_fraction=0.0,
        )
