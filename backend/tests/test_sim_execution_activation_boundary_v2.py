import pytest

from backend.connectors.ninjatrader_sim_broker_connector_v2 import (
    NinjaTraderSimBrokerConnectorV2,
)
from backend.services.sim_execution_activation_boundary_v2 import (
    SimExecutionActivationBoundaryV2,
)
from backend.services.sim_execution_activation_gate_v2 import (
    SimExecutionActivationGateV2,
)


def binding_probe():
    return {
        "future_sim_eligible": True,
        "sim_runtime_revalidation": "PASS",
        "sim_execution_authority": "DISABLED",
        "external_order_authority": False,
    }


class State:
    healthy = True


state = State()


def health_probe():
    return {
        "healthy": state.healthy,
        "connected": state.healthy,
        "execution_mode": "SIM",
        "sim_execution_authority": "DISABLED",
        "external_order_authority": False,
    }


def recovery_probe():
    return {
        "status": "CONFIRMED_NOT_EXECUTED",
        "resolved": True,
        "executed": False,
    }


def inventory_probe():
    return {
        "ambiguous_orders": 0,
        "ambiguous_positions": 0,
        "unresolved_orders": 0,
        "unresolved_positions": 0,
    }


def raw_ack_capability():
    return {
        "ack_submit_enabled": True,
        "scope": "SIM_ACK_TEST_ONLY",
    }


def raw_mutation_capability():
    return {
        "native_mutation_enabled": True,
        "scope": "SIM_MUTATION_TEST_ONLY",
    }


def make_gate():
    return SimExecutionActivationGateV2(
        binding_probe=binding_probe,
        health_probe=health_probe,
        recovery_probe=recovery_probe,
        native_inventory_probe=inventory_probe,
        ack_capability_probe=raw_ack_capability,
        mutation_capability_probe=raw_mutation_capability,
    )


class FakeTransport:
    def __init__(
        self,
        *,
        orders=None,
        positions=None,
    ):
        self.connected = False
        self.calls = []
        self.orders = list(
            orders or []
        )
        self.positions = list(
            positions or []
        )

    def connect(self):
        self.connected = True
        self.calls.append(("connect",))

        return {
            "connected": True,
            "status": "CONNECTED",
        }

    def disconnect(self):
        self.connected = False
        self.calls.append(("disconnect",))

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
            "accepted": True,
            "status": "ACKNOWLEDGED",
            "order_id": "native-order-1",
            "client_order_id": client_order_id,
        }

    def modify_order(self, **kwargs):
        self.calls.append(
            (
                "modify_order",
                dict(kwargs),
            )
        )

        return {
            "modified": True,
            "status": "MODIFIED",
            "order_id": kwargs["order_id"],
        }

    def cancel_order(self, **kwargs):
        self.calls.append(
            (
                "cancel_order",
                dict(kwargs),
            )
        )

        return {
            "cancelled": True,
            "status": "CANCELLED",
            "order_id": kwargs["order_id"],
        }

    def close_position(self, **kwargs):
        self.calls.append(
            (
                "close_position",
                dict(kwargs),
            )
        )

        return {
            "closed": True,
            "status": "CLOSE_ACKNOWLEDGED",
            "position_id": kwargs["position_id"],
        }

    def close_partial(self, **kwargs):
        raise AssertionError(
            "partial close remains disabled"
        )


def make_runtime(
    *,
    orders=None,
    positions=None,
):
    state.healthy = True

    gate = make_gate()

    boundary = SimExecutionActivationBoundaryV2(
        gate=gate,
        ack_capability_probe=raw_ack_capability,
        mutation_capability_probe=raw_mutation_capability,
    )

    transport = FakeTransport(
        orders=orders,
        positions=positions,
    )

    connector = NinjaTraderSimBrokerConnectorV2(
        transport=transport,
        binding_probe=binding_probe,
        ack_authority_probe=(
            boundary.ack_authority_probe
        ),
        mutation_authority_probe=(
            boundary.mutation_authority_probe
        ),
    )

    connector.connect()

    return gate, boundary, connector


def test_boundary_starts_disabled():
    gate, boundary, connector = make_runtime()

    assert gate.status()["state"] == "DISABLED"

    assert boundary.status() == {
        "state": "DISABLED",
        "armed": False,
        "external_order_authority": False,
    }


