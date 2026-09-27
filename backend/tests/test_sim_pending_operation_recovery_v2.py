import pytest

from backend.services.sim_pending_operation_recovery_v2 import (
    SimPendingOperationRecoveryV2,
)


class FakeSimReconciler:
    execution_mode = "SIM"

    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def reconcile_order(
        self,
        *,
        client_order_id,
    ):
        self.calls.append(
            (
                "reconcile_order",
                client_order_id,
            )
        )

        if self.error is not None:
            raise self.error

        return self.result

    def submit_order(self, **kwargs):
        self.calls.append(
            (
                "submit_order",
                kwargs,
            )
        )

        raise AssertionError(
            "SIM recovery must never resubmit"
        )


def recovery(result=None, error=None):
    return SimPendingOperationRecoveryV2(
        broker_connector=FakeSimReconciler(
            result=result,
            error=error,
        )
    )


def test_operation_id_is_required():
    value = recovery(
        result={}
    )

    for bad in (
        None,
        "",
        "   ",
    ):
        with pytest.raises(
            ValueError,
            match="operation_id is required",
        ):
            value.reconcile(
                operation_id=bad,
            )


def test_not_found_is_unresolved_and_never_resubmitted():
    value = recovery(
        result={
            "resolved": False,
            "client_order_id": "op-1",
            "status": "NOT_FOUND",
            "order": None,
            "fills": [],
            "position": None,
            "fill_confirmed": False,
            "position_confirmed": False,
        }
    )

    result = value.reconcile(
        operation_id="op-1",
    )

    assert result == {
        "status": "RECOVERY_REQUIRED",
        "resolved": False,
        "operation_id": "op-1",
        "native_status": "NOT_FOUND",
        "executed": False,
        "reason": (
            "native_order_not_found;"
            " automatic_resubmit_forbidden"
        ),
        "native": None,
    }

    assert value.broker_connector.calls == [
        (
            "reconcile_order",
            "op-1",
        )
    ]


@pytest.mark.parametrize(
    "status",
    [
        "ACKNOWLEDGED",
        "WORKING",
        "PARTIALLY_FILLED",
    ],
)
def test_non_terminal_native_order_remains_pending_without_resubmit(
    status,
):
    value = recovery(
        result={
            "resolved": True,
            "client_order_id": "op-1",
            "status": status,
            "order": {
                "order_id": "native-order-1",
                "client_order_id": "op-1",
                "accepted": True,
                "status": status,
            },
            "fills": [],
            "position": None,
            "fill_confirmed": False,
            "position_confirmed": False,
        }
    )

    result = value.reconcile(
        operation_id="op-1",
    )

    assert result["status"] == "PENDING_NATIVE"
    assert result["resolved"] is False
    assert result["executed"] is False
    assert result["native_status"] == status

    assert [
        call[0]
        for call in value.broker_connector.calls
    ] == [
        "reconcile_order",
    ]


def test_filled_with_native_fill_is_confirmed_executed():
    native = {
        "resolved": True,
        "client_order_id": "op-1",
        "status": "FILLED",
        "order": {
            "order_id": "native-order-1",
            "client_order_id": "op-1",
            "accepted": True,
            "status": "FILLED",
        },
        "fills": [
            {
                "fill_id": "native-fill-1",
                "order_id": "native-order-1",
                "quantity": 1,
                "filled_price": 20000.0,
            }
        ],
        "position": {
            "position_id": "native-position-1",
            "order_id": "native-order-1",
        },
        "fill_confirmed": True,
        "position_confirmed": True,
    }

    value = recovery(
        result=native
    )

    result = value.reconcile(
        operation_id="op-1",
    )

    assert result["status"] == "CONFIRMED_EXECUTED"
    assert result["resolved"] is True
    assert result["executed"] is True
    assert result["native_status"] == "FILLED"
    assert result["native"] == native

    assert [
        call[0]
        for call in value.broker_connector.calls
    ] == [
        "reconcile_order",
    ]


@pytest.mark.parametrize(
    "status",
    [
        "REJECTED",
        "CANCELLED",
    ],
)
def test_rejected_or_cancelled_is_confirmed_not_executed(
    status,
):
    native = {
        "resolved": True,
        "client_order_id": "op-1",
        "status": status,
        "order": {
            "order_id": "native-order-1",
            "client_order_id": "op-1",
            "accepted": False,
            "status": status,
        },
        "fills": [],
        "position": None,
        "fill_confirmed": False,
        "position_confirmed": False,
    }

    value = recovery(
        result=native
    )

    result = value.reconcile(
        operation_id="op-1",
    )

    assert result["status"] == "CONFIRMED_NOT_EXECUTED"
    assert result["resolved"] is True
    assert result["executed"] is False
    assert result["native_status"] == status


def test_filled_without_confirmed_fill_fails_closed():
    value = recovery(
        result={
            "resolved": True,
            "client_order_id": "op-1",
            "status": "FILLED",
            "order": {
                "order_id": "native-order-1",
                "client_order_id": "op-1",
                "accepted": True,
                "status": "FILLED",
            },
            "fills": [],
            "position": None,
            "fill_confirmed": False,
            "position_confirmed": False,
        }
    )

    result = value.reconcile(
        operation_id="op-1",
    )

    assert result["status"] == "AMBIGUOUS"
    assert result["resolved"] is False
    assert result["executed"] is False


def test_connector_ambiguity_becomes_fail_closed_recovery_report():
    value = recovery(
        error=RuntimeError(
            "ambiguous native client_order_id."
        )
    )

    result = value.reconcile(
        operation_id="op-1",
    )

    assert result["status"] == "AMBIGUOUS"
    assert result["resolved"] is False
    assert result["executed"] is False
    assert (
        "ambiguous native client_order_id"
        in result["reason"]
    )

    assert [
        call[0]
        for call in value.broker_connector.calls
    ] == [
        "reconcile_order",
    ]


def test_invalid_reconciliation_shape_fails_closed():
    value = recovery(
        result=[]
    )

    result = value.reconcile(
        operation_id="op-1",
    )

    assert result["status"] == "CORRUPT"
    assert result["resolved"] is False
    assert result["executed"] is False


def test_client_order_identity_must_equal_durable_operation_id():
    value = recovery(
        result={
            "resolved": True,
            "client_order_id": "different-op",
            "status": "WORKING",
            "order": {
                "order_id": "native-order-1",
                "client_order_id": "different-op",
                "accepted": True,
                "status": "WORKING",
            },
            "fills": [],
            "position": None,
            "fill_confirmed": False,
            "position_confirmed": False,
        }
    )

    result = value.reconcile(
        operation_id="op-1",
    )

    assert result["status"] == "AMBIGUOUS"
    assert result["resolved"] is False
    assert result["executed"] is False


def test_recovery_service_has_no_submit_path():
    value = recovery(
        result={
            "resolved": False,
            "client_order_id": "op-1",
            "status": "NOT_FOUND",
            "order": None,
            "fills": [],
            "position": None,
            "fill_confirmed": False,
            "position_confirmed": False,
        }
    )

    value.reconcile(
        operation_id="op-1",
    )

    assert not any(
        call[0] == "submit_order"
        for call in value.broker_connector.calls
    )
