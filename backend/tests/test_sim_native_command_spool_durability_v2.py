import os
from pathlib import Path

import pytest

import backend.services.sim_native_command_spool_v2 as spool_module
from backend.services.sim_native_command_spool_v2 import (
    SimNativeCommandSpoolV2,
)


def command():
    return {
        "command_id": "cmd-durable-001",
        "operation_id": "op-durable-001",
        "command": "SUBMIT_ORDER",
        "client_order_id": "op-durable-001",
        "payload": {
            "symbol": "NQ",
            "side": "BUY",
            "quantity": 1,
        },
    }


def ack():
    return {
        "command_id": "cmd-durable-001",
        "operation_id": "op-durable-001",
        "client_order_id": "op-durable-001",
        "status": "ACKNOWLEDGED",
        "accepted": True,
        "order_id": "native-order-durable-1",
    }


def spool(tmp_path):
    return SimNativeCommandSpoolV2(
        root=tmp_path,
    )


def test_command_write_fsyncs_before_reporting_success(
    tmp_path,
    monkeypatch,
):
    value = spool(tmp_path)

    calls = []

    real_fsync = os.fsync

    def observed_fsync(fd):
        calls.append(fd)
        return real_fsync(fd)

    monkeypatch.setattr(
        spool_module.os,
        "fsync",
        observed_fsync,
    )

    result = value.write_command(
        command=command(),
    )

    assert result["created"] is True
    assert result["idempotent"] is False
    assert len(calls) == 1

    assert Path(
        result["path"]
    ).is_file()


def test_ack_write_fsyncs_before_reporting_success(
    tmp_path,
    monkeypatch,
):
    value = spool(tmp_path)

    value.write_command(
        command=command(),
    )

    calls = []

    real_fsync = os.fsync

    def observed_fsync(fd):
        calls.append(fd)
        return real_fsync(fd)

    monkeypatch.setattr(
        spool_module.os,
        "fsync",
        observed_fsync,
    )

    result = value.write_ack(
        native_ack=ack(),
    )

    assert result["created"] is True
    assert result["idempotent"] is False
    assert len(calls) == 1

    assert Path(
        result["path"]
    ).is_file()


def test_identical_existing_command_does_not_rewrite_or_resync(
    tmp_path,
    monkeypatch,
):
    value = spool(tmp_path)

    first = value.write_command(
        command=command(),
    )

    calls = []

    def forbidden_fsync(fd):
        calls.append(fd)
        raise AssertionError(
            "idempotent evidence must not be rewritten"
        )

    monkeypatch.setattr(
        spool_module.os,
        "fsync",
        forbidden_fsync,
    )

    second = value.write_command(
        command=command(),
    )

    assert second["created"] is False
    assert second["idempotent"] is True
    assert second["path"] == first["path"]
    assert calls == []


def test_identical_existing_ack_does_not_rewrite_or_resync(
    tmp_path,
    monkeypatch,
):
    value = spool(tmp_path)

    value.write_command(
        command=command(),
    )

    first = value.write_ack(
        native_ack=ack(),
    )

    calls = []

    def forbidden_fsync(fd):
        calls.append(fd)
        raise AssertionError(
            "idempotent ACK must not be rewritten"
        )

    monkeypatch.setattr(
        spool_module.os,
        "fsync",
        forbidden_fsync,
    )

    second = value.write_ack(
        native_ack=ack(),
    )

    assert second["created"] is False
    assert second["idempotent"] is True
    assert second["path"] == first["path"]
    assert calls == []


def test_fsync_failure_never_reports_command_success(
    tmp_path,
    monkeypatch,
):
    value = spool(tmp_path)

    def fail_fsync(fd):
        raise OSError(
            "simulated fsync failure"
        )

    monkeypatch.setattr(
        spool_module.os,
        "fsync",
        fail_fsync,
    )

    with pytest.raises(
        RuntimeError,
        match="command durability sync failed",
    ):
        value.write_command(
            command=command(),
        )


def test_fsync_failure_never_reports_ack_success(
    tmp_path,
    monkeypatch,
):
    value = spool(tmp_path)

    value.write_command(
        command=command(),
    )

    def fail_fsync(fd):
        raise OSError(
            "simulated fsync failure"
        )

    monkeypatch.setattr(
        spool_module.os,
        "fsync",
        fail_fsync,
    )

    with pytest.raises(
        RuntimeError,
        match="ack durability sync failed",
    ):
        value.write_ack(
            native_ack=ack(),
        )


def test_existing_truncated_command_still_fails_closed(
    tmp_path,
):
    value = spool(tmp_path)

    result = value.write_command(
        command=command(),
    )

    Path(
        result["path"]
    ).write_bytes(
        b'{"command_id":'
    )

    with pytest.raises(
        RuntimeError,
        match="corrupt command evidence",
    ):
        value.read_command(
            command_id="cmd-durable-001",
        )


def test_existing_truncated_ack_still_fails_closed(
    tmp_path,
):
    value = spool(tmp_path)

    value.write_command(
        command=command(),
    )

    result = value.write_ack(
        native_ack=ack(),
    )

    Path(
        result["path"]
    ).write_bytes(
        b'{"status":'
    )

    with pytest.raises(
        RuntimeError,
        match="corrupt ack evidence",
    ):
        value.read_ack(
            command_id="cmd-durable-001",
        )