def test_submit_before_operator_arm_is_blocked_before_transport():
    gate, boundary, connector = make_runtime()

    before = list(
        connector.transport.calls
    )

    with pytest.raises(
        RuntimeError,
        match="SIM execution authority is disabled",
    ):
        connector.submit_order(
            prepared_order={
                "symbol": "NQ",
                "side": "BUY",
                "quantity": 1,
            },
            client_order_id="op-1",
        )

    assert connector.transport.calls == before


def test_operator_arm_allows_ack_capability():
    gate, boundary, connector = make_runtime()

    gate.arm(
        operator_token="ARM_SIM_EXECUTION_V2",
    )

    result = connector.submit_order(
        prepared_order={
            "symbol": "NQ",
            "side": "BUY",
            "quantity": 1,
        },
        client_order_id="op-1",
    )

    assert result["accepted"] is True
    assert result["status"] == "ACKNOWLEDGED"

    assert [
        call[0]
        for call in connector.transport.calls
    ] == [
        "connect",
        "get_orders",
        "submit_order",
    ]


def test_health_loss_revokes_gate_and_blocks_new_submit():
    gate, boundary, connector = make_runtime()

    assert gate.arm(
        operator_token="ARM_SIM_EXECUTION_V2",
    )["armed"] is True

    state.healthy = False

    before = list(
        connector.transport.calls
    )

    with pytest.raises(
        RuntimeError,
        match="SIM execution authority is disabled",
    ):
        connector.submit_order(
            prepared_order={
                "symbol": "NQ",
                "side": "BUY",
                "quantity": 1,
            },
            client_order_id="op-2",
        )

    assert gate.status()["state"] == "REVOKED"
    assert gate.status()["armed"] is False
    assert connector.transport.calls == before


def test_revoked_gate_cannot_be_rearmed_through_boundary():
    gate, boundary, connector = make_runtime()

    gate.arm(
        operator_token="ARM_SIM_EXECUTION_V2",
    )

    gate.revoke(
        reason="operator_revoke",
    )

    assert boundary.status()["state"] == "REVOKED"

    with pytest.raises(
        RuntimeError,
        match="SIM execution authority is disabled",
    ):
        connector.submit_order(
            prepared_order={
                "symbol": "NQ",
                "side": "BUY",
                "quantity": 1,
            },
            client_order_id="op-3",
        )


def test_mutation_before_arm_is_blocked():
    gate, boundary, connector = make_runtime(
        orders=[
            {
                "order_id": "native-order-1",
                "status": "WORKING",
            }
        ]
    )

    before = list(
        connector.transport.calls
    )

    with pytest.raises(
        RuntimeError,
        match="SIM execution authority is disabled",
    ):
        connector.cancel_order(
            order_id="native-order-1",
        )

    assert connector.transport.calls == before


def test_armed_gate_allows_mutation_capability():
    gate, boundary, connector = make_runtime(
        orders=[
            {
                "order_id": "native-order-1",
                "status": "WORKING",
            }
        ]
    )

    gate.arm(
        operator_token="ARM_SIM_EXECUTION_V2",
    )

    result = connector.cancel_order(
        order_id="native-order-1",
    )

    assert result["cancelled"] is True
    assert result["status"] == "CANCELLED"

    assert [
        call[0]
        for call in connector.transport.calls
    ] == [
        "connect",
        "get_orders",
        "cancel_order",
    ]


def test_health_loss_revokes_mutation_capability_before_transport():
    gate, boundary, connector = make_runtime(
        orders=[
            {
                "order_id": "native-order-1",
                "status": "WORKING",
            }
        ]
    )

    gate.arm(
        operator_token="ARM_SIM_EXECUTION_V2",
    )

    state.healthy = False

    before = list(
        connector.transport.calls
    )

    with pytest.raises(
        RuntimeError,
        match="SIM execution authority is disabled",
    ):
        connector.cancel_order(
            order_id="native-order-1",
        )

    assert gate.status()["state"] == "REVOKED"
    assert connector.transport.calls == before


def test_boundary_has_no_order_transport_methods():
    gate, boundary, connector = make_runtime()

    for name in (
        "submit_order",
        "modify_order",
        "cancel_order",
        "close_position",
        "close_partial",
    ):
        assert not hasattr(
            boundary,
            name,
        )
