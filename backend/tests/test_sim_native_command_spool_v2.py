import json
from pathlib import Path

import pytest

from backend.services.sim_native_command_spool_v2 import (
    SimNativeCommandSpoolV2,
)


def command():
    return {
        "command_id": "cmd-001",
        "operation_id": "op-001",
        "command": "SUBMIT_ORDER",
        "client_order_id": "op-001",
        "payload": {
            "symbol": "NQ",
            "side": "BUY",
            "quantity": 1,
        },
    }


def ack():
    return {
        "command_id": "cmd-001",
        "operation_id": "op-001",
        "client_order_id": "op-001",
        "status": "ACKNOWLEDGED",
        "accepted": True,
        "order_id": "native-order-1",
    }


def spool(tmp_path):
    return SimNativeCommandSpoolV2(
        root=tmp_path,
    )


def test_write_command_creates_durable_command_file(tmp_path):
    value = spool(tmp_path)

    result = value.write_command(
        command=command(),
    )

    assert result["created"] is True
    assert result["idempotent"] is False
    assert result["command_id"] == "cmd-001"

    path = Path(result["path"])

    assert path.is_file()

    saved = json.loads(
        path.read_text(
            encoding="utf-8",
        )
    )

    assert saved == command()


def test_identical_command_write_is_idempotent(tmp_path):
    value = spool(tmp_path)

    first = value.write_command(
        command=command(),
    )

    second = value.write_command(
        command=command(),
    )

    assert first["path"] == second["path"]
    assert second["created"] is False
    assert second["idempotent"] is True


def test_same_command_id_with_different_payload_fails_closed(tmp_path):
    value = spool(tmp_path)

    value.write_command(
        command=command(),
    )

    changed = command()
    changed["payload"]["quantity"] = 2

    with pytest.raises(
        RuntimeError,
        match="command identity collision",
    ):
        value.write_command(
            command=changed,
        )


@pytest.mark.parametrize(
    "bad",
    [
        None,
        [],
        {},
        {
            "command_id": "",
            "operation_id": "op-001",
            "command": "SUBMIT_ORDER",
            "client_order_id": "op-001",
            "payload": {"symbol": "NQ"},
        },
        {
            "command_id": "cmd-001",
            "operation_id": "op-001",
            "command": "SUBMIT_ORDER",
            "client_order_id": "wrong",
            "payload": {"symbol": "NQ"},
        },
    ],
)
def test_invalid_command_shape_fails_closed(
    tmp_path,
    bad,
):
    value = spool(tmp_path)

    with pytest.raises(
        ValueError,
        match="invalid native SIM command",
    ):
        value.write_command(
            command=bad,
        )


def test_write_ack_requires_existing_command(tmp_path):
    value = spool(tmp_path)

    with pytest.raises(
        RuntimeError,
        match="command evidence not found",
    ):
        value.write_ack(
            native_ack=ack(),
        )


def test_matching_ack_is_written_separately(tmp_path):
    value = spool(tmp_path)

    command_result = value.write_command(
        command=command(),
    )

    ack_result = value.write_ack(
        native_ack=ack(),
    )

    command_path = Path(
        command_result["path"]
    )
    ack_path = Path(
        ack_result["path"]
    )

    assert ack_path.is_file()
    assert ack_path != command_path

    assert json.loads(
        ack_path.read_text(
            encoding="utf-8",
        )
    ) == ack()


def test_ack_identity_mismatch_fails_closed(tmp_path):
    value = spool(tmp_path)

    value.write_command(
        command=command(),
    )

    bad_ack = ack()
    bad_ack["operation_id"] = "wrong"

    with pytest.raises(
        RuntimeError,
        match="ack identity does not match command",
    ):
        value.write_ack(
            native_ack=bad_ack,
        )


def test_identical_ack_write_is_idempotent(tmp_path):
    value = spool(tmp_path)

    value.write_command(
        command=command(),
    )

    first = value.write_ack(
        native_ack=ack(),
    )

    second = value.write_ack(
        native_ack=ack(),
    )

    assert first["path"] == second["path"]
    assert second["created"] is False
    assert second["idempotent"] is True


def test_ack_collision_fails_closed(tmp_path):
    value = spool(tmp_path)

    value.write_command(
        command=command(),
    )

    value.write_ack(
        native_ack=ack(),
    )

    changed = ack()
    changed["status"] = "REJECTED"
    changed["accepted"] = False

    with pytest.raises(
        RuntimeError,
        match="ack evidence collision",
    ):
        value.write_ack(
            native_ack=changed,
        )


def test_read_ack_returns_none_when_response_missing(tmp_path):
    value = spool(tmp_path)

    value.write_command(
        command=command(),
    )

    assert value.read_ack(
        command_id="cmd-001",
    ) is None


def test_read_ack_returns_matching_response(tmp_path):
    value = spool(tmp_path)

    value.write_command(
        command=command(),
    )

    value.write_ack(
        native_ack=ack(),
    )

    result = value.read_ack(
        command_id="cmd-001",
    )

    assert result == ack()


def test_truncated_command_file_fails_closed(tmp_path):
    value = spool(tmp_path)

    result = value.write_command(
        command=command(),
    )

    path = Path(result["path"])

    path.write_text(
        '{"command_id":',
        encoding="utf-8",
    )

    with pytest.raises(
        RuntimeError,
        match="corrupt command evidence",
    ):
        value.read_command(
            command_id="cmd-001",
        )


def test_truncated_ack_file_fails_closed(tmp_path):
    value = spool(tmp_path)

    value.write_command(
        command=command(),
    )

    result = value.write_ack(
        native_ack=ack(),
    )

    path = Path(result["path"])

    path.write_text(
        '{"status":',
        encoding="utf-8",
    )

    with pytest.raises(
        RuntimeError,
        match="corrupt ack evidence",
    ):
        value.read_ack(
            command_id="cmd-001",
        )


def test_timeout_without_ack_is_unknown_and_never_retryable(tmp_path):
    value = spool(tmp_path)

    value.write_command(
        command=command(),
    )

    result = value.classify_pending(
        command_id="cmd-001",
    )

    assert result == {
        "status": "UNKNOWN",
        "resolved": False,
        "command_id": "cmd-001",
        "operation_id": "op-001",
        "client_order_id": "op-001",
        "automatic_retry_allowed": False,
        "reconciliation_required": True,
    }


def test_ack_resolves_pending_command(tmp_path):
    value = spool(tmp_path)

    value.write_command(
        command=command(),
    )

    value.write_ack(
        native_ack=ack(),
    )

    result = value.classify_pending(
        command_id="cmd-001",
    )

    assert result["status"] == "ACKNOWLEDGED"
    assert result["resolved"] is True
    assert result["automatic_retry_allowed"] is False
    assert result["reconciliation_required"] is False


def test_spool_has_no_order_transport_surface(tmp_path):
    value = spool(tmp_path)

    for name in (
        "connect",
        "submit_order",
        "modify_order",
        "cancel_order",
        "close_position",
        "close_partial",
    ):
        assert not hasattr(
            value,
            name,
        )
