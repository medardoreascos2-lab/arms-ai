import pytest

from backend.connectors.broker_connector_v2 import BrokerConnectorV2
from backend.connectors.ninjatrader_sim_broker_connector_v2 import (
    NinjaTraderSimBrokerConnectorV2,
)


class FakeReadOnlyNativeSimTransport:
    def __init__(self):
        self.calls = []
        self.connected = False

        self.account = {
            "account_ref": "a" * 64,
            "provider": "Simulator",
            "connection_mode": "Live",
        }

        self.positions = [
            {
                "position_id": "native-position-1",
                "symbol": "NQ",
                "quantity": 1,
                "side": "BUY",
            }
        ]

        self.orders = [
            {
                "order_id": "native-order-1",
                "client_order_id": "durable-operation-1",
                "status": "WORKING",
            }
        ]

        self.fills = [
            {
                "fill_id": "native-fill-1",
                "order_id": "native-order-0",
            }
        ]

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
        return dict(self.account)

    def get_positions(self):
        self.calls.append(("get_positions",))
        return [dict(row) for row in self.positions]

    def get_orders(self):
        self.calls.append(("get_orders",))
        return [dict(row) for row in self.orders]

    def get_fills(self):
        self.calls.append(("get_fills",))
        return [dict(row) for row in self.fills]

    # Mutation methods deliberately exist only so tests can prove
    # the connector never reaches them while authority is disabled.
    def submit_order(self, **kwargs):
        self.calls.append(("submit_order", kwargs))
        raise AssertionError("native submit must not be called")

    def modify_order(self, **kwargs):
        self.calls.append(("modify_order", kwargs))
        raise AssertionError("native modify must not be called")

    def cancel_order(self, **kwargs):
        self.calls.append(("cancel_order", kwargs))
        raise AssertionError("native cancel must not be called")

    def close_partial(self, **kwargs):
        self.calls.append(("close_partial", kwargs))
        raise AssertionError("native partial close must not be called")

    def close_position(self, **kwargs):
        self.calls.append(("close_position", kwargs))
        raise AssertionError("native close must not be called")


def binding_probe():
    return {
        "future_sim_eligible": True,
        "sim_runtime_revalidation": "PASS",
        "sim_execution_authority": "DISABLED",
        "external_order_authority": False,
    }


def connector():
    return NinjaTraderSimBrokerConnectorV2(
        transport=FakeReadOnlyNativeSimTransport(),
        binding_probe=binding_probe,
    )


def test_connector_implements_broker_contract_and_reports_sim_mode():
    value = connector()

    assert isinstance(value, BrokerConnectorV2)
    assert value.broker_name == "NINJATRADER_SIM"
    assert value.execution_mode == "SIM"
    assert value.is_connected is False


def test_connect_requires_current_valid_native_sim_binding():
    value = connector()

    result = value.connect()

    assert result["connected"] is True
    assert result["execution_mode"] == "SIM"
    assert result["sim_execution_authority"] == "DISABLED"
    assert result["external_order_authority"] is False
    assert value.is_connected is True


def test_invalid_binding_fails_before_transport_connect():
    transport = FakeReadOnlyNativeSimTransport()

    value = NinjaTraderSimBrokerConnectorV2(
        transport=transport,
        binding_probe=lambda: {
            "future_sim_eligible": False,
            "sim_runtime_revalidation": "REVOKED",
            "sim_execution_authority": "DISABLED",
            "external_order_authority": False,
        },
    )

    with pytest.raises(
        RuntimeError,
        match="SIM binding is not eligible",
    ):
        value.connect()

    assert transport.calls == []


def test_read_queries_are_external_transport_evidence_not_local_invented_state():
    value = connector()
    value.connect()

    assert value.get_account()["provider"] == "Simulator"
    assert value.get_positions()[0]["position_id"] == "native-position-1"
    assert value.get_orders()[0]["order_id"] == "native-order-1"
    assert value.get_fills()[0]["fill_id"] == "native-fill-1"

    assert [call[0] for call in value.transport.calls] == [
        "connect",
        "get_account",
        "get_positions",
        "get_orders",
        "get_fills",
    ]


