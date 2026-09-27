import pytest

from backend.services.sim_native_command_consumer_v2 import (
    SimNativeCommandConsumerV2,
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


class FakeSpool:
    def __init__(
        self,
        *,
        stored_command=None,
        stored_ack=None,
    ):
        self.stored_command = stored_command
        self.stored_ack = stored_ack
        self.calls = []

    def read_command(
        self,
        *,
        command_id,
    ):
        self.calls.append(
            ("read_command", command_id)
        )

        if self.stored_command is None:
            return None

        return dict(self.stored_command)

    def read_ack(
        self,
        *,
        command_id,
    ):
        self.calls.append(
            ("read_ack", command_id)
        )

        if self.stored_ack is None:
            return None

        return dict(self.stored_ack)

    def write_ack(
        self,
        *,
        native_ack,
    ):
        self.calls.append(
            ("write_ack", dict(native_ack))
        )

        self.stored_ack = dict(native_ack)

        return {
            "created": True,
            "idempotent": False,
            "command_id": native_ack["command_id"],
            "path": "fake-ack.json",
        }


class FakeExecutor:
    def __init__(
        self,
        *,
        result=None,
        error=None,
    ):
        self.result = result
        self.error = error
        self.calls = []

    def submit_order(
        self,
        *,
        prepared_order,
        command_id,
        operation_id,
        client_order_id,
    ):
        self.calls.append(
            {
                "prepared_order": dict(prepared_order),
                "command_id": command_id,
                "operation_id": operation_id,
                "client_order_id": client_order_id,
            }
        )

        if self.error is not None:
            raise self.error

        return dict(self.result)


def consumer(
    *,
    stored_command=None,
    stored_ack=None,
    executor_result=None,
    executor_error=None,
):
    spool = FakeSpool(
        stored_command=stored_command,
        stored_ack=stored_ack,
    )

    executor = FakeExecutor(
        result=executor_result,
        error=executor_error,
    )

    value = SimNativeCommandConsumerV2(
        spool=spool,
        executor=executor,
    )

    return value, spool, executor


def valid_executor_ack():
    return {
        "command_id": "cmd-001",
        "operation_id": "op-001",
        "client_order_id": "op-001",
        "status": "ACKNOWLEDGED",
        "accepted": True,
        "order_id": "native-order-1",
    }


def test_missing_command_fails_closed():
    value, spool, executor = consumer()

    with pytest.raises(
        RuntimeError,
        match="command evidence not found",
    ):
        value.consume(
            command_id="cmd-001",
        )

    assert executor.calls == []


def test_existing_ack_prevents_duplicate_execution():
    existing_ack = valid_executor_ack()

    value, spool, executor = consumer(
        stored_command=command(),
        stored_ack=existing_ack,
    )

    result = value.consume(
        command_id="cmd-001",
    )

    assert result["status"] == "ACKNOWLEDGED"
    assert result["idempotent_replay"] is True
    assert executor.calls == []

    assert [
        call[0]
        for call in spool.calls
    ] == [
        "read_command",
        "read_ack",
    ]


def test_new_command_executes_once_and_writes_ack():
    value, spool, executor = consumer(
        stored_command=command(),
        executor_result=valid_executor_ack(),
    )

    result = value.consume(
        command_id="cmd-001",
    )

    assert result["status"] == "ACKNOWLEDGED"
    assert result["idempotent_replay"] is False

    assert len(executor.calls) == 1

    assert executor.calls[0] == {
        "prepared_order": {
            "symbol": "NQ",
            "side": "BUY",
            "quantity": 1,
        },
        "command_id": "cmd-001",
        "operation_id": "op-001",
        "client_order_id": "op-001",
    }

    assert [
        call[0]
        for call in spool.calls
    ] == [
        "read_command",
        "read_ack",
        "write_ack",
    ]


def test_rejected_native_result_is_persisted_as_ack():
    rejected = {
        "command_id": "cmd-001",
        "operation_id": "op-001",
        "client_order_id": "op-001",
        "status": "REJECTED",
        "accepted": False,
        "order_id": "native-order-1",
    }

    value, spool, executor = consumer(
        stored_command=command(),
        executor_result=rejected,
    )

    result = value.consume(
        command_id="cmd-001",
    )

    assert result["status"] == "REJECTED"
    assert result["accepted"] is False
    assert len(executor.calls) == 1

    writes = [
        call
        for call in spool.calls
        if call[0] == "write_ack"
    ]

    assert len(writes) == 1
    assert writes[0][1] == rejected


@pytest.mark.parametrize(
    "bad",
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
            "operation_id": "op-001",
            "client_order_id": "op-001",
            "status": "FILLED",
            "accepted": True,
            "order_id": "native-order-1",
        },
    ],
)
def test_invalid_executor_ack_never_gets_persisted(
    bad,
):
    value, spool, executor = consumer(
        stored_command=command(),
        executor_result=bad,
    )

    with pytest.raises(
        RuntimeError,
        match="invalid native SIM consumer acknowledgement",
    ):
        value.consume(
            command_id="cmd-001",
        )

    assert not any(
        call[0] == "write_ack"
        for call in spool.calls
    )


def test_executor_exception_becomes_unknown_without_ack():
    value, spool, executor = consumer(
        stored_command=command(),
        executor_error=TimeoutError(
            "simulated native timeout"
        ),
    )

    result = value.consume(
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
        "reason": "native_execution_outcome_unknown",
    }

    assert len(executor.calls) == 1

    assert not any(
        call[0] == "write_ack"
        for call in spool.calls
    )


def test_unknown_outcome_is_not_automatically_reexecuted_by_consumer_instance():
    value, spool, executor = consumer(
        stored_command=command(),
        executor_error=TimeoutError(
            "simulated native timeout"
        ),
    )

    first = value.consume(
        command_id="cmd-001",
    )

    assert first["status"] == "UNKNOWN"

    executor.error = None
    executor.result = valid_executor_ack()

    second = value.consume(
        command_id="cmd-001",
    )

    assert second["status"] == "UNKNOWN"
    assert second["automatic_retry_allowed"] is False

    assert len(executor.calls) == 1


def test_command_identity_must_be_self_consistent():
    bad_command = command()
    bad_command["client_order_id"] = "wrong"

    value, spool, executor = consumer(
        stored_command=bad_command,
        executor_result=valid_executor_ack(),
    )

    with pytest.raises(
        RuntimeError,
        match="invalid native SIM consumer command",
    ):
        value.consume(
            command_id="cmd-001",
        )

    assert executor.calls == []


def test_consumer_has_no_broker_mutation_surface():
    value, spool, executor = consumer(
        stored_command=command(),
        executor_result=valid_executor_ack(),
    )

    for name in (
        "modify_order",
        "cancel_order",
        "close_position",
        "close_partial",
    ):
        assert not hasattr(
            value,
            name,
        )
