import json
from datetime import (
    datetime,
    timedelta,
    timezone,
)

from backend.services.sim_first_native_entry_preflight_v2 import (
    SimFirstNativeEntryPreflightV2,
)
from backend.services.sim_first_native_entry_preflight_coordinator_v2 import (
    SimFirstNativeEntryPreflightCoordinatorV2,
)
from backend.services.sim_native_evidence_recovery_adapter_v2 import (
    SimNativeEvidenceRecoveryAdapterV2,
)
from backend.services.sim_native_order_execution_evidence_reader_v2 import (
    SimNativeOrderExecutionEvidenceReaderV2,
)
from backend.services.sim_native_order_execution_reconciler_v2 import (
    SimNativeOrderExecutionReconcilerV2,
)
from backend.services.sim_native_preflight_capabilities_v2 import (
    SimNativeEvidenceCapabilityV2,
    SimNativeRecoveryCapabilityV2,
)
from backend.services.sim_native_runtime_snapshot_reader_v2 import (
    SimNativeRuntimeSnapshotReaderV2,
)
from backend.services.sim_pending_operation_recovery_v2 import (
    SimPendingOperationRecoveryV2,
)
from backend.services.sim_submit_activation_inspection_source_v2 import (
    SimSubmitActivationInspectionSourceV2,
)


NOW = datetime(
    2026,
    9,
    27,
    4,
    15,
    0,
    tzinfo=timezone.utc,
)

COMMAND_ID = "cmd-entry-1"
OPERATION_ID = "op-entry-1"


def command():
    return {
        "command_id": COMMAND_ID,
        "operation_id": OPERATION_ID,
        "client_order_id": OPERATION_ID,
    }


def prepare_directories(tmp_path):
    runtime_directory = (
        tmp_path / "runtime"
    )

    activation_directory = (
        tmp_path / "activation"
    )

    evidence_directory = (
        tmp_path / "native-evidence"
    )

    runtime_directory.mkdir()
    activation_directory.mkdir()
    evidence_directory.mkdir()

    return (
        runtime_directory,
        activation_directory,
        evidence_directory,
    )


def write_runtime(
    directory,
    *,
    readiness="PHYSICAL_TEST_READY",
    position_state="FLAT",
    active_order_count=0,
):
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
                    (
                        NOW
                        - timedelta(seconds=1)
                    ).isoformat(),
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


