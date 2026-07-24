import pytest

from backend.execution.execution_manager_v2 import (
    ExecutionManagerV2,
)


def build_manager() -> ExecutionManagerV2:
    return ExecutionManagerV2(
        execution_mode="PAPER",
        maximum_contracts=20,
    )


def build_valid_signal() -> dict[str, object]:
    return {
        "approved": True,
        "status": "READY",
        "decision": "SEND_SIGNAL",
        "symbol": "NQ",
        "timeframe": "5M",
        "direction": "LONG",
        "entry_price": 100.0,
        "stop_loss": 95.0,
        "take_profit": 110.0,
        "contracts": 2,
        "probability": 0.92,
        "confluence_score": 0.90,
        "grade": "A+",
        "blocking_reasons": [],
        "warnings": [],
        "summary": (
            "NQ LONG ENTRY 100.0 "
            "SL 95.0 TP 110.0"
        ),
    }


def test_prepares_long_market_order():
    manager = build_manager()

    result = manager.prepare_order(
        signal=build_valid_signal(),
        order_type="MARKET",
    )

    assert result["approved"] is True
    assert result["status"] == "READY_TO_SUBMIT"
    assert result["decision"] == "SUBMIT_ORDER"
    assert result["execution_mode"] == "PAPER"
    assert result["symbol"] == "NQ"
    assert result["side"] == "BUY"
    assert result["order_type"] == "MARKET"
    assert result["quantity"] == 2
    assert result["entry_price"] == 100.0
    assert result["stop_loss"] == 95.0
    assert result["take_profit"] == 110.0
    assert result["blocking_reasons"] == []


def test_prepares_short_market_order():
    manager = build_manager()

    signal = build_valid_signal()

    signal.update(
        {
            "direction": "SHORT",
            "entry_price": 100.0,
            "stop_loss": 105.0,
            "take_profit": 90.0,
        }
    )

    result = manager.prepare_order(
        signal=signal,
        order_type="MARKET",
    )

    assert result["approved"] is True
    assert result["side"] == "SELL"
    assert result["quantity"] == 2


def test_prepares_limit_order():
    manager = build_manager()

    result = manager.prepare_order(
        signal=build_valid_signal(),
        order_type="LIMIT",
    )

    assert result["approved"] is True
    assert result["order_type"] == "LIMIT"
    assert result["limit_price"] == 100.0


def test_market_order_has_no_limit_price():
    manager = build_manager()

    result = manager.prepare_order(
        signal=build_valid_signal(),
        order_type="MARKET",
    )

    assert result["limit_price"] is None


def test_blocks_unapproved_signal():
    manager = build_manager()

    signal = build_valid_signal()
    signal["approved"] = False
    signal["status"] = "BLOCKED"
    signal["decision"] = "DO_NOT_SEND"

    result = manager.prepare_order(
        signal=signal,
        order_type="MARKET",
    )

    assert result["approved"] is False
    assert result["status"] == "BLOCKED"
    assert result["decision"] == "DO_NOT_SUBMIT"
    assert (
        "signal_not_approved"
        in result["blocking_reasons"]
    )


def test_blocks_signal_with_do_not_send():
    manager = build_manager()

    signal = build_valid_signal()
    signal["decision"] = "DO_NOT_SEND"

    result = manager.prepare_order(
        signal=signal,
        order_type="MARKET",
    )

    assert result["approved"] is False
    assert (
        "signal_decision_not_sendable"
        in result["blocking_reasons"]
    )


def test_blocks_zero_contracts():
    manager = build_manager()

    signal = build_valid_signal()
    signal["contracts"] = 0

    result = manager.prepare_order(
        signal=signal,
        order_type="MARKET",
    )

    assert result["approved"] is False
    assert (
        "invalid_contract_quantity"
        in result["blocking_reasons"]
    )


def test_blocks_contracts_above_maximum():
    manager = build_manager()

    signal = build_valid_signal()
    signal["contracts"] = 21

    result = manager.prepare_order(
        signal=signal,
        order_type="MARKET",
    )

    assert result["approved"] is False
    assert (
        "maximum_contracts_exceeded"
        in result["blocking_reasons"]
    )


def test_rejects_invalid_signal_type():
    manager = build_manager()

    with pytest.raises(
        TypeError,
        match="signal",
    ):
        manager.prepare_order(
            signal=object(),
            order_type="MARKET",
        )


def test_rejects_invalid_direction():
    manager = build_manager()

    signal = build_valid_signal()
    signal["direction"] = "SIDEWAYS"

    with pytest.raises(
        ValueError,
        match="direction",
    ):
        manager.prepare_order(
            signal=signal,
            order_type="MARKET",
        )


def test_rejects_invalid_order_type():
    manager = build_manager()

    with pytest.raises(
        ValueError,
        match="order_type",
    ):
        manager.prepare_order(
            signal=build_valid_signal(),
            order_type="ICEBERG",
        )


def test_rejects_invalid_long_prices():
    manager = build_manager()

    signal = build_valid_signal()
    signal["stop_loss"] = 105.0

    with pytest.raises(
        ValueError,
        match="stop_loss",
    ):
        manager.prepare_order(
            signal=signal,
            order_type="MARKET",
        )


def test_rejects_invalid_short_prices():
    manager = build_manager()

    signal = build_valid_signal()

    signal.update(
        {
            "direction": "SHORT",
            "stop_loss": 95.0,
            "take_profit": 110.0,
        }
    )

    with pytest.raises(
        ValueError,
        match="stop_loss",
    ):
        manager.prepare_order(
            signal=signal,
            order_type="MARKET",
        )


def test_normalizes_symbol_and_order_type():
    manager = build_manager()

    signal = build_valid_signal()
    signal["symbol"] = " nq "

    result = manager.prepare_order(
        signal=signal,
        order_type=" market ",
    )

    assert result["symbol"] == "NQ"
    assert result["order_type"] == "MARKET"


def test_rejects_invalid_execution_mode():
    with pytest.raises(
        ValueError,
        match="execution_mode",
    ):
        ExecutionManagerV2(
            execution_mode="UNKNOWN",
            maximum_contracts=20,
        )


def test_rejects_invalid_maximum_contracts():
    with pytest.raises(
        ValueError,
        match="maximum_contracts",
    ):
        ExecutionManagerV2(
            execution_mode="PAPER",
            maximum_contracts=0,
        )
