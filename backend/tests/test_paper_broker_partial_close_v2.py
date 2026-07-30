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
) -> PaperBrokerConnectorV2:
    connector = PaperBrokerConnectorV2(
        execution_engine=(
            PaperExecutionEngineV2(
                fill_market_orders_immediately=True,
                slippage_points=0.25,
            )
        ),
        account_id="PARTIAL-TEST",
        starting_balance=17000.0,
    )

    connector.connect()

    return connector


def build_order(
    *,
    quantity: float = 4.0,
) -> dict[str, object]:
    return {
        "approved": True,
        "status": "READY_TO_SUBMIT",
        "decision": "SUBMIT_ORDER",
        "execution_mode": "PAPER",
        "symbol": "NQ",
        "side": "BUY",
        "order_type": "MARKET",
        "quantity": quantity,
        "entry_price": 23000.0,
        "limit_price": None,
        "stop_loss": 22980.0,
        "take_profit": 23040.0,
        "blocking_reasons": [],
        "probability": 0.92,
        "confluence_score": 0.90,
        "grade": "A+",
        "warnings": [],
    }


def open_position(
    connector: PaperBrokerConnectorV2,
    *,
    quantity: float = 4.0,
) -> dict[str, object]:
    execution = connector.submit_order(
        prepared_order=(
            build_order(
                quantity=quantity,
            )
        )
    )

    assert execution["accepted"] is True
    assert execution["status"] == "FILLED"
    assert execution["position_id"]

    return execution


def test_implements_broker_contract():
    connector = build_connector()

    assert isinstance(
        connector,
        BrokerConnectorV2,
    )


def test_closes_part_of_open_position():
    connector = build_connector()
    execution = open_position(
        connector,
        quantity=4.0,
    )

    broker_position_id = str(
        execution["position_id"]
    )

    result = connector.close_partial(
        position_id=(
            broker_position_id
        ),
        quantity=1.0,
        current_price=23020.0,
        reason="PARTIAL_TAKE_PROFIT",
    )

    assert result["closed"] is True
    assert result["partial"] is True
    assert (
        result["status"]
        == "PARTIALLY_CLOSED"
    )
    assert (
        result["closed_quantity"]
        == 1.0
    )
    assert (
        result["remaining_quantity"]
        == 3.0
    )

    position = result["position"]

    assert (
        position["position_id"]
        == broker_position_id
    )
    assert position["status"] == "OPEN"
    assert position["quantity"] == 3.0


def test_partial_close_keeps_same_position_id():
    connector = build_connector()
    execution = open_position(
        connector,
        quantity=2.0,
    )

    original_id = str(
        execution["position_id"]
    )

    result = connector.close_partial(
        position_id=original_id,
        quantity=1.0,
        current_price=23010.0,
        reason="REDUCE_RISK",
    )

    stored = (
        connector.get_positions()[0]
    )

    assert (
        result["position_id"]
        == original_id
    )
    assert (
        stored["position_id"]
        == original_id
    )
    assert stored["quantity"] == 1.0
    assert stored["status"] == "OPEN"


def test_partial_close_creates_fill():
    connector = build_connector()
    execution = open_position(
        connector,
        quantity=4.0,
    )

    fills_before = len(
        connector.get_fills()
    )

    result = connector.close_partial(
        position_id=str(
            execution["position_id"]
        ),
        quantity=2.0,
        current_price=23015.0,
        reason="LOCK_PROFIT",
    )

    fills = connector.get_fills()

    assert len(fills) == (
        fills_before + 1
    )

    partial_fill = fills[-1]

    assert (
        partial_fill["fill_type"]
        == "PARTIAL_CLOSE"
    )
    assert partial_fill["quantity"] == 2.0
    assert (
        partial_fill["filled_price"]
        == 23015.0
    )
    assert (
        partial_fill["position_id"]
        == result["position_id"]
    )


def test_accumulates_partial_closed_quantity():
    connector = build_connector()
    execution = open_position(
        connector,
        quantity=4.0,
    )

    position_id = str(
        execution["position_id"]
    )

    first = connector.close_partial(
        position_id=position_id,
        quantity=1.0,
        current_price=23010.0,
        reason="PARTIAL_1",
    )

    second = connector.close_partial(
        position_id=position_id,
        quantity=1.0,
        current_price=23020.0,
        reason="PARTIAL_2",
    )

    assert (
        first["remaining_quantity"]
        == 3.0
    )
    assert (
        second["remaining_quantity"]
        == 2.0
    )

    assert (
        second["position"][
            "partial_closed_quantity"
        ]
        == 2.0
    )


def test_rejects_quantity_equal_to_open_quantity():
    connector = build_connector()
    execution = open_position(
        connector,
        quantity=2.0,
    )

    result = connector.close_partial(
        position_id=str(
            execution["position_id"]
        ),
        quantity=2.0,
        current_price=23020.0,
        reason="INVALID_TEST",
    )

    assert result["closed"] is False
    assert result["partial"] is False
    assert (
        result["status"]
        == "INVALID_PARTIAL_QUANTITY"
    )

    position = (
        connector.get_positions()[0]
    )

    assert position["quantity"] == 2.0
    assert position["status"] == "OPEN"


def test_rejects_quantity_greater_than_open():
    connector = build_connector()
    execution = open_position(
        connector,
        quantity=2.0,
    )

    result = connector.close_partial(
        position_id=str(
            execution["position_id"]
        ),
        quantity=3.0,
        current_price=23020.0,
        reason="INVALID_TEST",
    )

    assert result["closed"] is False
    assert (
        result["status"]
        == "INVALID_PARTIAL_QUANTITY"
    )


def test_returns_not_found():
    connector = build_connector()

    result = connector.close_partial(
        position_id="missing-position",
        quantity=1.0,
        current_price=23020.0,
        reason="TEST",
    )

    assert result["closed"] is False
    assert result["status"] == "NOT_FOUND"


def test_requires_connection():
    connector = PaperBrokerConnectorV2(
        execution_engine=(
            PaperExecutionEngineV2(
                fill_market_orders_immediately=True,
                slippage_points=0.25,
            )
        )
    )

    with pytest.raises(
        RuntimeError,
        match="conectado",
    ):
        connector.close_partial(
            position_id="position-1",
            quantity=1.0,
            current_price=23020.0,
            reason="TEST",
        )


def test_rejects_non_positive_quantity():
    connector = build_connector()

    with pytest.raises(
        ValueError,
        match="quantity",
    ):
        connector.close_partial(
            position_id="position-1",
            quantity=0.0,
            current_price=23020.0,
            reason="TEST",
        )


def test_rejects_invalid_price():
    connector = build_connector()

    with pytest.raises(
        ValueError,
        match="current_price",
    ):
        connector.close_partial(
            position_id="position-1",
            quantity=1.0,
            current_price=0.0,
            reason="TEST",
        )
