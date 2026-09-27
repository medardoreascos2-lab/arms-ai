import pytest


MODULE = (
    "backend.services."
    "sim_first_native_entry_preflight_coordinator_v2"
)


def load_coordinator():
    module = __import__(
        MODULE,
        fromlist=[
            "SimFirstNativeEntryPreflightCoordinatorV2"
        ],
    )

    return (
        module
        .SimFirstNativeEntryPreflightCoordinatorV2
    )


class FakePreflight:
    def __init__(self):
        self.calls = []

    def evaluate(self, **kwargs):
        self.calls.append(
            dict(kwargs)
        )

        return {
            "status": "READY_FOR_OPERATOR_REVIEW",
            "eligible": True,
            "blocking_reasons": [],
            "native_submit_enabled": False,
            "automatic_retry_allowed": False,
        }


class FakeRuntimeSource:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = 0

    def snapshot(self):
        self.calls += 1

        if self.error is not None:
            raise self.error

        return dict(self.result)


class FakeActivationSource:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def inspect(
        self,
        *,
        command_id,
    ):
        self.calls.append(
            command_id
        )

        if self.error is not None:
            raise self.error

        return dict(self.result)


class FakeCapability:
    def __init__(self, available=True):
        self.available = available

    def is_available(self):
        return self.available


def runtime_snapshot():
    return {
        "account_name": "Sim101",
        "provider": "Simulator",
        "connection_status": "Connected",
        "physical_test_readiness": (
            "PHYSICAL_TEST_READY"
        ),
        "position_state": "FLAT",
        "active_order_count": 0,
        "native_submit_enabled": False,
        "auto_retry_allowed": False,
    }


def activation_snapshot():
    return {
        "valid": True,
        "consumed": False,
        "command_id": "cmd-entry-1",
        "operation_id": "op-entry-1",
        "client_order_id": "op-entry-1",
    }


def command():
    return {
        "command_id": "cmd-entry-1",
        "operation_id": "op-entry-1",
        "client_order_id": "op-entry-1",
    }


def build(
    *,
    runtime=None,
    activation=None,
    recovery_available=True,
    evidence_available=True,
):
    Coordinator = load_coordinator()

    preflight = FakePreflight()

    coordinator = Coordinator(
        preflight=preflight,
        runtime_source=FakeRuntimeSource(
            result=(
                runtime
                if runtime is not None
                else runtime_snapshot()
            )
        ),
        activation_source=FakeActivationSource(
            result=(
                activation
                if activation is not None
                else activation_snapshot()
            )
        ),
        recovery_capability=FakeCapability(
            recovery_available
        ),
        native_evidence_capability=FakeCapability(
            evidence_available
        ),
    )

    return coordinator, preflight


def test_valid_sources_delegate_exactly_once():
    coordinator, preflight = build()

    result = coordinator.evaluate(
        command=command(),
    )

    assert result["status"] == "READY_FOR_OPERATOR_REVIEW"
    assert result["eligible"] is True

    assert len(preflight.calls) == 1

    call = preflight.calls[0]

    assert call == {
        "account_name": "Sim101",
        "provider": "Simulator",
        "connection_status": "Connected",
        "physical_test_readiness": "PHYSICAL_TEST_READY",
        "position_state": "FLAT",
        "active_order_count": 0,
        "activation_valid": True,
        "activation_consumed": False,
        "command_id": "cmd-entry-1",
        "operation_id": "op-entry-1",
        "client_order_id": "op-entry-1",
        "native_submit_enabled": False,
        "auto_retry_allowed": False,
        "recovery_available": True,
        "native_evidence_available": True,
    }


def test_runtime_snapshot_must_be_dict():
    Coordinator = load_coordinator()

    coordinator = Coordinator(
        preflight=FakePreflight(),
        runtime_source=FakeRuntimeSource(
            result=[]
        ),
        activation_source=FakeActivationSource(
            result=activation_snapshot()
        ),
        recovery_capability=FakeCapability(),
        native_evidence_capability=FakeCapability(),
    )

    with pytest.raises(RuntimeError):
        coordinator.evaluate(
            command=command(),
        )


