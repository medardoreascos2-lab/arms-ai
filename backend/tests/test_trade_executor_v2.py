import pytest

from backend.execution.position_v2 import (
    PositionDirectionV2,
    PositionStatusV2,
)

from backend.execution.trade_executor_v2 import (
    TradeExecutorV2,
)

from backend.strategies.trading_strategy_v2 import (
    TradingActionV2,
    TradingDecisionV2,
)


def build_decision(
    action: TradingActionV2,
) -> TradingDecisionV2:

    return TradingDecisionV2(
        action=action,
        confidence=0.80,
        reason="Test decision",
    )


def test_buy_decision_opens_long_position():

    executor = TradeExecutorV2()

    position = executor.execute(
        decision=build_decision(
            TradingActionV2.BUY,
        ),
        symbol="NQ",
        price=20000.0,
        quantity=2.0,
    )

    assert position is not None
    assert executor.active_position is position

    assert position.symbol == "NQ"
    assert position.direction is PositionDirectionV2.LONG
    assert position.status is PositionStatusV2.OPEN
    assert position.entry_price == 20000.0
    assert position.quantity == 2.0


def test_sell_decision_opens_short_position():

    executor = TradeExecutorV2()

    position = executor.execute(
        decision=build_decision(
            TradingActionV2.SELL,
        ),
        symbol="NQ",
        price=20000.0,
        quantity=3.0,
    )

    assert position is not None
    assert position.direction is PositionDirectionV2.SHORT
    assert position.entry_price == 20000.0
    assert position.quantity == 3.0


def test_hold_decision_does_not_open_position():

    executor = TradeExecutorV2()

    result = executor.execute(
        decision=build_decision(
            TradingActionV2.HOLD,
        ),
        symbol="NQ",
        price=20000.0,
        quantity=1.0,
    )

    assert result is None
    assert executor.active_position is None


def test_rejects_opening_second_position():

    executor = TradeExecutorV2()

    executor.execute(
        decision=build_decision(
            TradingActionV2.BUY,
        ),
        symbol="NQ",
        price=20000.0,
        quantity=1.0,
    )

    with pytest.raises(
        RuntimeError,
        match="posición abierta",
    ):
        executor.execute(
            decision=build_decision(
                TradingActionV2.SELL,
            ),
            symbol="NQ",
            price=19990.0,
            quantity=1.0,
        )


def test_closes_active_position():

    executor = TradeExecutorV2()

    opened_position = executor.execute(
        decision=build_decision(
            TradingActionV2.BUY,
        ),
        symbol="NQ",
        price=20000.0,
        quantity=2.0,
    )

    closed_position = executor.close_active_position(
        exit_price=20025.0,
        reason="MANUAL",
    )

    assert closed_position is opened_position
    assert closed_position.status is PositionStatusV2.CLOSED
    assert closed_position.realized_pnl == 50.0

    assert executor.active_position is None
    assert executor.closed_positions == [
        closed_position,
    ]


def test_rejects_closing_when_no_position_exists():

    executor = TradeExecutorV2()

    with pytest.raises(
        RuntimeError,
        match="posición activa",
    ):
        executor.close_active_position(
            exit_price=20000.0,
            reason="MANUAL",
        )


@pytest.mark.parametrize(
    "price",
    [
        0.0,
        -1.0,
    ],
)
def test_rejects_invalid_entry_price(price):

    executor = TradeExecutorV2()

    with pytest.raises(
        ValueError,
        match="price",
    ):
        executor.execute(
            decision=build_decision(
                TradingActionV2.BUY,
            ),
            symbol="NQ",
            price=price,
            quantity=1.0,
        )


@pytest.mark.parametrize(
    "quantity",
    [
        0.0,
        -1.0,
    ],
)
def test_rejects_invalid_quantity(quantity):

    executor = TradeExecutorV2()

    with pytest.raises(
        ValueError,
        match="quantity",
    ):
        executor.execute(
            decision=build_decision(
                TradingActionV2.BUY,
            ),
            symbol="NQ",
            price=20000.0,
            quantity=quantity,
        )


def test_rejects_invalid_decision():

    executor = TradeExecutorV2()

    with pytest.raises(
        TypeError,
        match="decision",
    ):
        executor.execute(
            decision="BUY",
            symbol="NQ",
            price=20000.0,
            quantity=1.0,
        )


def test_rejects_empty_symbol():

    executor = TradeExecutorV2()

    with pytest.raises(
        ValueError,
        match="symbol",
    ):
        executor.execute(
            decision=build_decision(
                TradingActionV2.BUY,
            ),
            symbol="   ",
            price=20000.0,
            quantity=1.0,
        )
