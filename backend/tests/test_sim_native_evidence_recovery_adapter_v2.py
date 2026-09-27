import pytest

from backend.services.sim_pending_operation_recovery_v2 import (
    SimPendingOperationRecoveryV2,
)


MODULE = (
    "backend.services."
    "sim_native_evidence_recovery_adapter_v2"
)


def load_adapter():
    module = __import__(
        MODULE,
        fromlist=[
            "SimNativeEvidenceRecoveryAdapterV2"
        ],
    )

    return (
        module
        .SimNativeEvidenceRecoveryAdapterV2
    )


class FakeReconciler:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def reconcile(
        self,
        *,
        command_id,
        operation_id,
        client_order_id,
    ):
        self.calls.append(
            {
                "command_id": command_id,
                "operation_id": operation_id,
                "client_order_id": client_order_id,
            }
        )

        if self.error is not None:
            raise self.error

        return dict(self.result)


class FakeReader:
    def __init__(self, events=None):
        self.events = list(events or [])
        self.calls = []

    def read_for_command(
        self,
        *,
        command_id,
        operation_id,
        client_order_id,
    ):
        self.calls.append(
            {
                "command_id": command_id,
                "operation_id": operation_id,
                "client_order_id": client_order_id,
            }
        )

        return list(self.events)


def make_adapter(
    result,
    *,
    events=None,
    error=None,
):
    Adapter = load_adapter()

    return Adapter(
        command_id="cmd-1",
        evidence_reconciler=FakeReconciler(
            result=result,
            error=error,
        ),
        evidence_reader=FakeReader(
            events=events,
        ),
    )


def order_event(
    state,
    *,
    order_id="native-1",
    quantity=1,
    filled=0,
):
    return {
        "event_type": "ORDER_UPDATE",
        "command_id": "cmd-1",
        "operation_id": "op-1",
        "client_order_id": "op-1",
        "order_id": order_id,
        "order_state": state,
        "quantity": quantity,
        "filled": filled,
        "average_fill_price": 0.0,
    }


def execution_event(
    *,
    execution_id="exec-1",
    order_id="native-1",
    quantity=1,
    price=25000.25,
):
    return {
        "event_type": "EXECUTION_UPDATE",
        "command_id": "cmd-1",
        "operation_id": "op-1",
        "client_order_id": "op-1",
        "execution_id": execution_id,
        "order_id": order_id,
        "quantity": quantity,
        "price": price,
    }


def test_adapter_exposes_sim_execution_mode():
    adapter = make_adapter(
        {
            "status": "RECOVERY_REQUIRED",
            "resolved": False,
            "automatic_retry_allowed": False,
            "native_order_id": None,
            "filled_quantity": 0,
            "execution_count": 0,
        }
    )

    assert adapter.execution_mode == "SIM"


def test_recovery_required_maps_to_not_found():
    adapter = make_adapter(
        {
            "status": "RECOVERY_REQUIRED",
            "resolved": False,
            "automatic_retry_allowed": False,
            "native_order_id": None,
            "filled_quantity": 0,
            "execution_count": 0,
        }
    )

    native = adapter.reconcile_order(
        client_order_id="op-1"
    )

    assert native["client_order_id"] == "op-1"
    assert native["status"] == "NOT_FOUND"
    assert native["fill_confirmed"] is False
    assert native["fills"] == []


def test_pending_unfilled_maps_to_working():
    adapter = make_adapter(
        {
            "status": "PENDING_NATIVE",
            "resolved": False,
            "automatic_retry_allowed": False,
            "native_order_id": "native-1",
            "filled_quantity": 0,
            "execution_count": 0,
        },
        events=[
            order_event("Working"),
        ],
    )

    native = adapter.reconcile_order(
        client_order_id="op-1"
    )

    assert native["status"] == "WORKING"
    assert native["order"]["order_id"] == "native-1"


def test_partial_fill_maps_to_partially_filled():
    adapter = make_adapter(
        {
            "status": "PENDING_NATIVE",
            "resolved": False,
            "automatic_retry_allowed": False,
            "native_order_id": "native-1",
            "filled_quantity": 1,
            "execution_count": 1,
        },
        events=[
            order_event(
                "PartFilled",
                quantity=2,
                filled=1,
            ),
            execution_event(
                quantity=1,
            ),
        ],
    )

    native = adapter.reconcile_order(
        client_order_id="op-1"
    )

    assert native["status"] == "PARTIALLY_FILLED"
    assert native["fill_confirmed"] is True
    assert len(native["fills"]) == 1


