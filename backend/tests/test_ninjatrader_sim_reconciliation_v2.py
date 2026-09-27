import pytest

from backend.connectors.ninjatrader_sim_broker_connector_v2 import (
    NinjaTraderSimBrokerConnectorV2,
)


def binding_probe():
    return {
        "future_sim_eligible": True,
        "sim_runtime_revalidation": "PASS",
        "sim_execution_authority": "DISABLED",
        "external_order_authority": False,
    }


class FakeReconciliationTransport:
    def __init__(
        self,
        *,
        orders=None,
        fills=None,
        positions=None,
    ):
        self.connected = False
        self.calls = []

        self.orders = list(
            orders or []
        )
        self.fills = list(
            fills or []
        )
        self.positions = list(
            positions or []
        )

    def connect(self):
        self.calls.append(("connect",))
        self.connected = True
        return {
            "connected": True,
            "status": "CONNECTED",
        }

    def disconnect(self):
        self.calls.append(("disconnect",))
        self.connected = False
        return {
            "connected": False,
            "status": "DISCONNECTED",
        }

    def health_check(self):
        self.calls.append(("health_check",))
        return {
            "healthy": self.connected,
            "connected": self.connected,
        }

    def get_account(self):
        self.calls.append(("get_account",))
        return {
            "provider": "Simulator",
        }

    def get_orders(self):
        self.calls.append(("get_orders",))
        return [
            dict(row)
            for row in self.orders
        ]

    def get_fills(self):
        self.calls.append(("get_fills",))
        return [
            dict(row)
            for row in self.fills
        ]

    def get_positions(self):
        self.calls.append(("get_positions",))
        return [
            dict(row)
            for row in self.positions
        ]

    def submit_order(self, **kwargs):
        raise AssertionError(
            "R48I reconciliation must not submit"
        )

    def modify_order(self, **kwargs):
        raise AssertionError(
            "R48I reconciliation must not modify"
        )

    def cancel_order(self, **kwargs):
        raise AssertionError(
            "R48I reconciliation must not cancel"
        )

    def close_partial(self, **kwargs):
        raise AssertionError(
            "R48I reconciliation must not close"
        )

    def close_position(self, **kwargs):
        raise AssertionError(
            "R48I reconciliation must not close"
        )


def connector(
    *,
    orders=None,
    fills=None,
    positions=None,
):
    transport = FakeReconciliationTransport(
        orders=orders,
        fills=fills,
        positions=positions,
    )

    value = NinjaTraderSimBrokerConnectorV2(
        transport=transport,
        binding_probe=binding_probe,
    )

    value.connect()

    return value


def test_reconcile_requires_non_empty_client_order_id():
    value = connector()

    for bad in (
        None,
        "",
        "   ",
    ):
        with pytest.raises(
            ValueError,
            match="client_order_id is required",
        ):
            value.reconcile_order(
                client_order_id=bad,
            )


def test_missing_native_order_returns_unresolved_without_inventing_rejection():
    value = connector()

    result = value.reconcile_order(
        client_order_id="durable-op-1",
    )

    assert result == {
        "resolved": False,
        "client_order_id": "durable-op-1",
        "status": "NOT_FOUND",
        "order": None,
        "fills": [],
        "position": None,
        "fill_confirmed": False,
        "position_confirmed": False,
    }


def test_acknowledged_order_without_fill_remains_acknowledged():
    value = connector(
        orders=[
            {
                "order_id": "native-order-1",
                "client_order_id": "durable-op-1",
                "accepted": True,
                "status": "ACKNOWLEDGED",
                "symbol": "NQ",
                "side": "BUY",
                "quantity": 1,
            }
        ]
    )

    result = value.reconcile_order(
        client_order_id="durable-op-1",
    )

    assert result["resolved"] is True
    assert result["status"] == "ACKNOWLEDGED"
    assert result["fill_confirmed"] is False
    assert result["position_confirmed"] is False
    assert result["fills"] == []
    assert result["position"] is None


@pytest.mark.parametrize(
    "status",
    [
        "ACKNOWLEDGED",
        "WORKING",
        "PARTIALLY_FILLED",
        "FILLED",
        "REJECTED",
        "CANCELLED",
    ],
)
def test_only_known_native_order_statuses_are_admitted(status):
    fills = []

    if status == "FILLED":
        fills = [
            {
                "fill_id": "native-fill-1",
                "order_id": "native-order-1",
                "quantity": 1,
                "filled_price": 20000.0,
            }
        ]

    value = connector(
        orders=[
            {
                "order_id": "native-order-1",
                "client_order_id": "durable-op-1",
                "accepted": (
                    status
                    not in {
                        "REJECTED",
                        "CANCELLED",
                    }
                ),
                "status": status,
            }
        ],
        fills=fills,
    )

    result = value.reconcile_order(
        client_order_id="durable-op-1",
    )

    assert result["status"] == status


def test_unknown_native_order_status_fails_closed():
    value = connector(
        orders=[
            {
                "order_id": "native-order-1",
                "client_order_id": "durable-op-1",
                "accepted": True,
                "status": "MYSTERY",
            }
        ]
    )

    with pytest.raises(
        RuntimeError,
        match="invalid native SIM order state",
    ):
        value.reconcile_order(
            client_order_id="durable-op-1",
        )


