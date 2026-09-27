from pathlib import Path

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


MODULE = (
    "backend.services."
    "sim_native_preflight_capabilities_v2"
)


def load_capabilities():
    module = __import__(
        MODULE,
        fromlist=[
            "SimNativeEvidenceCapabilityV2",
            "SimNativeRecoveryCapabilityV2",
        ],
    )

    return (
        module.SimNativeEvidenceCapabilityV2,
        module.SimNativeRecoveryCapabilityV2,
    )


def build_real_chain(tmp_path):
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

    adapter = (
        SimNativeEvidenceRecoveryAdapterV2(
            command_id="cmd-entry-1",
            evidence_reconciler=reconciler,
            evidence_reader=reader,
        )
    )

    recovery = (
        SimPendingOperationRecoveryV2(
            broker_connector=adapter,
        )
    )

    return (
        reader,
        reconciler,
        adapter,
        recovery,
    )


def test_real_empty_evidence_directory_is_available(
    tmp_path,
):
    EvidenceCapability, _ = (
        load_capabilities()
    )

    reader, _, _, _ = (
        build_real_chain(tmp_path)
    )

    capability = EvidenceCapability(
        evidence_reader=reader,
    )

    assert capability.is_available() is True


def test_real_recovery_chain_is_available_without_evidence(
    tmp_path,
):
    _, RecoveryCapability = (
        load_capabilities()
    )

    _, _, _, recovery = (
        build_real_chain(tmp_path)
    )

    capability = RecoveryCapability(
        recovery=recovery,
    )

    assert capability.is_available() is True


def test_evidence_capability_detects_missing_directory_after_start(
    tmp_path,
):
    EvidenceCapability, _ = (
        load_capabilities()
    )

    directory = (
        tmp_path / "evidence"
    )

    directory.mkdir()

    reader = (
        SimNativeOrderExecutionEvidenceReaderV2(
            evidence_directory=directory,
        )
    )

    capability = EvidenceCapability(
        evidence_reader=reader,
    )

    directory.rmdir()

    assert capability.is_available() is False


def test_evidence_capability_rejects_non_reader_shape():
    EvidenceCapability, _ = (
        load_capabilities()
    )

    class Invalid:
        pass

    capability = EvidenceCapability(
        evidence_reader=Invalid(),
    )

    assert capability.is_available() is False


def test_recovery_capability_rejects_missing_reconcile():
    _, RecoveryCapability = (
        load_capabilities()
    )

    class Invalid:
        pass

    capability = RecoveryCapability(
        recovery=Invalid(),
    )

    assert capability.is_available() is False


def test_recovery_capability_requires_sim_execution_mode():
    _, RecoveryCapability = (
        load_capabilities()
    )

    class Broker:
        execution_mode = "LIVE"

    class Recovery:
        broker_connector = Broker()

        def reconcile(
            self,
            *,
            operation_id,
        ):
            raise AssertionError(
                "reconcile must not be called"
            )

    capability = RecoveryCapability(
        recovery=Recovery(),
    )

    assert capability.is_available() is False


def test_recovery_availability_does_not_call_reconcile():
    _, RecoveryCapability = (
        load_capabilities()
    )

    class Broker:
        execution_mode = "SIM"

    class Recovery:
        broker_connector = Broker()

        def __init__(self):
            self.calls = 0

        def reconcile(
            self,
            *,
            operation_id,
        ):
            self.calls += 1

            raise AssertionError(
                "availability must not reconcile"
            )

    recovery = Recovery()

    capability = RecoveryCapability(
        recovery=recovery,
    )

    assert capability.is_available() is True
    assert recovery.calls == 0


def test_evidence_availability_does_not_read_command(
    tmp_path,
):
    EvidenceCapability, _ = (
        load_capabilities()
    )

    class Reader:
        def __init__(self, directory):
            self._directory = directory
            self.calls = 0

        def read_for_command(
            self,
            *,
            command_id,
            operation_id,
            client_order_id,
        ):
            self.calls += 1

            raise AssertionError(
                "availability must not read order evidence"
            )

    reader = Reader(
        Path(tmp_path)
    )

    capability = EvidenceCapability(
        evidence_reader=reader,
    )

    assert capability.is_available() is True
    assert reader.calls == 0


def test_capabilities_have_no_execution_surface(
    tmp_path,
):
    (
        EvidenceCapability,
        RecoveryCapability,
    ) = load_capabilities()

    reader, _, _, recovery = (
        build_real_chain(tmp_path)
    )

    evidence = EvidenceCapability(
        evidence_reader=reader,
    )

    recovery_capability = RecoveryCapability(
        recovery=recovery,
    )

    for value in (
        evidence,
        recovery_capability,
    ):
        for forbidden in (
            "submit_order",
            "cancel_order",
            "modify_order",
            "close_position",
            "close_partial",
            "flatten",
            "execute",
            "reconcile",
            "consume",
            "arm",
        ):
            assert not hasattr(
                value,
                forbidden,
            )
