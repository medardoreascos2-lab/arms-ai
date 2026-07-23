from datetime import (
    datetime,
    timezone,
)

import pytest

from backend.execution.partial_take_profit_engine import (
    PartialTakeProfitEngine,
)
from backend.execution.position_manager import (
    PositionManager,
)


def build_trade(
    *,
    action: str = "BUY",
    entry_price: float = 21691.0,
    contracts: int = 2,
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
        "contracts": contracts,
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
    contracts: int = 2,
    trigger_points: float = 30.0,
    contracts_to_close: int = 1,
) -> tuple[
    PositionManager,
    PartialTakeProfitEngine,
]:
    manager = PositionManager()

    manager.open_position(
        build_trade(
            action=action,
            contracts=contracts,
        )
    )

    engine = PartialTakeProfitEngine(
        position_manager=manager,
        trigger_points=trigger_points,
        contracts_to_close=contracts_to_close,
        point_value=2.0,
    )

    return manager, engine


def test_keeps_long_position_before_trigger():
    manager, engine = build_engine(
        action="BUY"
    )

    result = engine.evaluate_price(
        symbol="NQ",
        timeframe="5m",
        current_price=21710.0,
    )

    assert result["executed"] is False
    assert result["status"] == "INACTIVE"

    position = manager.get_open_position(
        symbol="NQ",
        timeframe="5m",
    )

    assert position is not None
    assert position["contracts"] == 2


def test_executes_long_partial_take_profit():
    manager, engine = build_engine(
        action="BUY"
    )

    result = engine.evaluate_price(
        symbol="NQ",
        timeframe="5m",
        current_price=21721.0,
    )

    assert result["executed"] is True
    assert result["status"] == "PARTIAL_TAKE_PROFIT"
    assert result["exit_price"] == 21721.0
    assert result["contracts_closed"] == 1
    assert result["contracts_remaining"] == 1
    assert result["pnl_points"] == 30.0
    assert result["realized_pnl"] == 60.0

    position = manager.get_open_position(
        symbol="NQ",
        timeframe="5m",
    )

    assert position is not None
    assert position["contracts"] == 1


def test_executes_short_partial_take_profit():
    manager, engine = build_engine(
        action="SELL"
    )

    result = engine.evaluate_price(
        symbol="NQ",
        timeframe="5m",
        current_price=21661.0,
    )

    assert result["executed"] is True
    assert result["pnl_points"] == 30.0
    assert result["realized_pnl"] == 60.0

    position = manager.get_open_position(
        symbol="NQ",
        timeframe="5m",
    )

    assert position is not None
    assert position["contracts"] == 1


def test_does_not_execute_same_partial_twice():
    manager, engine = build_engine(
        action="BUY"
    )

    first = engine.evaluate_price(
        symbol="NQ",
        timeframe="5m",
        current_price=21721.0,
    )

    second = engine.evaluate_price(
        symbol="NQ",
        timeframe="5m",
        current_price=21731.0,
    )

    assert first["executed"] is True
    assert second["executed"] is False
    assert second["status"] == "ALREADY_EXECUTED"

    position = manager.get_open_position(
        symbol="NQ",
        timeframe="5m",
    )

    assert position is not None
    assert position["contracts"] == 1


def test_returns_insufficient_contracts_when_partial_is_not_possible():
    manager = PositionManager()

    manager.open_position(
        build_trade(
            contracts=1
        )
    )

    engine = PartialTakeProfitEngine(
        position_manager=manager,
        trigger_points=30.0,
        contracts_to_close=1,
        point_value=2.0,
    )

    result = engine.evaluate_price(
        symbol="NQ",
        timeframe="5m",
        current_price=21721.0,
    )

    assert result["executed"] is False
    assert (
        result["status"]
        == "INSUFFICIENT_CONTRACTS"
    )
    assert (
        result["contracts_available"]
        == 1
    )
    assert (
        result["contracts_to_close"]
        == 1
    )
    assert (
        result["contracts_remaining"]
        == 1
    )


def test_returns_no_position_when_missing():
    engine = PartialTakeProfitEngine(
        position_manager=PositionManager(),
        trigger_points=30.0,
        contracts_to_close=1,
        point_value=2.0,
    )

    result = engine.evaluate_price(
        symbol="NQ",
        timeframe="5m",
        current_price=21721.0,
    )

    assert result["executed"] is False
    assert result["status"] == "NO_POSITION"


def test_rejects_invalid_trigger_points():
    with pytest.raises(
        ValueError,
        match="trigger_points",
    ):
        PartialTakeProfitEngine(
            position_manager=PositionManager(),
            trigger_points=0,
            contracts_to_close=1,
            point_value=2.0,
        )


def test_rejects_invalid_contracts_to_close():
    with pytest.raises(
        ValueError,
        match="contracts_to_close",
    ):
        PartialTakeProfitEngine(
            position_manager=PositionManager(),
            trigger_points=30.0,
            contracts_to_close=0,
            point_value=2.0,
        )


def test_rejects_invalid_point_value():
    with pytest.raises(
        ValueError,
        match="point_value",
    ):
        PartialTakeProfitEngine(
            position_manager=PositionManager(),
            trigger_points=30.0,
            contracts_to_close=1,
            point_value=0,
        )


def test_allows_partial_for_new_position_same_market():
    manager, engine = build_engine(
        action="BUY"
    )

    first = engine.evaluate_price(
        symbol="NQ",
        timeframe="5m",
        current_price=21721.0,
    )

    assert first["executed"] is True

    manager.close_position(
        symbol="NQ",
        timeframe="5m",
        exit_price=21730.0,
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

    new_trade = build_trade(
        action="BUY",
        contracts=2,
    )

    new_trade["executed_at"] = datetime(
        2026,
        7,
        22,
        11,
        0,
        tzinfo=timezone.utc,
    )

    manager.open_position(
        new_trade
    )

    second = engine.evaluate_price(
        symbol="NQ",
        timeframe="5m",
        current_price=21721.0,
    )

    assert second["executed"] is True
    assert (
        second["status"]
        == "PARTIAL_TAKE_PROFIT"
    )
    assert (
        second["contracts_remaining"]
        == 1
    )


def test_returns_no_position_after_previous_partial_closed():
    manager, engine = build_engine(
        action="BUY"
    )

    engine.evaluate_price(
        symbol="NQ",
        timeframe="5m",
        current_price=21721.0,
    )

    manager.close_position(
        symbol="NQ",
        timeframe="5m",
        exit_price=21730.0,
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

    result = engine.evaluate_price(
        symbol="NQ",
        timeframe="5m",
        current_price=21731.0,
    )

    assert result["executed"] is False
    assert result["status"] == "NO_POSITION"
