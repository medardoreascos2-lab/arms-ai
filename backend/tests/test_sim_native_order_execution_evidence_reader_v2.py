import json
from pathlib import Path

import pytest


MODULE = (
    "backend.services."
    "sim_native_order_execution_evidence_reader_v2"
)


def load_reader():
    module = __import__(
        MODULE,
        fromlist=["SimNativeOrderExecutionEvidenceReaderV2"],
    )

    return module.SimNativeOrderExecutionEvidenceReaderV2


def write_json(path: Path, payload: dict):
    path.write_text(
        json.dumps(
            payload,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )


def test_reads_valid_order_update(tmp_path):
    Reader = load_reader()

    write_json(
        tmp_path / "cmd-1.order.native-1.Working.0.json",
        {
            "event_type": "ORDER_UPDATE",
            "command_id": "cmd-1",
            "operation_id": "op-1",
            "client_order_id": "op-1",
            "order_id": "native-1",
            "order_state": "Working",
            "quantity": 1,
            "filled": 0,
            "average_fill_price": 0.0,
        },
    )

    reader = Reader(
        evidence_directory=tmp_path,
    )

    events = reader.read_for_command(
        command_id="cmd-1",
        operation_id="op-1",
        client_order_id="op-1",
    )

    assert len(events) == 1

    event = events[0]

    assert event["event_type"] == "ORDER_UPDATE"
    assert event["order_id"] == "native-1"
    assert event["order_state"] == "Working"
    assert event["quantity"] == 1
    assert event["filled"] == 0


def test_reads_valid_execution_update(tmp_path):
    Reader = load_reader()

    write_json(
        tmp_path / "cmd-1.execution.exec-1.json",
        {
            "event_type": "EXECUTION_UPDATE",
            "command_id": "cmd-1",
            "operation_id": "op-1",
            "client_order_id": "op-1",
            "execution_id": "exec-1",
            "order_id": "native-1",
            "quantity": 1,
            "price": 25000.25,
        },
    )

    reader = Reader(
        evidence_directory=tmp_path,
    )

    events = reader.read_for_command(
        command_id="cmd-1",
        operation_id="op-1",
        client_order_id="op-1",
    )

    assert len(events) == 1
    assert events[0]["event_type"] == "EXECUTION_UPDATE"
    assert events[0]["execution_id"] == "exec-1"


def test_rejects_wrong_command_identity(tmp_path):
    Reader = load_reader()

    write_json(
        tmp_path / "cmd-1.order.native-1.Working.0.json",
        {
            "event_type": "ORDER_UPDATE",
            "command_id": "cmd-other",
            "operation_id": "op-1",
            "client_order_id": "op-1",
            "order_id": "native-1",
            "order_state": "Working",
            "quantity": 1,
            "filled": 0,
            "average_fill_price": 0.0,
        },
    )

    reader = Reader(
        evidence_directory=tmp_path,
    )

    with pytest.raises(RuntimeError):
        reader.read_for_command(
            command_id="cmd-1",
            operation_id="op-1",
            client_order_id="op-1",
        )


def test_rejects_operation_client_mismatch(tmp_path):
    Reader = load_reader()

    write_json(
        tmp_path / "cmd-1.execution.exec-1.json",
        {
            "event_type": "EXECUTION_UPDATE",
            "command_id": "cmd-1",
            "operation_id": "op-1",
            "client_order_id": "other-op",
            "execution_id": "exec-1",
            "order_id": "native-1",
            "quantity": 1,
            "price": 25000.25,
        },
    )

    reader = Reader(
        evidence_directory=tmp_path,
    )

    with pytest.raises(RuntimeError):
        reader.read_for_command(
            command_id="cmd-1",
            operation_id="op-1",
            client_order_id="op-1",
        )


def test_rejects_unknown_event_type(tmp_path):
    Reader = load_reader()

    write_json(
        tmp_path / "cmd-1.bad.json",
        {
            "event_type": "UNKNOWN_EVENT",
            "command_id": "cmd-1",
            "operation_id": "op-1",
            "client_order_id": "op-1",
        },
    )

    reader = Reader(
        evidence_directory=tmp_path,
    )

    with pytest.raises(RuntimeError):
        reader.read_for_command(
            command_id="cmd-1",
            operation_id="op-1",
            client_order_id="op-1",
        )


def test_rejects_non_object_json(tmp_path):
    Reader = load_reader()

    (
        tmp_path / "cmd-1.bad.json"
    ).write_text(
        "[]",
        encoding="utf-8",
    )

    reader = Reader(
        evidence_directory=tmp_path,
    )

    with pytest.raises(RuntimeError):
        reader.read_for_command(
            command_id="cmd-1",
            operation_id="op-1",
            client_order_id="op-1",
        )


def test_rejects_oversized_file(tmp_path):
    Reader = load_reader(
    )

    path = tmp_path / "cmd-1.bad.json"

    path.write_bytes(
        b"x" * ((1024 * 1024) + 1)
    )

    reader = Reader(
        evidence_directory=tmp_path,
    )

    with pytest.raises(RuntimeError):
        reader.read_for_command(
            command_id="cmd-1",
            operation_id="op-1",
            client_order_id="op-1",
        )


def test_rejects_invalid_order_numbers(tmp_path):
    Reader = load_reader()

    write_json(
        tmp_path / "cmd-1.order.native-1.Filled.2.json",
        {
            "event_type": "ORDER_UPDATE",
            "command_id": "cmd-1",
            "operation_id": "op-1",
            "client_order_id": "op-1",
            "order_id": "native-1",
            "order_state": "Filled",
            "quantity": 1,
            "filled": 2,
            "average_fill_price": 25000.25,
        },
    )

    reader = Reader(
        evidence_directory=tmp_path,
    )

    with pytest.raises(RuntimeError):
        reader.read_for_command(
            command_id="cmd-1",
            operation_id="op-1",
            client_order_id="op-1",
        )


def test_rejects_nonfinite_prices(tmp_path):
    Reader = load_reader()

    (
        tmp_path / "cmd-1.execution.exec-1.json"
    ).write_text(
        (
            '{"event_type":"EXECUTION_UPDATE",'
            '"command_id":"cmd-1",'
            '"operation_id":"op-1",'
            '"client_order_id":"op-1",'
            '"execution_id":"exec-1",'
            '"order_id":"native-1",'
            '"quantity":1,'
            '"price":NaN}'
        ),
        encoding="utf-8",
    )

    reader = Reader(
        evidence_directory=tmp_path,
    )

    with pytest.raises(RuntimeError):
        reader.read_for_command(
            command_id="cmd-1",
            operation_id="op-1",
            client_order_id="op-1",
        )


def test_empty_directory_returns_no_events(tmp_path):
    Reader = load_reader()

    reader = Reader(
        evidence_directory=tmp_path,
    )

    events = reader.read_for_command(
        command_id="cmd-1",
        operation_id="op-1",
        client_order_id="op-1",
    )

    assert events == []


def test_does_not_read_other_command_files(tmp_path):
    Reader = load_reader()

    write_json(
        tmp_path / "cmd-other.order.native-9.Working.0.json",
        {
            "event_type": "ORDER_UPDATE",
            "command_id": "cmd-other",
            "operation_id": "op-other",
            "client_order_id": "op-other",
            "order_id": "native-9",
            "order_state": "Working",
            "quantity": 1,
            "filled": 0,
            "average_fill_price": 0.0,
        },
    )

    reader = Reader(
        evidence_directory=tmp_path,
    )

    events = reader.read_for_command(
        command_id="cmd-1",
        operation_id="op-1",
        client_order_id="op-1",
    )

    assert events == []
