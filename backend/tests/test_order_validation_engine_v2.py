import pytest

from backend.execution.order_validation_engine_v2 import (
    OrderValidationEngineV2,
)


def build_engine() -> OrderValidationEngineV2:
    return OrderValidationEngineV2(
        minimum_reward_risk_ratio=2.0,
        minimum_stop_points=2.0,
        maximum_stop_points=50.0,
        allowed_symbols={
            "NQ",
            "MNQ",
            "ES",
            "MES",
        },
    )


def build_valid_order() -> dict[str, object]:
    return {
        "approved": True,
        "status": "READY_TO_SUBMIT",
        "decision": "SUBMIT_ORDER",
        "execution_mode": "PAPER",
        "symbol": "NQ",
        "side": "BUY",
        "order_type": "MARKET",
        "quantity": 2,
        "entry_price": 100.0,
        "limit_price": None,
        "stop_loss": 95.0,
        "take_profit": 110.0,
        "blocking_reasons": [],
    }


def test_approves_valid_buy_order():
    engine = build_engine()

    result = engine.validate(
        prepared_order=build_valid_order(),
        market_is_open=True,
        open_symbols=set(),
    )

    assert result["approved"] is True
    assert result["status"] == "APPROVED"
    assert result["decision"] == "ALLOW_ORDER"
    assert result["symbol"] == "NQ"
    assert result["side"] == "BUY"
    assert result["reward_risk_ratio"] == 2.0
    assert result["blocking_reasons"] == []


def test_approves_valid_sell_order():
    engine = build_engine()

    order = build_valid_order()

    order.update(
        {
            "side": "SELL",
            "stop_loss": 105.0,
            "take_profit": 90.0,
        }
    )

    result = engine.validate(
        prepared_order=order,
        market_is_open=True,
        open_symbols=set(),
    )

    assert result["approved"] is True
    assert result["side"] == "SELL"
    assert result["reward_risk_ratio"] == 2.0


def test_blocks_unapproved_prepared_order():
    engine = build_engine()

    order = build_valid_order()
    order["approved"] = False

    result = engine.validate(
        prepared_order=order,
        market_is_open=True,
        open_symbols=set(),
    )

    assert result["approved"] is False
    assert (
        "prepared_order_not_approved"
        in result["blocking_reasons"]
    )


def test_blocks_wrong_prepared_order_status():
    engine = build_engine()

    order = build_valid_order()
    order["status"] = "BLOCKED"

    result = engine.validate(
        prepared_order=order,
        market_is_open=True,
        open_symbols=set(),
    )

    assert result["approved"] is False
    assert (
        "prepared_order_not_ready"
        in result["blocking_reasons"]
    )


def test_blocks_wrong_decision():
    engine = build_engine()

    order = build_valid_order()
    order["decision"] = "DO_NOT_SUBMIT"

    result = engine.validate(
        prepared_order=order,
        market_is_open=True,
        open_symbols=set(),
    )

    assert result["approved"] is False
    assert (
        "prepared_order_not_submittable"
        in result["blocking_reasons"]
    )


def test_blocks_closed_market():
    engine = build_engine()

    result = engine.validate(
        prepared_order=build_valid_order(),
        market_is_open=False,
        open_symbols=set(),
    )

    assert result["approved"] is False
    assert (
        "market_closed"
        in result["blocking_reasons"]
    )


def test_blocks_duplicate_symbol():
    engine = build_engine()

    result = engine.validate(
        prepared_order=build_valid_order(),
        market_is_open=True,
        open_symbols={
            "NQ",
        },
    )

    assert result["approved"] is False
    assert (
        "symbol_position_already_open"
        in result["blocking_reasons"]
    )


def test_normalizes_open_symbols():
    engine = build_engine()

    result = engine.validate(
        prepared_order=build_valid_order(),
        market_is_open=True,
        open_symbols={
            " nq ",
        },
    )

    assert result["approved"] is False
    assert (
        "symbol_position_already_open"
        in result["blocking_reasons"]
    )


def test_blocks_symbol_not_allowed():
    engine = build_engine()

    order = build_valid_order()
    order["symbol"] = "CL"

    result = engine.validate(
        prepared_order=order,
        market_is_open=True,
        open_symbols=set(),
    )

    assert result["approved"] is False
    assert (
        "symbol_not_allowed"
        in result["blocking_reasons"]
    )


def test_blocks_invalid_quantity():
    engine = build_engine()

    order = build_valid_order()
    order["quantity"] = 0

    result = engine.validate(
        prepared_order=order,
        market_is_open=True,
        open_symbols=set(),
    )

    assert result["approved"] is False
    assert (
        "invalid_quantity"
        in result["blocking_reasons"]
    )


