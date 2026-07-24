import pytest

from backend.execution.paper_execution_engine_v2 import (
    PaperExecutionEngineV2,
)


def build_engine() -> PaperExecutionEngineV2:
    return PaperExecutionEngineV2(
        fill_market_orders_immediately=True,
        slippage_points=0.25,
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
        "probability": 0.92,
        "confluence_score": 0.90,
        "grade": "A+",
        "warnings": [],
    }


def test_executes_market_buy_order():
    engine = build_engine()

    result = engine.execute(
        prepared_order=build_valid_order(),
    )

    assert result["accepted"] is True
    assert result["status"] == "FILLED"
    assert result["execution_mode"] == "PAPER"
    assert result["symbol"] == "NQ"
    assert result["side"] == "BUY"
    assert result["order_type"] == "MARKET"
    assert result["quantity"] == 2
    assert result["requested_price"] == 100.0
    assert result["filled_price"] == 100.25
    assert result["stop_loss"] == 95.0
    assert result["take_profit"] == 110.0
    assert result["order_id"]
    assert result["rejection_reasons"] == []


def test_executes_market_sell_order():
    engine = build_engine()

    order = build_valid_order()

    order.update(
        {
            "side": "SELL",
            "entry_price": 100.0,
            "stop_loss": 105.0,
            "take_profit": 90.0,
        }
    )

    result = engine.execute(
        prepared_order=order,
    )

    assert result["accepted"] is True
    assert result["status"] == "FILLED"
    assert result["filled_price"] == 99.75


def test_submits_limit_order_without_immediate_fill():
    engine = build_engine()

    order = build_valid_order()

    order.update(
        {
            "order_type": "LIMIT",
            "limit_price": 99.0,
        }
    )

    result = engine.execute(
        prepared_order=order,
    )

    assert result["accepted"] is True
    assert result["status"] == "SUBMITTED"
    assert result["requested_price"] == 99.0
    assert result["filled_price"] is None


def test_rejects_unapproved_order():
    engine = build_engine()

    order = build_valid_order()
    order["approved"] = False
    order["status"] = "BLOCKED"
    order["decision"] = "DO_NOT_SUBMIT"

    result = engine.execute(
        prepared_order=order,
    )

    assert result["accepted"] is False
    assert result["status"] == "REJECTED"
    assert (
        "prepared_order_not_approved"
        in result["rejection_reasons"]
    )


def test_rejects_wrong_execution_mode():
    engine = build_engine()

    order = build_valid_order()
    order["execution_mode"] = "LIVE"

    result = engine.execute(
        prepared_order=order,
    )

    assert result["accepted"] is False
    assert (
        "execution_mode_not_paper"
        in result["rejection_reasons"]
    )


def test_rejects_wrong_decision():
    engine = build_engine()

    order = build_valid_order()
    order["decision"] = "DO_NOT_SUBMIT"

    result = engine.execute(
        prepared_order=order,
    )

    assert result["accepted"] is False
    assert (
        "prepared_order_not_submittable"
        in result["rejection_reasons"]
    )


def test_rejects_invalid_quantity():
    engine = build_engine()

    order = build_valid_order()
    order["quantity"] = 0

    result = engine.execute(
        prepared_order=order,
    )

    assert result["accepted"] is False
    assert (
        "invalid_quantity"
        in result["rejection_reasons"]
    )


def test_rejects_invalid_prepared_order_type():
    engine = build_engine()

    with pytest.raises(
        TypeError,
        match="prepared_order",
    ):
        engine.execute(
            prepared_order=object(),
        )


def test_rejects_invalid_side():
    engine = build_engine()

    order = build_valid_order()
    order["side"] = "HOLD"

    with pytest.raises(
        ValueError,
        match="side",
    ):
        engine.execute(
            prepared_order=order,
        )


def test_rejects_invalid_order_type():
    engine = build_engine()

    order = build_valid_order()
    order["order_type"] = "ICEBERG"

    with pytest.raises(
        ValueError,
        match="order_type",
    ):
        engine.execute(
            prepared_order=order,
        )


def test_rejects_limit_without_limit_price():
    engine = build_engine()

    order = build_valid_order()
    order["order_type"] = "LIMIT"
    order["limit_price"] = None

    with pytest.raises(
        ValueError,
        match="limit_price",
    ):
        engine.execute(
            prepared_order=order,
        )


def test_rejects_negative_slippage():
    with pytest.raises(
        ValueError,
        match="slippage_points",
    ):
        PaperExecutionEngineV2(
            fill_market_orders_immediately=True,
            slippage_points=-0.25,
        )


def test_can_disable_immediate_market_fill():
    engine = PaperExecutionEngineV2(
        fill_market_orders_immediately=False,
        slippage_points=0.25,
    )

    result = engine.execute(
        prepared_order=build_valid_order(),
    )

    assert result["accepted"] is True
    assert result["status"] == "SUBMITTED"
    assert result["filled_price"] is None
