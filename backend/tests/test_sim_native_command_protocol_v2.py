import pytest

from backend.services.sim_native_command_protocol_v2 import (
    SimNativeCommandProtocolV2,
)


def protocol():
    return SimNativeCommandProtocolV2()


def valid_submit():
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


def test_build_submit_command_requires_matching_durable_identity():
    value = protocol()

    command = value.build_submit_command(
        command_id="cmd-001",
        operation_id="op-001",
        client_order_id="op-001",
        prepared_order={
            "symbol": "NQ",
            "side": "BUY",
            "quantity": 1,
        },
    )

    assert command == valid_submit()


@pytest.mark.parametrize(
    ("operation_id", "client_order_id"),
    [
        ("op-001", "different"),
        ("", "op-001"),
        ("op-001", ""),
        (None, "op-001"),
        ("op-001", None),
    ],
)
def test_submit_identity_mismatch_or_missing_fails_closed(
    operation_id,
    client_order_id,
):
    value = protocol()

    with pytest.raises(
        ValueError,
        match="durable submit identity is invalid",
    ):
        value.build_submit_command(
            command_id="cmd-001",
            operation_id=operation_id,
            client_order_id=client_order_id,
            prepared_order={
                "symbol": "NQ",
                "side": "BUY",
                "quantity": 1,
            },
        )


def test_command_id_is_required():
    value = protocol()

    for bad in (
        None,
        "",
        "   ",
    ):
        with pytest.raises(
            ValueError,
            match="command_id is required",
        ):
            value.build_submit_command(
                command_id=bad,
                operation_id="op-001",
                client_order_id="op-001",
                prepared_order={
                    "symbol": "NQ",
                    "side": "BUY",
                    "quantity": 1,
                },
            )


def test_prepared_order_must_be_non_empty_dict():
    value = protocol()

    for bad in (
        None,
        [],
        {},
    ):
        with pytest.raises(
            ValueError,
            match="prepared_order is required",
        ):
            value.build_submit_command(
                command_id="cmd-001",
                operation_id="op-001",
                client_order_id="op-001",
                prepared_order=bad,
            )


def test_validate_ack_accepts_matching_native_ack():
    value = protocol()

    ack = value.validate_ack(
        command=valid_submit(),
        native_ack={
            "command_id": "cmd-001",
            "operation_id": "op-001",
            "client_order_id": "op-001",
            "status": "ACKNOWLEDGED",
            "accepted": True,
            "order_id": "native-order-1",
        },
    )

    assert ack["status"] == "ACKNOWLEDGED"
    assert ack["accepted"] is True
    assert ack["order_id"] == "native-order-1"


@pytest.mark.parametrize(
    "native_ack",
    [
        None,
        [],
        {},
        {
            "command_id": "wrong",
            "operation_id": "op-001",
            "client_order_id": "op-001",
            "status": "ACKNOWLEDGED",
            "accepted": True,
            "order_id": "native-order-1",
        },
        {
            "command_id": "cmd-001",
            "operation_id": "wrong",
            "client_order_id": "op-001",
            "status": "ACKNOWLEDGED",
            "accepted": True,
            "order_id": "native-order-1",
        },
        {
            "command_id": "cmd-001",
            "operation_id": "op-001",
            "client_order_id": "wrong",
            "status": "ACKNOWLEDGED",
            "accepted": True,
            "order_id": "native-order-1",
        },
        {
            "command_id": "cmd-001",
            "operation_id": "op-001",
            "client_order_id": "op-001",
            "status": "FILLED",
            "accepted": True,
            "order_id": "native-order-1",
        },
        {
            "command_id": "cmd-001",
            "operation_id": "op-001",
            "client_order_id": "op-001",
            "status": "ACKNOWLEDGED",
            "accepted": True,
            "order_id": "",
        },
    ],
)
def test_invalid_ack_fails_closed(native_ack):
    value = protocol()

    with pytest.raises(
        RuntimeError,
        match="invalid native SIM command acknowledgement",
    ):
        value.validate_ack(
            command=valid_submit(),
            native_ack=native_ack,
        )


def test_rejection_is_valid_terminal_ack_without_fill():
    value = protocol()

    ack = value.validate_ack(
        command=valid_submit(),
        native_ack={
            "command_id": "cmd-001",
            "operation_id": "op-001",
            "client_order_id": "op-001",
            "status": "REJECTED",
            "accepted": False,
            "order_id": "native-order-1",
        },
    )

    assert ack["status"] == "REJECTED"
    assert ack["accepted"] is False


def test_ack_must_never_contain_fill_or_position_evidence():
    value = protocol()

    with pytest.raises(
        RuntimeError,
        match="invalid native SIM command acknowledgement",
    ):
        value.validate_ack(
            command=valid_submit(),
            native_ack={
                "command_id": "cmd-001",
                "operation_id": "op-001",
                "client_order_id": "op-001",
                "status": "ACKNOWLEDGED",
                "accepted": True,
                "order_id": "native-order-1",
                "fill_id": "native-fill-1",
            },
        )


def test_timeout_classifies_unknown_and_forbids_retry():
    value = protocol()

    result = value.classify_timeout(
        command=valid_submit(),
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


def test_timeout_does_not_create_rejection_or_execution():
    value = protocol()

    result = value.classify_timeout(
        command=valid_submit(),
    )

    assert "accepted" not in result
    assert "order_id" not in result
    assert "fill_id" not in result
    assert "position_id" not in result


def test_duplicate_command_identity_must_not_be_regenerated():
    value = protocol()

    first = value.build_submit_command(
        command_id="cmd-001",
        operation_id="op-001",
        client_order_id="op-001",
        prepared_order={
            "symbol": "NQ",
            "side": "BUY",
            "quantity": 1,
        },
    )

    second = value.build_submit_command(
        command_id="cmd-001",
        operation_id="op-001",
        client_order_id="op-001",
        prepared_order={
            "symbol": "NQ",
            "side": "BUY",
            "quantity": 1,
        },
    )

    assert second == first


def test_command_protocol_has_no_transport_surface():
    value = protocol()

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
