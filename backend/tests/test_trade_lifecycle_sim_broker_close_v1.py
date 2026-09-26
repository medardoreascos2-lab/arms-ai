from backend.connectors.broker_connector_v2 import BrokerConnectorV2
from backend.tests.test_trade_lifecycle_broker_connector_integration_v2 import (
    build_service,
    build_signal,
)


class FakeSimBrokerV1(BrokerConnectorV2):
    VALID_FINAL_ORDER_STATUSES = {
        "FILLED",
        "CANCELLED",
        "REJECTED",
    }

    def __init__(self):
        self.account_id = "SIM101-TEST"
        self.starting_balance = 17000.0
        self._connected = False
        self.close_calls = []

    @property
    def broker_name(self):
        return "FAKE_SIM101"

    @property
    def execution_mode(self):
        return "SIM"

    @property
    def is_connected(self):
        return self._connected

    def connect(self):
        self._connected = True
        return {
            "connected": True,
            "status": "CONNECTED",
            "broker": self.broker_name,
            "execution_mode": self.execution_mode,
            "account_id": self.account_id,
        }

    def disconnect(self):
        self._connected = False
        return {
            "connected": False,
            "status": "DISCONNECTED",
        }

    def health_check(self):
        return {
            "healthy": self._connected,
            "status": "READY" if self._connected else "DISCONNECTED",
        }

    def submit_order(
        self,
        *,
        prepared_order,
        client_order_id=None,
    ):
        return {
            "accepted": True,
            "status": "FILLED",
            "broker": self.broker_name,
            "execution_mode": "SIM",
            "order_id": "SIM-ORDER-1",
            "position_id": "SIM-POSITION-1",
            "client_order_id": client_order_id,
            "symbol": prepared_order["symbol"],
            "side": prepared_order["side"],
            "quantity": prepared_order["quantity"],
            "filled_price": prepared_order["entry_price"],
            "stop_loss": prepared_order["stop_loss"],
            "take_profit": prepared_order["take_profit"],
        }

    def modify_order(
        self,
        *,
        order_id,
        stop_loss=None,
        take_profit=None,
        limit_price=None,
    ):
        raise AssertionError("modify_order not expected")

    def cancel_order(self, *, order_id):
        raise AssertionError("cancel_order not expected")

    def close_partial(
        self,
        *,
        position_id,
        quantity,
        current_price,
        reason,
    ):
        raise AssertionError("close_partial not expected")

    def close_position(
        self,
        *,
        position_id,
        current_price,
        reason,
    ):
        self.close_calls.append(
            {
                "position_id": position_id,
                "current_price": current_price,
                "reason": reason,
            }
        )
        return {
            "closed": True,
            "status": "CLOSED",
            "position_id": position_id,
        }

    def get_account(self):
        return {
            "account_id": self.account_id,
            "execution_mode": self.execution_mode,
        }

    def get_positions(self):
        return []

    def get_orders(self):
        return []

    def get_fills(self):
        return []


def test_close_active_position_delegates_to_injected_sim_broker():
    broker = FakeSimBrokerV1()

    lifecycle = build_service(
        broker_connector_v2=broker,
    )

    class FakeDurability:
        operation = {
            "operation_id": "durable-close-operation-123",
        }

    lifecycle._durability = FakeDurability()

    result = lifecycle.submit_signal.__wrapped__(
        lifecycle,
        signal=build_signal(),
        order_type="MARKET",
        risk_context={
            "account_balance": 17000.0,
            "risk_percent": 0.5,
            "point_value": 2.0,
            "daily_pnl": 0.0,
            "total_drawdown": 0.0,
        },
    )

    assert result["accepted"] is True

    position = result["position"]

    assert position is not None
    assert position["broker_position_id"] == "SIM-POSITION-1"
    assert position["execution_mode"] == "SIM"

    lifecycle.close_active_position.__wrapped__(
        lifecycle,
        position_id=position["position_id"],
        current_price=23010.0,
        reason="SESSION_CLOSE",
    )

    assert broker.close_calls == [
        {
            "position_id": "SIM-POSITION-1",
            "current_price": 23010.0,
            "reason": "SESSION_CLOSE",
        }
    ]


class CapturingSimBrokerV1(FakeSimBrokerV1):
    def __init__(self):
        super().__init__()
        self.submitted_client_order_ids = []

    def submit_order(
        self,
        *,
        prepared_order,
        client_order_id=None,
    ):
        self.submitted_client_order_ids.append(
            client_order_id
        )
        return super().submit_order(
            prepared_order=prepared_order,
            client_order_id=client_order_id,
        )


def test_sim_submission_uses_current_durable_operation_id():
    broker = CapturingSimBrokerV1()

    lifecycle = build_service(
        broker_connector_v2=broker,
    )

    class FakeDurability:
        operation = {
            "operation_id": "durable-operation-123",
        }

    lifecycle._durability = FakeDurability()

    result = lifecycle.submit_signal.__wrapped__(
        lifecycle,
        signal=build_signal(),
        order_type="MARKET",
        risk_context={
            "account_balance": 17000.0,
            "risk_percent": 0.5,
            "point_value": 2.0,
            "daily_pnl": 0.0,
            "total_drawdown": 0.0,
        },
    )

    assert result["accepted"] is True
    assert broker.submitted_client_order_ids == [
        "durable-operation-123"
    ]


def test_sim_submission_without_durable_identity_fails_before_broker():
    broker = CapturingSimBrokerV1()

    lifecycle = build_service(
        broker_connector_v2=broker,
    )

    try:
        lifecycle.submit_signal(
            signal=build_signal(),
            order_type="MARKET",
            risk_context={
                "account_balance": 17000.0,
                "risk_percent": 0.5,
                "point_value": 2.0,
                "daily_pnl": 0.0,
                "total_drawdown": 0.0,
            },
        )
    except RuntimeError as exc:
        assert str(exc) == "SIM durable operation identity required."
    else:
        raise AssertionError(
            "SIM submission without durable identity must fail closed."
        )

    assert broker.submitted_client_order_ids == []