def test_activation_snapshot_must_be_dict():
    Coordinator = load_coordinator()

    coordinator = Coordinator(
        preflight=FakePreflight(),
        runtime_source=FakeRuntimeSource(
            result=runtime_snapshot()
        ),
        activation_source=FakeActivationSource(
            result=[]
        ),
        recovery_capability=FakeCapability(),
        native_evidence_capability=FakeCapability(),
    )

    with pytest.raises(RuntimeError):
        coordinator.evaluate(
            command=command(),
        )


def test_command_must_be_dict():
    coordinator, _ = build()

    with pytest.raises(RuntimeError):
        coordinator.evaluate(
            command=[],
        )


def test_command_identity_is_forwarded_without_mutation():
    coordinator, preflight = build(
        activation={
            "valid": True,
            "consumed": False,
            "command_id": "cmd-X_1",
            "operation_id": "op-X_1",
            "client_order_id": "op-X_1",
        }
    )

    payload = {
        "command_id": "cmd-X_1",
        "operation_id": "op-X_1",
        "client_order_id": "op-X_1",
    }

    coordinator.evaluate(
        command=payload,
    )

    call = preflight.calls[0]

    assert call["command_id"] == "cmd-X_1"
    assert call["operation_id"] == "op-X_1"
    assert call["client_order_id"] == "op-X_1"


def test_recovery_capability_false_is_forwarded():
    coordinator, preflight = build(
        recovery_available=False
    )

    coordinator.evaluate(
        command=command(),
    )

    assert (
        preflight.calls[0][
            "recovery_available"
        ]
        is False
    )


def test_evidence_capability_false_is_forwarded():
    coordinator, preflight = build(
        evidence_available=False
    )

    coordinator.evaluate(
        command=command(),
    )

    assert (
        preflight.calls[0][
            "native_evidence_available"
        ]
        is False
    )


def test_runtime_source_exception_fails_closed():
    Coordinator = load_coordinator()

    coordinator = Coordinator(
        preflight=FakePreflight(),
        runtime_source=FakeRuntimeSource(
            result={},
            error=RuntimeError(
                "runtime unavailable"
            ),
        ),
        activation_source=FakeActivationSource(
            result=activation_snapshot()
        ),
        recovery_capability=FakeCapability(),
        native_evidence_capability=FakeCapability(),
    )

    with pytest.raises(
        RuntimeError,
        match="runtime unavailable",
    ):
        coordinator.evaluate(
            command=command(),
        )


def test_activation_source_exception_fails_closed():
    Coordinator = load_coordinator()

    coordinator = Coordinator(
        preflight=FakePreflight(),
        runtime_source=FakeRuntimeSource(
            result=runtime_snapshot()
        ),
        activation_source=FakeActivationSource(
            result={},
            error=RuntimeError(
                "activation unavailable"
            ),
        ),
        recovery_capability=FakeCapability(),
        native_evidence_capability=FakeCapability(),
    )

    with pytest.raises(
        RuntimeError,
        match="activation unavailable",
    ):
        coordinator.evaluate(
            command=command(),
        )


def test_missing_runtime_field_fails_closed():
    snapshot = runtime_snapshot()
    snapshot.pop(
        "position_state"
    )

    coordinator, _ = build(
        runtime=snapshot
    )

    with pytest.raises(RuntimeError):
        coordinator.evaluate(
            command=command(),
        )


def test_missing_activation_field_fails_closed():
    snapshot = activation_snapshot()
    snapshot.pop(
        "consumed"
    )

    coordinator, _ = build(
        activation=snapshot
    )

    with pytest.raises(RuntimeError):
        coordinator.evaluate(
            command=command(),
        )


def test_coordinator_has_no_execution_surface():
    coordinator, _ = build()

    for forbidden in (
        "submit_order",
        "cancel_order",
        "modify_order",
        "close_position",
        "close_partial",
        "flatten",
        "execute",
    ):
        assert not hasattr(
            coordinator,
            forbidden,
        )