@pytest.mark.parametrize(
    ("method", "kwargs"),
    [
        (
            "submit_order",
            {
                "prepared_order": {
                    "symbol": "NQ",
                    "side": "BUY",
                    "quantity": 1,
                },
                "client_order_id": "durable-operation-1",
            },
        ),
        (
            "modify_order",
            {
                "order_id": "native-order-1",
                "stop_loss": 20000.0,
            },
        ),
        (
            "cancel_order",
            {
                "order_id": "native-order-1",
            },
        ),
        (
            "close_partial",
            {
                "position_id": "native-position-1",
                "quantity": 1,
                "current_price": 20000.0,
                "reason": "test",
            },
        ),
        (
            "close_position",
            {
                "position_id": "native-position-1",
                "current_price": 20000.0,
                "reason": "test",
            },
        ),
    ],
)
def test_all_native_mutations_fail_closed_before_transport(method, kwargs):
    value = connector()
    value.connect()

    before = list(value.transport.calls)

    with pytest.raises(
        RuntimeError,
        match="SIM execution authority is disabled",
    ):
        getattr(value, method)(**kwargs)

    assert value.transport.calls == before


def test_health_never_claims_execution_authority():
    value = connector()
    value.connect()

    health = value.health_check()

    assert health["healthy"] is True
    assert health["execution_mode"] == "SIM"
    assert health["sim_execution_authority"] == "DISABLED"
    assert health["external_order_authority"] is False


def test_disconnect_removes_read_only_connection_state():
    value = connector()
    value.connect()

    result = value.disconnect()

    assert result["connected"] is False
    assert value.is_connected is False


def test_binding_revoked_after_connect_blocks_all_reads_before_transport():
    transport = FakeReadOnlyNativeSimTransport()

    state = {
        "future_sim_eligible": True,
        "sim_runtime_revalidation": "PASS",
        "sim_execution_authority": "DISABLED",
        "external_order_authority": False,
    }

    value = NinjaTraderSimBrokerConnectorV2(
        transport=transport,
        binding_probe=lambda: dict(state),
    )

    value.connect()

    state["future_sim_eligible"] = False
    state["sim_runtime_revalidation"] = "REVOKED"

    before = list(transport.calls)

    for method in (
        value.get_account,
        value.get_positions,
        value.get_orders,
        value.get_fills,
    ):
        with pytest.raises(
            RuntimeError,
            match="SIM binding is not eligible",
        ):
            method()

    assert transport.calls == before


def test_native_health_loss_is_never_reported_healthy():
    transport = FakeReadOnlyNativeSimTransport()
    value = NinjaTraderSimBrokerConnectorV2(
        transport=transport,
        binding_probe=binding_probe,
    )

    value.connect()

    def unhealthy():
        transport.calls.append(("health_check",))
        return {
            "healthy": False,
            "connected": False,
        }

    transport.health_check = unhealthy

    result = value.health_check()

    assert result["healthy"] is False
    assert result["connected"] is True
    assert result["sim_execution_authority"] == "DISABLED"
    assert result["external_order_authority"] is False


@pytest.mark.parametrize(
    ("method", "bad"),
    [
        ("get_account", []),
        ("get_positions", {}),
        ("get_positions", [object()]),
        ("get_orders", {}),
        ("get_orders", [object()]),
        ("get_fills", {}),
        ("get_fills", [object()]),
    ],
)
def test_invalid_native_read_evidence_fails_closed(method, bad):
    transport = FakeReadOnlyNativeSimTransport()

    setattr(
        transport,
        method,
        lambda: bad,
    )

    value = NinjaTraderSimBrokerConnectorV2(
        transport=transport,
        binding_probe=binding_probe,
    )

    value.connect()

    with pytest.raises(
        RuntimeError,
        match="Native SIM .* evidence invalid",
    ):
        getattr(value, method)()


def test_invalid_native_health_shape_fails_closed():
    transport = FakeReadOnlyNativeSimTransport()
    value = NinjaTraderSimBrokerConnectorV2(
        transport=transport,
        binding_probe=binding_probe,
    )

    value.connect()

    transport.health_check = lambda: []

    with pytest.raises(
        RuntimeError,
        match="Native SIM health evidence invalid",
    ):
        value.health_check()


def test_mutation_methods_never_call_native_transport_even_after_repeated_attempts():
    value = connector()
    value.connect()

    attempts = (
        (
            "submit_order",
            {
                "prepared_order": {
                    "symbol": "NQ",
                    "side": "BUY",
                    "quantity": 1,
                },
                "client_order_id": "durable-op",
            },
        ),
        (
            "cancel_order",
            {
                "order_id": "native-order-1",
            },
        ),
        (
            "close_position",
            {
                "position_id": "native-position-1",
                "current_price": 20000.0,
                "reason": "test",
            },
        ),
    )

    before = list(value.transport.calls)

    for _ in range(3):
        for method, kwargs in attempts:
            with pytest.raises(
                RuntimeError,
                match="SIM execution authority is disabled",
            ):
                getattr(value, method)(**kwargs)

    assert value.transport.calls == before