def test_blocks_reward_risk_below_minimum():
    engine = build_engine()

    order = build_valid_order()
    order["take_profit"] = 107.0

    result = engine.validate(
        prepared_order=order,
        market_is_open=True,
        open_symbols=set(),
    )

    assert result["approved"] is False
    assert result["reward_risk_ratio"] == 1.4
    assert (
        "reward_risk_below_minimum"
        in result["blocking_reasons"]
    )


def test_blocks_stop_below_minimum():
    engine = build_engine()

    order = build_valid_order()
    order["stop_loss"] = 99.0
    order["take_profit"] = 102.0

    result = engine.validate(
        prepared_order=order,
        market_is_open=True,
        open_symbols=set(),
    )

    assert result["approved"] is False
    assert (
        "stop_distance_below_minimum"
        in result["blocking_reasons"]
    )


def test_blocks_stop_above_maximum():
    engine = build_engine()

    order = build_valid_order()
    order["stop_loss"] = 40.0
    order["take_profit"] = 220.0

    result = engine.validate(
        prepared_order=order,
        market_is_open=True,
        open_symbols=set(),
    )

    assert result["approved"] is False
    assert (
        "stop_distance_above_maximum"
        in result["blocking_reasons"]
    )


def test_blocks_invalid_buy_levels():
    engine = build_engine()

    order = build_valid_order()
    order["stop_loss"] = 105.0
    order["take_profit"] = 110.0

    result = engine.validate(
        prepared_order=order,
        market_is_open=True,
        open_symbols=set(),
    )

    assert result["approved"] is False
    assert (
        "invalid_buy_levels"
        in result["blocking_reasons"]
    )


def test_blocks_invalid_sell_levels():
    engine = build_engine()

    order = build_valid_order()

    order.update(
        {
            "side": "SELL",
            "stop_loss": 95.0,
            "take_profit": 90.0,
        }
    )

    result = engine.validate(
        prepared_order=order,
        market_is_open=True,
        open_symbols=set(),
    )

    assert result["approved"] is False
    assert (
        "invalid_sell_levels"
        in result["blocking_reasons"]
    )


def test_validates_limit_order():
    engine = build_engine()

    order = build_valid_order()

    order.update(
        {
            "order_type": "LIMIT",
            "limit_price": 99.0,
            "entry_price": 99.0,
            "stop_loss": 94.0,
            "take_profit": 109.0,
        }
    )

    result = engine.validate(
        prepared_order=order,
        market_is_open=True,
        open_symbols=set(),
    )

    assert result["approved"] is True
    assert result["order_type"] == "LIMIT"


def test_blocks_limit_without_limit_price():
    engine = build_engine()

    order = build_valid_order()
    order["order_type"] = "LIMIT"
    order["limit_price"] = None

    result = engine.validate(
        prepared_order=order,
        market_is_open=True,
        open_symbols=set(),
    )

    assert result["approved"] is False
    assert (
        "limit_price_required"
        in result["blocking_reasons"]
    )


def test_rejects_invalid_prepared_order_type():
    engine = build_engine()

    with pytest.raises(
        TypeError,
        match="prepared_order",
    ):
        engine.validate(
            prepared_order=object(),
            market_is_open=True,
            open_symbols=set(),
        )


def test_rejects_invalid_open_symbols_type():
    engine = build_engine()

    with pytest.raises(
        TypeError,
        match="open_symbols",
    ):
        engine.validate(
            prepared_order=build_valid_order(),
            market_is_open=True,
            open_symbols=object(),
        )


@pytest.mark.parametrize(
    (
        "parameter",
        "value",
    ),
    [
        (
            "minimum_reward_risk_ratio",
            0.0,
        ),
        (
            "minimum_stop_points",
            0.0,
        ),
        (
            "maximum_stop_points",
            0.0,
        ),
    ],
)
def test_rejects_invalid_configuration(
    parameter,
    value,
):
    configuration = {
        "minimum_reward_risk_ratio": 2.0,
        "minimum_stop_points": 2.0,
        "maximum_stop_points": 50.0,
        "allowed_symbols": {
            "NQ",
        },
    }

    configuration[
        parameter
    ] = value

    with pytest.raises(
        ValueError,
        match=parameter,
    ):
        OrderValidationEngineV2(
            **configuration,
        )


def test_rejects_maximum_stop_below_minimum():
    with pytest.raises(
        ValueError,
        match="maximum_stop_points",
    ):
        OrderValidationEngineV2(
            minimum_reward_risk_ratio=2.0,
            minimum_stop_points=10.0,
            maximum_stop_points=5.0,
            allowed_symbols={
                "NQ",
            },
        )


def test_rejects_empty_allowed_symbols():
    with pytest.raises(
        ValueError,
        match="allowed_symbols",
    ):
        OrderValidationEngineV2(
            minimum_reward_risk_ratio=2.0,
            minimum_stop_points=2.0,
            maximum_stop_points=50.0,
            allowed_symbols=set(),
        )
