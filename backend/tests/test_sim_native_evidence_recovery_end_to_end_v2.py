import json

import pytest

from backend.services.sim_native_evidence_recovery_adapter_v2 import (
    SimNativeEvidenceRecoveryAdapterV2,
)
from backend.services.sim_native_order_execution_evidence_reader_v2 import (
    SimNativeOrderExecutionEvidenceReaderV2,
)
from backend.services.sim_native_order_execution_reconciler_v2 import (
    SimNativeOrderExecutionReconcilerV2,
)
from backend.services.sim_pending_operation_recovery_v2 import (
    SimPendingOperationRecoveryV2,
)


COMMAND_ID = "cmd-e2e-1"
OPERATION_ID = "op-e2e-1"


def write_json(path, payload):
    path.write_text(
        json.dumps(
            payload,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )


def build_recovery(directory):
    reader = (
        SimNativeOrderExecutionEvidenceReaderV2(
            evidence_directory=directory,
        )
    )

    reconciler = (
        SimNativeOrderExecutionReconcilerV2(
            evidence_reader=reader,
        )
    )

    adapter = SimNativeEvidenceRecoveryAdapterV2(
        command_id=COMMAND_ID,
        evidence_reconciler=reconciler,
        evidence_reader=reader,
    )

    return SimPendingOperationRecoveryV2(
        broker_connector=adapter,
    )


def order_payload(
    state,
    *,
    filled=0,
    quantity=1,
):
    return {
        "event_type": "ORDER_UPDATE",
        "command_id": COMMAND_ID,
        "operation_id": OPERATION_ID,
        "client_order_id": OPERATION_ID,
        "order_id": "native-order-1",
        "order_state": state,
        "quantity": quantity,
        "filled": filled,
        "average_fill_price": (
            25000.25 if filled else 0.0
        ),
    }


def execution_payload():
    return {
        "event_type": "EXECUTION_UPDATE",
        "command_id": COMMAND_ID,
        "operation_id": OPERATION_ID,
        "client_order_id": OPERATION_ID,
        "execution_id": "native-exec-1",
        "order_id": "native-order-1",
        "quantity": 1,
        "price": 25000.25,
    }


def test_empty_native_directory_requires_recovery(tmp_path):
    recovery = build_recovery(
        tmp_path
    )

    result = recovery.reconcile(
        operation_id=OPERATION_ID,
    )

    assert result["status"] == "RECOVERY_REQUIRED"
    assert result["resolved"] is False
    assert result["executed"] is False

    assert (
        "automatic_resubmit_forbidden"
        in result["reason"]
    )


def test_working_native_order_remains_pending(tmp_path):
    write_json(
        tmp_path
        / (
            COMMAND_ID
            + ".order.native-order-1.Working.0.json"
        ),
        order_payload("Working"),
    )

    recovery = build_recovery(
        tmp_path
    )

    result = recovery.reconcile(
        operation_id=OPERATION_ID,
    )

    assert result["status"] == "PENDING_NATIVE"
    assert result["resolved"] is False
    assert result["executed"] is False
    assert result["native_status"] == "WORKING"


def test_filled_plus_execution_confirms_execution(tmp_path):
    write_json(
        tmp_path
        / (
            COMMAND_ID
            + ".order.native-order-1.Filled.1.json"
        ),
        order_payload(
            "Filled",
            filled=1,
        ),
    )

    write_json(
        tmp_path
        / (
            COMMAND_ID
            + ".execution.native-exec-1.json"
        ),
        execution_payload(),
    )

    recovery = build_recovery(
        tmp_path
    )

    result = recovery.reconcile(
        operation_id=OPERATION_ID,
    )

    assert result["status"] == "CONFIRMED_EXECUTED"
    assert result["resolved"] is True
    assert result["executed"] is True
    assert result["native_status"] == "FILLED"

    fills = result["native"]["fills"]

    assert fills == [
        {
            "fill_id": "native-exec-1",
            "order_id": "native-order-1",
            "quantity": 1,
            "filled_price": 25000.25,
        }
    ]


def test_rejected_confirms_not_executed(tmp_path):
    write_json(
        tmp_path
        / (
            COMMAND_ID
            + ".order.native-order-1.Rejected.0.json"
        ),
        order_payload("Rejected"),
    )

    recovery = build_recovery(
        tmp_path
    )

    result = recovery.reconcile(
        operation_id=OPERATION_ID,
    )

    assert (
        result["status"]
        == "CONFIRMED_NOT_EXECUTED"
    )
    assert result["resolved"] is True
    assert result["executed"] is False
    assert result["native_status"] == "REJECTED"


def test_filled_without_execution_fails_closed(tmp_path):
    write_json(
        tmp_path
        / (
            COMMAND_ID
            + ".order.native-order-1.Filled.1.json"
        ),
        order_payload(
            "Filled",
            filled=1,
        ),
    )

    recovery = build_recovery(
        tmp_path
    )

    result = recovery.reconcile(
        operation_id=OPERATION_ID,
    )

    assert result["status"] == "AMBIGUOUS"
    assert result["resolved"] is False
    assert result["executed"] is False


def test_corrupt_native_json_fails_closed(tmp_path):
    path = (
        tmp_path
        / (
            COMMAND_ID
            + ".order.native-order-1.Working.0.json"
        )
    )

    path.write_text(
        '{"event_type":',
        encoding="utf-8",
    )

    recovery = build_recovery(
        tmp_path
    )

    result = recovery.reconcile(
        operation_id=OPERATION_ID,
    )

    assert result["status"] in {
        "AMBIGUOUS",
        "CORRUPT",
    }

    assert result["resolved"] is False
    assert result["executed"] is False


def test_no_submit_surface_exists_anywhere_in_recovery_chain(
    tmp_path,
):
    reader = (
        SimNativeOrderExecutionEvidenceReaderV2(
            evidence_directory=tmp_path,
        )
    )

    reconciler = (
        SimNativeOrderExecutionReconcilerV2(
            evidence_reader=reader,
        )
    )

    adapter = SimNativeEvidenceRecoveryAdapterV2(
        command_id=COMMAND_ID,
        evidence_reconciler=reconciler,
        evidence_reader=reader,
    )

    recovery = SimPendingOperationRecoveryV2(
        broker_connector=adapter,
    )

    assert not hasattr(
        adapter,
        "submit_order",
    )

    assert not hasattr(
        reconciler,
        "submit_order",
    )

    assert not hasattr(
        reader,
        "submit_order",
    )

    assert not hasattr(
        recovery,
        "submit_order",
    )