def test_confirmed_execution_maps_real_execution_evidence_to_fills():
    adapter = make_adapter(
        {
            "status": "CONFIRMED_EXECUTED",
            "resolved": True,
            "automatic_retry_allowed": False,
            "native_order_id": "native-1",
            "filled_quantity": 1,
            "execution_count": 1,
        },
        events=[
            order_event(
                "Filled",
                filled=1,
            ),
            execution_event(
                execution_id="exec-1",
                price=25000.25,
            ),
        ],
    )

    native = adapter.reconcile_order(
        client_order_id="op-1"
    )

    assert native["status"] == "FILLED"
    assert native["fill_confirmed"] is True

    assert native["fills"] == [
        {
            "fill_id": "exec-1",
            "order_id": "native-1",
            "quantity": 1,
            "filled_price": 25000.25,
        }
    ]


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ("Rejected", "REJECTED"),
        ("Cancelled", "CANCELLED"),
    ],
)
def test_confirmed_not_executed_preserves_terminal_native_state(
    state,
    expected,
):
    adapter = make_adapter(
        {
            "status": "CONFIRMED_NOT_EXECUTED",
            "resolved": True,
            "automatic_retry_allowed": False,
            "native_order_id": "native-1",
            "filled_quantity": 0,
            "execution_count": 0,
        },
        events=[
            order_event(state),
        ],
    )

    native = adapter.reconcile_order(
        client_order_id="op-1"
    )

    assert native["status"] == expected
    assert native["fill_confirmed"] is False
    assert native["fills"] == []


def test_confirmed_execution_without_execution_event_fails_closed():
    adapter = make_adapter(
        {
            "status": "CONFIRMED_EXECUTED",
            "resolved": True,
            "automatic_retry_allowed": False,
            "native_order_id": "native-1",
            "filled_quantity": 1,
            "execution_count": 1,
        },
        events=[
            order_event(
                "Filled",
                filled=1,
            ),
        ],
    )

    with pytest.raises(RuntimeError):
        adapter.reconcile_order(
            client_order_id="op-1"
        )


def test_terminal_not_executed_without_terminal_order_state_fails_closed():
    adapter = make_adapter(
        {
            "status": "CONFIRMED_NOT_EXECUTED",
            "resolved": True,
            "automatic_retry_allowed": False,
            "native_order_id": "native-1",
            "filled_quantity": 0,
            "execution_count": 0,
        },
        events=[
            order_event("Working"),
        ],
    )

    with pytest.raises(RuntimeError):
        adapter.reconcile_order(
            client_order_id="op-1"
        )


def test_adapter_never_allows_automatic_retry():
    adapter = make_adapter(
        {
            "status": "PENDING_NATIVE",
            "resolved": False,
            "automatic_retry_allowed": True,
            "native_order_id": "native-1",
            "filled_quantity": 0,
            "execution_count": 0,
        },
        events=[
            order_event("Working"),
        ],
    )

    with pytest.raises(RuntimeError):
        adapter.reconcile_order(
            client_order_id="op-1"
        )


def test_existing_recovery_service_accepts_adapter():
    adapter = make_adapter(
        {
            "status": "CONFIRMED_EXECUTED",
            "resolved": True,
            "automatic_retry_allowed": False,
            "native_order_id": "native-1",
            "filled_quantity": 1,
            "execution_count": 1,
        },
        events=[
            order_event(
                "Filled",
                filled=1,
            ),
            execution_event(),
        ],
    )

    recovery = SimPendingOperationRecoveryV2(
        broker_connector=adapter,
    )

    result = recovery.reconcile(
        operation_id="op-1",
    )

    assert result["status"] == "CONFIRMED_EXECUTED"
    assert result["resolved"] is True
    assert result["executed"] is True


def test_existing_recovery_service_does_not_resubmit_through_adapter():
    adapter = make_adapter(
        {
            "status": "RECOVERY_REQUIRED",
            "resolved": False,
            "automatic_retry_allowed": False,
            "native_order_id": None,
            "filled_quantity": 0,
            "execution_count": 0,
        }
    )

    recovery = SimPendingOperationRecoveryV2(
        broker_connector=adapter,
    )

    result = recovery.reconcile(
        operation_id="op-1",
    )

    assert result["status"] == "RECOVERY_REQUIRED"

    assert not hasattr(
        adapter,
        "submit_order",
    )
