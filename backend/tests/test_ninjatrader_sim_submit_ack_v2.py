import pytest

from backend.connectors.ninjatrader_sim_broker_connector_v2 import (
    NinjaTraderSimBrokerConnectorV2,
)


class FakeAckTransport:
    def __init__(self):
        self.calls = []
        self.connected = False
        self.orders = []

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

    def get_positions(self):
        self.calls.append(("get_positions",))
        return []

    def get_orders(self):
        self.calls.append(("get_orders",))
        return [
            dict(row)
            for row in self.orders
        ]

    def get_fills(self):
        self.calls.append(("get_fills",))
        return []

    def submit_order(
        self,
        *,
        prepared_order,
        client_order_id,
    ):
        self.calls.append(
            (
                "submit_order",
                {
                    "prepared_order": dict(prepared_order),
                    "client_order_id": client_order_id,
                },
            )
        )

        native = {
            "accepted": True,
            "status": "ACKNOWLEDGED",
            "order_id": "native-order-101",
            "client_order_id": client_order_id,
            "symbol": prepared_order["symbol"],
            "side": prepared_order["side"],
            "quantity": prepared_order["quantity"],
        }

        self.orders.append(
            dict(native)
        )

        return dict(native)

    def modify_order(self, **kwargs):
        raise AssertionError(
            "modify not allowed in R48H"
        )

    def cancel_order(self, **kwargs):
        raise AssertionError(
            "cancel not allowed in R48H"
        )

    def close_partial(self, **kwargs):
        raise AssertionError(
            "partial close not allowed in R48H"
        )

    def close_position(self, **kwargs):
        raise AssertionError(
            "close not allowed in R48H"
        )


def eligible_binding_probe():
    return {
        "future_sim_eligible": True,
        "sim_runtime_revalidation": "PASS",
        "sim_execution_authority": "DISABLED",
        "external_order_authority": False,
    }


def ack_authority_probe():
    return {
        "ack_submit_enabled": True,
        "scope": "SIM_ACK_TEST_ONLY",
    }


def connector(transport=None):
    return NinjaTraderSimBrokerConnectorV2(
        transport=(
            transport
            if transport is not None
            else FakeAckTransport()
        ),
        binding_probe=eligible_binding_probe,
        ack_authority_probe=ack_authority_probe,
    )


def prepared():
    return {
        "symbol": "NQ",
        "side": "BUY",
        "quantity": 1,
        "order_type": "MARKET",
    }


def test_submit_requires_non_empty_client_order_id():
    value = connector()
    value.connect()

    for bad in (
        None,
        "",
        "   ",
    ):
        with pytest.raises(
            ValueError,
            match="client_order_id is required",
        ):
            value.submit_order(
                prepared_order=prepared(),
                client_order_id=bad,
            )


def test_submit_requires_dict_prepared_order():
    value = connector()
    value.connect()

    with pytest.raises(
        TypeError,
        match="prepared_order must be a dict",
    ):
        value.submit_order(
            prepared_order=None,
            client_order_id="durable-op-1",
        )


def test_new_submit_returns_native_ack_without_inventing_fill_or_position():
    value = connector()
    value.connect()

    result = value.submit_order(
        prepared_order=prepared(),
        client_order_id="durable-op-1",
    )

    assert result["accepted"] is True
    assert result["status"] == "ACKNOWLEDGED"
    assert result["order_id"] == "native-order-101"
    assert result["client_order_id"] == "durable-op-1"

    assert "fill_id" not in result
    assert "filled_price" not in result
    assert "position_id" not in result
    assert "broker_position_id" not in result

    assert [
        call[0]
        for call in value.transport.calls
    ] == [
        "connect",
        "get_orders",
        "submit_order",
    ]


