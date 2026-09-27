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


def mutation_authority_probe():
    return {
        "native_mutation_enabled": True,
        "scope": "SIM_MUTATION_TEST_ONLY",
    }


class FakeMutationTransport:
    def __init__(
        self,
        *,
        orders=None,
        positions=None,
    ):
        self.calls = []
        self.connected = False

        self.orders = list(
            orders or []
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
        return []

    def get_positions(self):
        self.calls.append(("get_positions",))

        return [
            dict(row)
            for row in self.positions
        ]

    def submit_order(self, **kwargs):
        raise AssertionError(
            "submit not exercised in R48K"
        )

    def modify_order(
        self,
        **kwargs,
    ):
        self.calls.append(
            ("modify_order", dict(kwargs))
        )

        order_id = kwargs["order_id"]

        return {
            "modified": True,
            "status": "MODIFIED",
            "order_id": order_id,
            "stop_loss": kwargs.get("stop_loss"),
            "take_profit": kwargs.get("take_profit"),
            "limit_price": kwargs.get("limit_price"),
        }

    def cancel_order(
        self,
        **kwargs,
    ):
        self.calls.append(
            ("cancel_order", dict(kwargs))
        )

        return {
            "cancelled": True,
            "status": "CANCELLED",
            "order_id": kwargs["order_id"],
        }

    def close_position(
        self,
        **kwargs,
    ):
        self.calls.append(
            ("close_position", dict(kwargs))
        )

        return {
            "closed": True,
            "status": "CLOSE_ACKNOWLEDGED",
            "position_id": kwargs["position_id"],
            "reason": kwargs["reason"],
        }

    def close_partial(
        self,
        **kwargs,
    ):
        self.calls.append(
            ("close_partial", dict(kwargs))
        )

        raise AssertionError(
            "partial close must remain blocked"
        )


def connector(
    *,
    orders=None,
    positions=None,
    mutation_probe=mutation_authority_probe,
):
    transport = FakeMutationTransport(
        orders=orders,
        positions=positions,
    )

    value = NinjaTraderSimBrokerConnectorV2(
        transport=transport,
        binding_probe=binding_probe,
        mutation_authority_probe=mutation_probe,
    )

    value.connect()

    return value


def test_modify_requires_existing_unique_native_order():
    value = connector()

    with pytest.raises(
        RuntimeError,
        match="native order not found",
    ):
        value.modify_order(
            order_id="native-order-1",
            stop_loss=19950.0,
        )

    assert [
        call[0]
        for call in value.transport.calls
    ] == [
        "connect",
        "get_orders",
    ]


def test_modify_ambiguous_native_identity_fails_closed():
    value = connector(
        orders=[
            {
                "order_id": "native-order-1",
                "status": "WORKING",
            },
            {
                "order_id": "native-order-1",
                "status": "WORKING",
            },
        ]
    )

    with pytest.raises(
        RuntimeError,
        match="ambiguous native order identity",
    ):
        value.modify_order(
            order_id="native-order-1",
            stop_loss=19950.0,
        )

    assert [
        call[0]
        for call in value.transport.calls
    ] == [
        "connect",
        "get_orders",
    ]


def test_modify_calls_native_transport_only_after_identity_proof():
    value = connector(
        orders=[
            {
                "order_id": "native-order-1",
                "status": "WORKING",
                "stop_loss": 19900.0,
            }
        ]
    )

    result = value.modify_order(
        order_id="native-order-1",
        stop_loss=19950.0,
    )

    assert result["modified"] is True
    assert result["status"] == "MODIFIED"
    assert result["order_id"] == "native-order-1"

    assert [
        call[0]
        for call in value.transport.calls
    ] == [
        "connect",
        "get_orders",
        "modify_order",
    ]


def test_identical_modify_is_idempotent_and_not_resent():
    value = connector(
        orders=[
            {
                "order_id": "native-order-1",
                "status": "WORKING",
                "stop_loss": 19950.0,
                "take_profit": 20100.0,
                "limit_price": None,
            }
        ]
    )

    result = value.modify_order(
        order_id="native-order-1",
        stop_loss=19950.0,
        take_profit=20100.0,
    )

    assert result["modified"] is True
    assert result["status"] == "ALREADY_MODIFIED"
    assert result["idempotent_replay"] is True

    assert [
        call[0]
        for call in value.transport.calls
    ] == [
        "connect",
        "get_orders",
    ]


def test_cancel_requires_existing_unique_native_order():
    value = connector()

    with pytest.raises(
        RuntimeError,
        match="native order not found",
    ):
        value.cancel_order(
            order_id="native-order-1",
        )

    assert [
        call[0]
        for call in value.transport.calls
    ] == [
        "connect",
        "get_orders",
    ]


def test_already_cancelled_order_is_idempotent_and_not_resent():
    value = connector(
        orders=[
            {
                "order_id": "native-order-1",
                "status": "CANCELLED",
            }
        ]
    )

    result = value.cancel_order(
        order_id="native-order-1",
    )

    assert result["cancelled"] is True
    assert result["status"] == "ALREADY_CANCELLED"
    assert result["idempotent_replay"] is True

    assert [
        call[0]
        for call in value.transport.calls
    ] == [
        "connect",
        "get_orders",
    ]


def test_cancel_working_order_requires_native_ack():
    value = connector(
        orders=[
            {
                "order_id": "native-order-1",
                "status": "WORKING",
            }
        ]
    )

    result = value.cancel_order(
        order_id="native-order-1",
    )

    assert result["cancelled"] is True
    assert result["status"] == "CANCELLED"
    assert result["order_id"] == "native-order-1"

    assert [
        call[0]
        for call in value.transport.calls
    ] == [
        "connect",
        "get_orders",
        "cancel_order",
    ]


def test_close_requires_existing_unique_native_position():
    value = connector()

    with pytest.raises(
        RuntimeError,
        match="native position not found",
    ):
        value.close_position(
            position_id="native-position-1",
            current_price=20000.0,
            reason="SESSION_CLOSE",
        )

    assert [
        call[0]
        for call in value.transport.calls
    ] == [
        "connect",
        "get_positions",
    ]


def test_already_closed_position_is_idempotent_and_not_resent():
    value = connector(
        positions=[
            {
                "position_id": "native-position-1",
                "status": "CLOSED",
            }
        ]
    )

    result = value.close_position(
        position_id="native-position-1",
        current_price=20000.0,
        reason="SESSION_CLOSE",
    )

    assert result["closed"] is True
    assert result["status"] == "ALREADY_CLOSED"
    assert result["idempotent_replay"] is True

    assert [
        call[0]
        for call in value.transport.calls
    ] == [
        "connect",
        "get_positions",
    ]


def test_open_position_close_requires_native_ack():
    value = connector(
        positions=[
            {
                "position_id": "native-position-1",
                "status": "OPEN",
                "quantity": 1,
            }
        ]
    )

    result = value.close_position(
        position_id="native-position-1",
        current_price=20000.0,
        reason="SESSION_CLOSE",
    )

    assert result["closed"] is True
    assert result["status"] == "CLOSE_ACKNOWLEDGED"
    assert result["position_id"] == "native-position-1"

    assert [
        call[0]
        for call in value.transport.calls
    ] == [
        "connect",
        "get_positions",
        "close_position",
    ]


def test_invalid_native_mutation_ack_fails_closed():
    class BadTransport(
        FakeMutationTransport
    ):
        def cancel_order(
            self,
            **kwargs,
        ):
            self.calls.append(
                ("cancel_order", dict(kwargs))
            )

            return {
                "cancelled": True,
                "status": "CANCELLED",
                "order_id": "wrong-order",
            }

    transport = BadTransport(
        orders=[
            {
                "order_id": "native-order-1",
                "status": "WORKING",
            }
        ]
    )

    value = NinjaTraderSimBrokerConnectorV2(
        transport=transport,
        binding_probe=binding_probe,
        mutation_authority_probe=(
            mutation_authority_probe
        ),
    )

    value.connect()

    with pytest.raises(
        RuntimeError,
        match="invalid native SIM mutation acknowledgement",
    ):
        value.cancel_order(
            order_id="native-order-1",
        )


def test_without_mutation_authority_all_mutations_remain_blocked():
    value = connector(
        orders=[
            {
                "order_id": "native-order-1",
                "status": "WORKING",
            }
        ],
        mutation_probe=None,
    )

    before = list(
        value.transport.calls
    )

    with pytest.raises(
        RuntimeError,
        match="SIM execution authority is disabled",
    ):
        value.cancel_order(
            order_id="native-order-1",
        )

    assert value.transport.calls == before


def test_partial_close_remains_disabled_until_durable_operation_identity_exists():
    value = connector(
        positions=[
            {
                "position_id": "native-position-1",
                "status": "OPEN",
                "quantity": 2,
            }
        ]
    )

    before = list(
        value.transport.calls
    )

    with pytest.raises(
        RuntimeError,
        match="partial close durable identity is required",
    ):
        value.close_partial(
            position_id="native-position-1",
            quantity=1,
            current_price=20000.0,
            reason="PARTIAL_TP",
        )

    assert value.transport.calls == before
