import json
from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.services.sim_first_native_entry_preflight_v2 import (
    SimFirstNativeEntryPreflightV2,
)
from backend.services.sim_first_native_entry_preflight_coordinator_v2 import (
    SimFirstNativeEntryPreflightCoordinatorV2,
)
from backend.services.sim_native_runtime_snapshot_reader_v2 import (
    SimNativeRuntimeSnapshotReaderV2,
)
from backend.services.sim_submit_activation_inspection_source_v2 import (
    SimSubmitActivationInspectionSourceV2,
)


NOW = datetime(
    2026,
    9,
    27,
    3,
    45,
    0,
    tzinfo=timezone.utc,
)


class Capability:
    def __init__(self, available=True):
        self.available = available

    def is_available(self):
        return self.available


def write_runtime(
    directory,
    *,
    observed_at=None,
    readiness="PHYSICAL_TEST_READY",
    position_state="FLAT",
    active_order_count=0,
):
    if observed_at is None:
        observed_at = (
            NOW - timedelta(seconds=1)
        ).isoformat()

    path = (
        directory
        / "sim-native-runtime-snapshot-v2.json"
    )

    path.write_text(
        json.dumps(
            {
                "schema":
                    "arms.nt.sim-runtime-readiness.v2",
                "observed_at":
                    observed_at,
                "account_name":
                    "Sim101",
                "provider":
                    "Simulator",
                "connection_status":
                    "Connected",
                "instrument":
                    "NQ DEC26",
                "physical_test_readiness":
                    readiness,
                "position_state":
                    position_state,
                "active_order_count":
                    active_order_count,
                "native_submit_enabled":
                    False,
                "auto_retry_allowed":
                    False,
            },
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )

    return path


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
                "command_id":
                    command_id,
                "operation_id":
                    operation_id,
                "client_order_id":
                    client_order_id,
                "permit":
                    "ONE_SHOT_SIM101_V2",
                "account":
                    "Sim101",
            },
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )

    return path


def command():
    return {
        "command_id":
            "cmd-entry-1",
        "operation_id":
            "op-entry-1",
        "client_order_id":
            "op-entry-1",
    }


def build(
    tmp_path,
    *,
    recovery_available=True,
    evidence_available=True,
):
    runtime_source = (
        SimNativeRuntimeSnapshotReaderV2(
            snapshot_directory=tmp_path,
            instrument="NQ DEC26",
            clock=lambda: NOW,
            maximum_age_seconds=15,
        )
    )

    activation_source = (
        SimSubmitActivationInspectionSourceV2(
            activation_directory=tmp_path,
        )
    )

    return (
        SimFirstNativeEntryPreflightCoordinatorV2(
            preflight=(
                SimFirstNativeEntryPreflightV2()
            ),
            runtime_source=runtime_source,
            activation_source=activation_source,
            recovery_capability=Capability(
                recovery_available
            ),
            native_evidence_capability=Capability(
                evidence_available
            ),
        )
    )


def test_real_filesystem_sources_reach_operator_review(
    tmp_path,
):
    write_runtime(tmp_path)
    write_activation(tmp_path)

    coordinator = build(tmp_path)

    result = coordinator.evaluate(
        command=command(),
    )

    assert (
        result["status"]
        == "READY_FOR_OPERATOR_REVIEW"
    )

    assert result["eligible"] is True
    assert result["blocking_reasons"] == []

    assert (
        result["native_submit_enabled"]
        is False
    )

    assert (
        result["automatic_retry_allowed"]
        is False
    )


def test_market_closed_blocks_real_filesystem_chain(
    tmp_path,
):
    write_runtime(
        tmp_path,
        readiness="MARKET_SESSION_CLOSED",
    )

    write_activation(tmp_path)

    result = build(
        tmp_path
    ).evaluate(
        command=command(),
    )

    assert result["status"] == "BLOCKED"

    assert (
        "PHYSICAL_TEST_NOT_READY"
        in result["blocking_reasons"]
    )


def test_nonflat_native_position_blocks_chain(
    tmp_path,
):
    write_runtime(
        tmp_path,
        position_state="LONG",
    )

    write_activation(tmp_path)

    result = build(
        tmp_path
    ).evaluate(
        command=command(),
    )

    assert result["status"] == "BLOCKED"

    assert (
        "POSITION_NOT_FLAT"
        in result["blocking_reasons"]
    )


def test_active_native_order_blocks_chain(
    tmp_path,
):
    write_runtime(
        tmp_path,
        active_order_count=1,
    )

    write_activation(tmp_path)

    result = build(
        tmp_path
    ).evaluate(
        command=command(),
    )

    assert result["status"] == "BLOCKED"

    assert (
        "ACTIVE_NATIVE_ORDERS_PRESENT"
        in result["blocking_reasons"]
    )


def test_consumed_activation_blocks_chain(
    tmp_path,
):
    write_runtime(tmp_path)

    activation = write_activation(
        tmp_path
    )

    (
        tmp_path
        / (activation.name + ".consumed")
    ).write_text(
        "consumed\n",
        encoding="utf-8",
    )

    result = build(
        tmp_path
    ).evaluate(
        command=command(),
    )

    assert result["status"] == "BLOCKED"

    assert (
        "ACTIVATION_ALREADY_CONSUMED"
        in result["blocking_reasons"]
    )


def test_stale_native_runtime_fails_closed(
    tmp_path,
):
    write_runtime(
        tmp_path,
        observed_at=(
            NOW
            - timedelta(seconds=16)
        ).isoformat(),
    )

    write_activation(tmp_path)

    with pytest.raises(RuntimeError):
        build(
            tmp_path
        ).evaluate(
            command=command(),
        )


def test_activation_identity_mismatch_fails_closed(
    tmp_path,
):
    write_runtime(tmp_path)

    write_activation(
        tmp_path,
        operation_id="op-entry-1",
        client_order_id="op-entry-1",
    )

    wrong_command = {
        "command_id":
            "cmd-entry-1",
        "operation_id":
            "op-other",
        "client_order_id":
            "op-other",
    }

    with pytest.raises(RuntimeError):
        build(
            tmp_path
        ).evaluate(
            command=wrong_command,
        )


def test_recovery_capability_absence_blocks_chain(
    tmp_path,
):
    write_runtime(tmp_path)
    write_activation(tmp_path)

    result = build(
        tmp_path,
        recovery_available=False,
    ).evaluate(
        command=command(),
    )

    assert result["status"] == "BLOCKED"

    assert (
        "RECOVERY_UNAVAILABLE"
        in result["blocking_reasons"]
    )


def test_native_evidence_capability_absence_blocks_chain(
    tmp_path,
):
    write_runtime(tmp_path)
    write_activation(tmp_path)

    result = build(
        tmp_path,
        evidence_available=False,
    ).evaluate(
        command=command(),
    )

    assert result["status"] == "BLOCKED"

    assert (
        "NATIVE_EVIDENCE_UNAVAILABLE"
        in result["blocking_reasons"]
    )


def test_end_to_end_chain_has_no_execution_surface(
    tmp_path,
):
    write_runtime(tmp_path)
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
        "consume",
        "arm",
    ):
        assert not hasattr(
            coordinator,
            forbidden,
        )