def test_duplicate_client_order_id_uses_native_evidence_and_does_not_resubmit():
    transport = FakeAckTransport()

    transport.orders.append(
        {
            "accepted": True,
            "status": "ACKNOWLEDGED",
            "order_id": "native-existing-1",
            "client_order_id": "durable-op-1",
            "symbol": "NQ",
            "side": "BUY",
            "quantity": 1,
        }
    )

    value = connector(transport)
    value.connect()

    result = value.submit_order(
        prepared_order=prepared(),
        client_order_id="durable-op-1",
    )

    assert result["order_id"] == "native-existing-1"
    assert result["idempotent_replay"] is True

    assert [
        call[0]
        for call in transport.calls
    ] == [
        "connect",
        "get_orders",
    ]


def test_duplicate_native_evidence_is_ambiguous_and_fails_closed():
    transport = FakeAckTransport()

    transport.orders.extend(
        [
            {
                "accepted": True,
                "status": "ACKNOWLEDGED",
                "order_id": "native-1",
                "client_order_id": "durable-op-1",
            },
            {
                "accepted": True,
                "status": "ACKNOWLEDGED",
                "order_id": "native-2",
                "client_order_id": "durable-op-1",
            },
        ]
    )

    value = connector(transport)
    value.connect()

    with pytest.raises(
        RuntimeError,
        match="ambiguous native client_order_id",
    ):
        value.submit_order(
            prepared_order=prepared(),
            client_order_id="durable-op-1",
        )

    assert [
        call[0]
        for call in transport.calls
    ] == [
        "connect",
        "get_orders",
    ]


@pytest.mark.parametrize(
    "native",
    [
        None,
        [],
        {},
        {
            "accepted": True,
            "status": "FILLED",
            "order_id": "native-1",
            "client_order_id": "durable-op-1",
        },
        {
            "accepted": True,
            "status": "ACKNOWLEDGED",
            "order_id": "",
            "client_order_id": "durable-op-1",
        },
        {
            "accepted": True,
            "status": "ACKNOWLEDGED",
            "order_id": "native-1",
            "client_order_id": "different-op",
        },
    ],
)
def test_invalid_native_ack_fails_closed(native):
    class BadAckTransport(
        FakeAckTransport
    ):
        def submit_order(
            self,
            *,
            prepared_order,
            client_order_id,
        ):
            self.calls.append(
                (
                    "submit_order",
                    client_order_id,
                )
            )

            return native

    value = connector(
        BadAckTransport()
    )

    value.connect()

    with pytest.raises(
        RuntimeError,
        match="invalid native SIM order acknowledgement",
    ):
        value.submit_order(
            prepared_order=prepared(),
            client_order_id="durable-op-1",
        )


def test_native_rejection_is_returned_but_never_converted_to_fill():
    class RejectTransport(
        FakeAckTransport
    ):
        def submit_order(
            self,
            *,
            prepared_order,
            client_order_id,
        ):
            self.calls.append(
                (
                    "submit_order",
                    client_order_id,
                )
            )

            return {
                "accepted": False,
                "status": "REJECTED",
                "order_id": "native-rejected-1",
                "client_order_id": client_order_id,
                "reason": "native_rejection",
            }

    value = connector(
        RejectTransport()
    )

    value.connect()

    result = value.submit_order(
        prepared_order=prepared(),
        client_order_id="durable-op-1",
    )

    assert result["accepted"] is False
    assert result["status"] == "REJECTED"
    assert result["order_id"] == "native-rejected-1"

    assert "fill_id" not in result
    assert "filled_price" not in result
    assert "position_id" not in result


def test_binding_without_explicit_ack_authority_never_submits():
    transport = FakeAckTransport()

    value = NinjaTraderSimBrokerConnectorV2(
        transport=transport,
        binding_probe=lambda: {
            "future_sim_eligible": True,
            "sim_runtime_revalidation": "PASS",
            "sim_execution_authority": "DISABLED",
            "external_order_authority": False,
        },
    )

    value.connect()

    before = list(
        transport.calls
    )

    with pytest.raises(
        RuntimeError,
        match="SIM execution authority is disabled",
    ):
        value.submit_order(
            prepared_order=prepared(),
            client_order_id="durable-op-1",
        )

    assert transport.calls == before
