import pytest

from backend.connectors.broker_connector_v2 import (
    BrokerConnectorV2,
)
from backend.connectors.paper_broker_connector_v2 import (
    PaperBrokerConnectorV2,
)
from backend.execution.paper_execution_engine_v2 import (
    PaperExecutionEngineV2,
)


def build_connector(
    *,
    fill_market_orders_immediately: bool = True,
) -> PaperBrokerConnectorV2:
    return PaperBrokerConnectorV2(
        execution_engine=(
            PaperExecutionEngineV2(
                fill_market_orders_immediately=(
                    fill_market_orders_immediately
                ),
                slippage_points=0.25,
            )
        ),
        account_id="paper-test",
        starting_balance=17000.0,
    )


def build_prepared_order(
    *,
    order_type: str = "MARKET",
) -> dict[str, object]:
    return {
        "approved": True,
        "status": "READY_TO_SUBMIT",
        "decision": "SUBMIT_ORDER",
        "execution_mode": "PAPER",
        "symbol": "NQ",
        "side": "BUY",
        "order_type": order_type,
        "quantity": 2,
        "entry_price": 23000.0,
        "limit_price": (
            23000.0
            if order_type == "LIMIT"
            else None
        ),
        "stop_loss": 22980.0,
        "take_profit": 23040.0,
        "blocking_reasons": [],
        "probability": 0.92,
        "confluence_score": 0.90,
        "grade": "A+",
        "warnings": [],
    }


def test_is_broker_connector_contract():
    connector = build_connector()

    assert isinstance(
        connector,
        BrokerConnectorV2,
    )


def test_connect_and_health_check():
    connector = build_connector()

    assert connector.is_connected is False

    result = connector.connect()

    assert result["connected"] is True
    assert result["status"] == "CONNECTED"
    assert connector.is_connected is True

    health = connector.health_check()

    assert health["healthy"] is True
    assert health["status"] == "READY"
    assert health["broker"] == "ARMS_PAPER"


def test_disconnect():
    connector = build_connector()
    connector.connect()

    result = connector.disconnect()

    assert result["connected"] is False
    assert result["status"] == "DISCONNECTED"
    assert connector.is_connected is False


def test_requires_connection_to_submit():
    connector = build_connector()

    with pytest.raises(
        RuntimeError,
        match="conectado",
    ):
        connector.submit_order(
            prepared_order=(
                build_prepared_order()
            )
        )


def test_submits_and_fills_market_order():
    connector = build_connector()
    connector.connect()

    result = connector.submit_order(
        prepared_order=(
            build_prepared_order()
        ),
        client_order_id="signal-001",
    )

    assert result["accepted"] is True
    assert result["status"] == "FILLED"
    assert result["execution_mode"] == "PAPER"
    assert result["broker"] == "ARMS_PAPER"
    assert result["filled_price"] == 23000.25
    assert result["client_order_id"] == "signal-001"
    assert result["position_id"]

    assert len(
        connector.get_orders()
    ) == 1

    assert len(
        connector.get_fills()
    ) == 1

    assert len(
        connector.get_positions()
    ) == 1


def test_client_order_id_is_idempotent():
    connector = build_connector()
    connector.connect()

    first = connector.submit_order(
        prepared_order=(
            build_prepared_order()
        ),
        client_order_id="same-order",
    )

    second = connector.submit_order(
        prepared_order=(
            build_prepared_order()
        ),
        client_order_id="same-order",
    )

    assert (
        first["order_id"]
        == second["order_id"]
    )

    assert (
        second["idempotent_replay"]
        is True
    )

    assert len(
        connector.get_orders()
    ) == 1

    assert len(
        connector.get_fills()
    ) == 1


def test_rejected_order_is_recorded():
    connector = build_connector()
    connector.connect()

    order = build_prepared_order()
    order["approved"] = False
    order["status"] = "BLOCKED"
    order["decision"] = "DO_NOT_SUBMIT"

    result = connector.submit_order(
        prepared_order=order,
    )

    assert result["accepted"] is False
    assert result["status"] == "REJECTED"
    assert len(
        connector.get_orders()
    ) == 1
    assert connector.get_fills() == []
    assert connector.get_positions() == []


def test_modifies_stop_and_target():
    connector = build_connector()
    connector.connect()

    execution = connector.submit_order(
        prepared_order=(
            build_prepared_order()
        )
    )

    modified = connector.modify_order(
        order_id=execution["order_id"],
        stop_loss=22995.0,
        take_profit=23060.0,
    )

    assert modified["modified"] is True
    assert modified["status"] == "MODIFIED"

    order = modified["order"]

    assert order["stop_loss"] == 22995.0
    assert order["take_profit"] == 23060.0

    position = (
        connector.get_positions()[0]
    )

    assert position["stop_loss"] == 22995.0
    assert position["take_profit"] == 23060.0


def test_cannot_cancel_filled_order():
    connector = build_connector()
    connector.connect()

    execution = connector.submit_order(
        prepared_order=(
            build_prepared_order()
        )
    )

    result = connector.cancel_order(
        order_id=execution["order_id"],
    )

    assert result["cancelled"] is False
    assert (
        result["status"]
        == "NOT_CANCELLABLE"
    )


def test_can_cancel_submitted_limit_order():
    connector = build_connector(
        fill_market_orders_immediately=False,
    )
    connector.connect()

    execution = connector.submit_order(
        prepared_order=(
            build_prepared_order(
                order_type="LIMIT",
            )
        )
    )

    assert execution["status"] in {
        "SUBMITTED",
        "FILLED",
    }

    if execution["status"] == "SUBMITTED":
        result = connector.cancel_order(
            order_id=execution["order_id"],
        )

        assert result["cancelled"] is True
        assert result["status"] == "CANCELLED"


def test_closes_open_position():
    connector = build_connector()
    connector.connect()

    execution = connector.submit_order(
        prepared_order=(
            build_prepared_order()
        )
    )

    result = connector.close_position(
        position_id=(
            execution["position_id"]
        ),
        current_price=23020.0,
        reason="MANUAL_TEST",
    )

    assert result["closed"] is True
    assert result["status"] == "CLOSED"

    position = result["position"]

    assert position["exit_price"] == 23020.0
    assert (
        position["close_reason"]
        == "MANUAL_TEST"
    )


def test_get_account():
    connector = build_connector()
    connector.connect()

    account = connector.get_account()

    assert account["account_id"] == "PAPER-TEST"
    assert account["balance"] == 17000.0
    assert account["equity"] == 17000.0
    assert account["execution_mode"] == "PAPER"


def test_rejects_invalid_execution_engine():
    with pytest.raises(
        TypeError,
        match="execution_engine",
    ):
        PaperBrokerConnectorV2(
            execution_engine=object(),
        )


def test_rejects_invalid_starting_balance():
    with pytest.raises(
        ValueError,
        match="starting_balance",
    ):
        PaperBrokerConnectorV2(
            execution_engine=(
                PaperExecutionEngineV2(
                    fill_market_orders_immediately=True,
                    slippage_points=0.25,
                )
            ),
            starting_balance=0.0,
        )
