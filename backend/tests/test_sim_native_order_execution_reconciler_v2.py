import pytest


MODULE = (
    "backend.services."
    "sim_native_order_execution_reconciler_v2"
)


def load_reconciler():
    module = __import__(
        MODULE,
        fromlist=[
            "SimNativeOrderExecutionReconcilerV2"
        ],
    )

    return (
        module
        .SimNativeOrderExecutionReconcilerV2
    )


class FakeReader:
    def __init__(self, events):
        self.events = list(events)
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


def order_event(
    state,
    *,
    order_id="native-1",
    quantity=1,
    filled=0,
    average_fill_price=0.0,
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
        "average_fill_price": average_fill_price,
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


def reconcile(events):
    Reconciler = load_reconciler()

    reader = FakeReader(events)

    reconciler = Reconciler(
        evidence_reader=reader,
    )

    result = reconciler.reconcile(
        command_id="cmd-1",
        operation_id="op-1",
        client_order_id="op-1",
    )

    return result, reader


def test_no_evidence_requires_recovery():
    result, reader = reconcile([])

    assert result["status"] == "RECOVERY_REQUIRED"
    assert result["resolved"] is False
    assert result["automatic_retry_allowed"] is False
    assert result["native_order_id"] is None

    assert len(reader.calls) == 1


def test_initialized_is_pending():
    result, _ = reconcile(
        [order_event("Initialized")]
    )

    assert result["status"] == "PENDING_NATIVE"
    assert result["resolved"] is False
    assert result["native_order_id"] == "native-1"


def test_submitted_is_pending():
    result, _ = reconcile(
        [order_event("Submitted")]
    )

    assert result["status"] == "PENDING_NATIVE"
    assert result["resolved"] is False


def test_accepted_is_pending():
    result, _ = reconcile(
        [order_event("Accepted")]
    )

    assert result["status"] == "PENDING_NATIVE"
    assert result["resolved"] is False


def test_working_is_pending():
    result, _ = reconcile(
        [order_event("Working")]
    )

    assert result["status"] == "PENDING_NATIVE"
    assert result["resolved"] is False


def test_part_filled_requires_execution():
    with pytest.raises(RuntimeError):
        reconcile(
            [
                order_event(
                    "PartFilled",
                    quantity=2,
                    filled=1,
                    average_fill_price=25000.25,
                )
            ]
        )


def test_part_filled_with_execution_is_pending():
    result, _ = reconcile(
        [
            order_event(
                "PartFilled",
                quantity=2,
                filled=1,
                average_fill_price=25000.25,
            ),
            execution_event(
                quantity=1,
            ),
        ]
    )

    assert result["status"] == "PENDING_NATIVE"
    assert result["resolved"] is False
    assert result["filled_quantity"] == 1


def test_filled_with_matching_execution_is_confirmed():
    result, _ = reconcile(
        [
            order_event(
                "Filled",
                quantity=1,
                filled=1,
                average_fill_price=25000.25,
            ),
            execution_event(
                quantity=1,
                price=25000.25,
            ),
        ]
    )

    assert result["status"] == "CONFIRMED_EXECUTED"
    assert result["resolved"] is True
    assert result["native_order_id"] == "native-1"
    assert result["filled_quantity"] == 1
    assert result["execution_count"] == 1


def test_filled_without_execution_fails_closed():
    with pytest.raises(RuntimeError):
        reconcile(
            [
                order_event(
                    "Filled",
                    quantity=1,
                    filled=1,
                    average_fill_price=25000.25,
                )
            ]
        )


def test_rejected_is_confirmed_not_executed():
    result, _ = reconcile(
        [order_event("Rejected")]
    )

    assert (
        result["status"]
        == "CONFIRMED_NOT_EXECUTED"
    )
    assert result["resolved"] is True
    assert result["filled_quantity"] == 0


def test_cancelled_without_execution_is_confirmed_not_executed():
    result, _ = reconcile(
        [order_event("Cancelled")]
    )

    assert (
        result["status"]
        == "CONFIRMED_NOT_EXECUTED"
    )
    assert result["resolved"] is True


def test_rejected_with_execution_fails_closed():
    with pytest.raises(RuntimeError):
        reconcile(
            [
                order_event("Rejected"),
                execution_event(),
            ]
        )


def test_multiple_native_order_ids_fail_closed():
    with pytest.raises(RuntimeError):
        reconcile(
            [
                order_event(
                    "Submitted",
                    order_id="native-1",
                ),
                order_event(
                    "Working",
                    order_id="native-2",
                ),
            ]
        )


def test_execution_order_id_must_match_native_order():
    with pytest.raises(RuntimeError):
        reconcile(
            [
                order_event(
                    "Filled",
                    quantity=1,
                    filled=1,
                    average_fill_price=25000.25,
                ),
                execution_event(
                    order_id="native-other",
                ),
            ]
        )


def test_duplicate_execution_id_fails_closed():
    with pytest.raises(RuntimeError):
        reconcile(
            [
                order_event(
                    "Filled",
                    quantity=2,
                    filled=2,
                    average_fill_price=25000.25,
                ),
                execution_event(
                    execution_id="exec-1",
                    quantity=1,
                ),
                execution_event(
                    execution_id="exec-1",
                    quantity=1,
                ),
            ]
        )


def test_execution_quantity_must_match_filled_quantity():
    with pytest.raises(RuntimeError):
        reconcile(
            [
                order_event(
                    "Filled",
                    quantity=2,
                    filled=2,
                    average_fill_price=25000.25,
                ),
                execution_event(
                    execution_id="exec-1",
                    quantity=1,
                ),
            ]
        )


def test_order_quantities_must_be_consistent():
    with pytest.raises(RuntimeError):
        reconcile(
            [
                order_event(
                    "Submitted",
                    quantity=1,
                ),
                order_event(
                    "Working",
                    quantity=2,
                ),
            ]
        )


def test_automatic_retry_is_never_allowed():
    result, _ = reconcile(
        [order_event("Working")]
    )

    assert result["automatic_retry_allowed"] is False
