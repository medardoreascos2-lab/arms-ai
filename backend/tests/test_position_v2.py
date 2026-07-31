import pytest

from backend.execution.position_v2 import (
    PositionDirectionV2,
    PositionStatusV2,
    PositionV2,
)


def test_creates_open_long_position():

    position = PositionV2(
        symbol="NQ",
        direction=PositionDirectionV2.LONG,
        entry_price=20000.0,
        quantity=2.0,
        stop_loss=19970.0,
        take_profit=20060.0,
    )

    assert position.symbol == "NQ"
    assert position.direction is PositionDirectionV2.LONG
    assert position.status is PositionStatusV2.OPEN
    assert position.entry_price == 20000.0
    assert position.quantity == 2.0
    assert position.exit_price is None
    assert position.exit_reason is None
    assert position.realized_pnl == 0.0


def test_closes_long_position_with_profit():

    position = PositionV2(
        symbol="NQ",
        direction=PositionDirectionV2.LONG,
        entry_price=20000.0,
        quantity=2.0,
    )

    pnl = position.close(
        exit_price=20025.0,
        reason="TAKE_PROFIT",
    )

    assert pnl == 50.0
    assert position.status is PositionStatusV2.CLOSED
    assert position.exit_price == 20025.0
    assert position.exit_reason == "TAKE_PROFIT"
    assert position.realized_pnl == 50.0


def test_closes_short_position_with_profit():

    position = PositionV2(
        symbol="NQ",
        direction=PositionDirectionV2.SHORT,
        entry_price=20000.0,
        quantity=3.0,
    )

    pnl = position.close(
        exit_price=19980.0,
        reason="MANUAL",
    )

    assert pnl == 60.0
    assert position.realized_pnl == 60.0


def test_rejects_closing_position_twice():

    position = PositionV2(
        symbol="NQ",
        direction=PositionDirectionV2.LONG,
        entry_price=20000.0,
        quantity=1.0,
    )

    position.close(
        exit_price=20010.0,
        reason="MANUAL",
    )

    with pytest.raises(
        RuntimeError,
        match="cerrada",
    ):
        position.close(
            exit_price=20020.0,
            reason="MANUAL",
        )


@pytest.mark.parametrize(
    "quantity",
    [
        0.0,
        -1.0,
    ],
)
def test_rejects_invalid_quantity(quantity):

    with pytest.raises(
        ValueError,
        match="quantity",
    ):
        PositionV2(
            symbol="NQ",
            direction=PositionDirectionV2.LONG,
            entry_price=20000.0,
            quantity=quantity,
        )


def test_rejects_invalid_direction():

    with pytest.raises(
        TypeError,
        match="direction",
    ):
        PositionV2(
            symbol="NQ",
            direction="LONG",
            entry_price=20000.0,
            quantity=1.0,
        )


def test_rejects_empty_symbol():

    with pytest.raises(
        ValueError,
        match="symbol",
    ):
        PositionV2(
            symbol="   ",
            direction=PositionDirectionV2.LONG,
            entry_price=20000.0,
            quantity=1.0,
        )


def test_position_enums_are_available():

    assert PositionDirectionV2.LONG.value == "LONG"
    assert PositionDirectionV2.SHORT.value == "SHORT"

    assert PositionStatusV2.OPEN.value == "OPEN"
    assert PositionStatusV2.CLOSED.value == "CLOSED"