def write_activation(
    directory,
):
    path = (
        directory
        / f"{COMMAND_ID}.arm.json"
    )

    path.write_text(
        json.dumps(
            {
                "command_id":
                    COMMAND_ID,
                "operation_id":
                    OPERATION_ID,
                "client_order_id":
                    OPERATION_ID,
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


def build_operational_chain(
    *,
    runtime_directory,
    activation_directory,
    evidence_directory,
):
    runtime_source = (
        SimNativeRuntimeSnapshotReaderV2(
            snapshot_directory=runtime_directory,
            instrument="NQ DEC26",
            clock=lambda: NOW,
            maximum_age_seconds=15,
        )
    )

    activation_source = (
        SimSubmitActivationInspectionSourceV2(
            activation_directory=activation_directory,
        )
    )

    evidence_reader = (
        SimNativeOrderExecutionEvidenceReaderV2(
            evidence_directory=evidence_directory,
        )
    )

    reconciler = (
        SimNativeOrderExecutionReconcilerV2(
            evidence_reader=evidence_reader,
        )
    )

    recovery_adapter = (
        SimNativeEvidenceRecoveryAdapterV2(
            command_id=COMMAND_ID,
            evidence_reconciler=reconciler,
            evidence_reader=evidence_reader,
        )
    )

    recovery = (
        SimPendingOperationRecoveryV2(
            broker_connector=recovery_adapter,
        )
    )

    evidence_capability = (
        SimNativeEvidenceCapabilityV2(
            evidence_reader=evidence_reader,
        )
    )

    recovery_capability = (
        SimNativeRecoveryCapabilityV2(
            recovery=recovery,
        )
    )

    coordinator = (
        SimFirstNativeEntryPreflightCoordinatorV2(
            preflight=(
                SimFirstNativeEntryPreflightV2()
            ),
            runtime_source=runtime_source,
            activation_source=activation_source,
            recovery_capability=recovery_capability,
            native_evidence_capability=(
                evidence_capability
            ),
        )
    )

    return {
        "coordinator": coordinator,
        "runtime_source": runtime_source,
        "activation_source": activation_source,
        "evidence_reader": evidence_reader,
        "reconciler": reconciler,
        "recovery_adapter": recovery_adapter,
        "recovery": recovery,
        "evidence_capability":
            evidence_capability,
        "recovery_capability":
            recovery_capability,
    }


def test_all_real_preflight_sources_reach_operator_review(
    tmp_path,
):
    (
        runtime_directory,
        activation_directory,
        evidence_directory,
    ) = prepare_directories(
        tmp_path
    )

    write_runtime(
        runtime_directory
    )

    write_activation(
        activation_directory
    )

    chain = build_operational_chain(
        runtime_directory=runtime_directory,
        activation_directory=activation_directory,
        evidence_directory=evidence_directory,
    )

    result = chain[
        "coordinator"
    ].evaluate(
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


def test_empty_native_evidence_directory_is_valid_before_first_submit(
    tmp_path,
):
    (
        runtime_directory,
        activation_directory,
        evidence_directory,
    ) = prepare_directories(
        tmp_path
    )

    write_runtime(
        runtime_directory
    )

    write_activation(
        activation_directory
    )

    assert list(
        evidence_directory.iterdir()
    ) == []

    chain = build_operational_chain(
        runtime_directory=runtime_directory,
        activation_directory=activation_directory,
        evidence_directory=evidence_directory,
    )

    assert (
        chain[
            "evidence_capability"
        ].is_available()
        is True
    )

    assert (
        chain[
            "recovery_capability"
        ].is_available()
        is True
    )

    result = chain[
        "coordinator"
    ].evaluate(
        command=command(),
    )

    assert result["eligible"] is True


def test_native_evidence_infrastructure_loss_blocks_preflight(
    tmp_path,
):
    (
        runtime_directory,
        activation_directory,
        evidence_directory,
    ) = prepare_directories(
        tmp_path
    )

    write_runtime(
        runtime_directory
    )

    write_activation(
        activation_directory
    )

    chain = build_operational_chain(
        runtime_directory=runtime_directory,
        activation_directory=activation_directory,
        evidence_directory=evidence_directory,
    )

    evidence_directory.rmdir()

    result = chain[
        "coordinator"
    ].evaluate(
        command=command(),
    )

    assert result["status"] == "BLOCKED"
    assert result["eligible"] is False

    assert (
        "NATIVE_EVIDENCE_UNAVAILABLE"
        in result["blocking_reasons"]
    )


def test_operational_preflight_does_not_reconcile_or_read_order_evidence(
    tmp_path,
):
    (
        runtime_directory,
        activation_directory,
        evidence_directory,
    ) = prepare_directories(
        tmp_path
    )

    write_runtime(
        runtime_directory
    )

    write_activation(
        activation_directory
    )

    chain = build_operational_chain(
        runtime_directory=runtime_directory,
        activation_directory=activation_directory,
        evidence_directory=evidence_directory,
    )

    evidence_calls = {
        "count": 0,
    }

    recovery_calls = {
        "count": 0,
    }

    original_read = (
        chain[
            "evidence_reader"
        ].read_for_command
    )

    original_reconcile = (
        chain[
            "recovery"
        ].reconcile
    )

    def forbidden_read(
        *,
        command_id,
        operation_id,
        client_order_id,
    ):
        evidence_calls["count"] += 1

        return original_read(
            command_id=command_id,
            operation_id=operation_id,
            client_order_id=client_order_id,
        )

    def forbidden_reconcile(
        *,
        operation_id,
    ):
        recovery_calls["count"] += 1

        return original_reconcile(
            operation_id=operation_id,
        )

    chain[
        "evidence_reader"
    ].read_for_command = forbidden_read

    chain[
        "recovery"
    ].reconcile = forbidden_reconcile

    result = chain[
        "coordinator"
    ].evaluate(
        command=command(),
    )

    assert result["eligible"] is True

    assert evidence_calls["count"] == 0
    assert recovery_calls["count"] == 0


def test_operational_chain_exposes_no_execution_surface(
    tmp_path,
):
    (
        runtime_directory,
        activation_directory,
        evidence_directory,
    ) = prepare_directories(
        tmp_path
    )

    write_runtime(
        runtime_directory
    )

    write_activation(
        activation_directory
    )

    chain = build_operational_chain(
        runtime_directory=runtime_directory,
        activation_directory=activation_directory,
        evidence_directory=evidence_directory,
    )

    protected = (
        chain["coordinator"],
        chain["runtime_source"],
        chain["activation_source"],
        chain["evidence_capability"],
        chain["recovery_capability"],
    )

    for value in protected:
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
                value,
                forbidden,
            )
