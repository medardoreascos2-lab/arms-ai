import json

from backend.services.sim_first_native_entry_preflight_v2 import (
    SimFirstNativeEntryPreflightV2,
)
from backend.services.sim_first_native_entry_preflight_coordinator_v2 import (
    SimFirstNativeEntryPreflightCoordinatorV2,
)
from backend.services.sim_submit_activation_inspection_source_v2 import (
    SimSubmitActivationInspectionSourceV2,
)


class RuntimeSource:
    def snapshot(self):
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


class Capability:
    def __init__(self, value=True):
        self.value = value

    def is_available(self):
        return self.value


def write_activation(
    directory,
    *,
    command_id="cmd-entry-1",
    operation_id="op-entry-1",
    client_order_id="op-entry-1",
):
    path = (
        directory
        / f"{command_id}.arm.json"
    )

    path.write_text(
        json.dumps(
            {
                "command_id": command_id,
                "operation_id": operation_id,
                "client_order_id": client_order_id,
                "permit": "ONE_SHOT_SIM101_V2",
                "account": "Sim101",
            },
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )

    return path


def build(tmp_path):
    activation_source = (
        SimSubmitActivationInspectionSourceV2(
            activation_directory=tmp_path,
        )
    )

    coordinator = (
        SimFirstNativeEntryPreflightCoordinatorV2(
            preflight=SimFirstNativeEntryPreflightV2(),
            runtime_source=RuntimeSource(),
            activation_source=activation_source,
            recovery_capability=Capability(True),
            native_evidence_capability=Capability(True),
        )
    )

    return coordinator


def test_real_activation_source_reaches_operator_review(tmp_path):
    write_activation(tmp_path)

    coordinator = build(tmp_path)

    result = coordinator.evaluate(
        command={
            "command_id": "cmd-entry-1",
            "operation_id": "op-entry-1",
            "client_order_id": "op-entry-1",
        }
    )

    assert (
        result["status"]
        == "READY_FOR_OPERATOR_REVIEW"
    )

    assert result["eligible"] is True
    assert (
        result["native_submit_enabled"]
        is False
    )
    assert (
        result["automatic_retry_allowed"]
        is False
    )


def test_real_consumed_marker_blocks_preflight(tmp_path):
    path = write_activation(tmp_path)

    consumed = (
        tmp_path
        / (path.name + ".consumed")
    )

    consumed.write_text(
        "consumed\n",
        encoding="utf-8",
    )

    coordinator = build(tmp_path)

    result = coordinator.evaluate(
        command={
            "command_id": "cmd-entry-1",
            "operation_id": "op-entry-1",
            "client_order_id": "op-entry-1",
        }
    )

    assert result["status"] == "BLOCKED"
    assert result["eligible"] is False
    assert (
        "ACTIVATION_ALREADY_CONSUMED"
        in result["blocking_reasons"]
    )


def test_real_activation_identity_mismatch_fails_closed(tmp_path):
    write_activation(
        tmp_path,
        command_id="cmd-entry-1",
        operation_id="op-entry-1",
        client_order_id="op-entry-1",
    )

    coordinator = build(tmp_path)

    try:
        coordinator.evaluate(
            command={
                "command_id": "cmd-entry-1",
                "operation_id": "op-other",
                "client_order_id": "op-other",
            }
        )
    except RuntimeError:
        return

    raise AssertionError(
        "activation identity mismatch must fail closed"
    )


def test_chain_has_no_execution_surface(tmp_path):
    write_activation(tmp_path)

    coordinator = build(tmp_path)

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