def test_duplicate_native_order_identity_fails_closed():
    value = connector(
        orders=[
            {
                "order_id": "native-order-1",
                "client_order_id": "durable-op-1",
                "accepted": True,
                "status": "WORKING",
            },
            {
                "order_id": "native-order-2",
                "client_order_id": "durable-op-1",
                "accepted": True,
                "status": "WORKING",
            },
        ]
    )

    with pytest.raises(
        RuntimeError,
        match="ambiguous native client_order_id",
    ):
        value.reconcile_order(
            client_order_id="durable-op-1",
        )


def test_filled_order_requires_matching_native_fill():
    value = connector(
        orders=[
            {
                "order_id": "native-order-1",
                "client_order_id": "durable-op-1",
                "accepted": True,
                "status": "FILLED",
            }
        ]
    )

    with pytest.raises(
        RuntimeError,
        match="FILLED order lacks native fill evidence",
    ):
        value.reconcile_order(
            client_order_id="durable-op-1",
        )


def test_fill_for_different_order_does_not_confirm_execution():
    value = connector(
        orders=[
            {
                "order_id": "native-order-1",
                "client_order_id": "durable-op-1",
                "accepted": True,
                "status": "FILLED",
            }
        ],
        fills=[
            {
                "fill_id": "native-fill-other",
                "order_id": "native-order-other",
                "quantity": 1,
                "filled_price": 20000.0,
            }
        ],
    )

    with pytest.raises(
        RuntimeError,
        match="FILLED order lacks native fill evidence",
    ):
        value.reconcile_order(
            client_order_id="durable-op-1",
        )


def test_matching_fill_is_external_execution_evidence():
    value = connector(
        orders=[
            {
                "order_id": "native-order-1",
                "client_order_id": "durable-op-1",
                "accepted": True,
                "status": "FILLED",
                "symbol": "NQ",
                "side": "BUY",
                "quantity": 1,
            }
        ],
        fills=[
            {
                "fill_id": "native-fill-1",
                "order_id": "native-order-1",
                "symbol": "NQ",
                "side": "BUY",
                "quantity": 1,
                "filled_price": 20000.0,
            }
        ],
    )

    result = value.reconcile_order(
        client_order_id="durable-op-1",
    )

    assert result["resolved"] is True
    assert result["status"] == "FILLED"
    assert result["fill_confirmed"] is True
    assert result["fills"][0]["fill_id"] == "native-fill-1"

    assert result["position"] is None
    assert result["position_confirmed"] is False


def test_matching_native_position_is_admitted_only_by_order_identity():
    value = connector(
        orders=[
            {
                "order_id": "native-order-1",
                "client_order_id": "durable-op-1",
                "accepted": True,
                "status": "FILLED",
                "symbol": "NQ",
                "side": "BUY",
                "quantity": 1,
            }
        ],
        fills=[
            {
                "fill_id": "native-fill-1",
                "order_id": "native-order-1",
                "symbol": "NQ",
                "side": "BUY",
                "quantity": 1,
                "filled_price": 20000.0,
            }
        ],
        positions=[
            {
                "position_id": "native-position-1",
                "order_id": "native-order-1",
                "symbol": "NQ",
                "side": "BUY",
                "quantity": 1,
                "status": "OPEN",
            },
            {
                "position_id": "native-position-other",
                "order_id": "other-order",
                "symbol": "NQ",
                "side": "SELL",
                "quantity": 1,
                "status": "OPEN",
            },
        ],
    )

    result = value.reconcile_order(
        client_order_id="durable-op-1",
    )

    assert result["fill_confirmed"] is True
    assert result["position_confirmed"] is True
    assert (
        result["position"]["position_id"]
        == "native-position-1"
    )


def test_multiple_native_positions_for_same_order_are_ambiguous():
    value = connector(
        orders=[
            {
                "order_id": "native-order-1",
                "client_order_id": "durable-op-1",
                "accepted": True,
                "status": "FILLED",
            }
        ],
        fills=[
            {
                "fill_id": "native-fill-1",
                "order_id": "native-order-1",
                "quantity": 1,
                "filled_price": 20000.0,
            }
        ],
        positions=[
            {
                "position_id": "native-position-1",
                "order_id": "native-order-1",
            },
            {
                "position_id": "native-position-2",
                "order_id": "native-order-1",
            },
        ],
    )

    with pytest.raises(
        RuntimeError,
        match="ambiguous native position evidence",
    ):
        value.reconcile_order(
            client_order_id="durable-op-1",
        )


def test_reconciliation_is_read_only_and_never_calls_mutation_transport():
    value = connector(
        orders=[
            {
                "order_id": "native-order-1",
                "client_order_id": "durable-op-1",
                "accepted": True,
                "status": "WORKING",
            }
        ]
    )

    value.reconcile_order(
        client_order_id="durable-op-1",
    )

    assert [
        call[0]
        for call in value.transport.calls
    ] == [
        "connect",
        "get_orders",
        "get_fills",
        "get_positions",
    ]
