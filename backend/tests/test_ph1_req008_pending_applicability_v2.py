from __future__ import annotations

import inspect
import json
import pytest

from backend.services.durable_execution_state_v2 import seal

from backend.services.state_recovery_service_v2 import (
    StateRecoveryServiceV2,
)


def test_state_recovery_exposes_pending_applicability_contract() -> None:
    """
    PH1-REQ-008:

    Startup must not infer pending-operation applicability from
    persistence internals.

    StateRecoveryServiceV2 owns the decision whether a durable
    checkpoint requires pending-operation reconciliation.
    """

    method = getattr(
        StateRecoveryServiceV2,
        "pending_reconciliation_required",
        None,
    )

    assert callable(method), (
        "PH1-REQ-008: StateRecoveryServiceV2 must expose "
        "pending_reconciliation_required(file_path=...) so "
        "startup can distinguish ordinary recovery from "
        "pending-operation reconciliation."
    )

    signature = inspect.signature(method)

    assert "file_path" in signature.parameters, (
        "pending_reconciliation_required must accept file_path"
    )


def _write_applicability_checkpoint(
    tmp_path,
    *,
    phase: str,
    pending_operation,
):
    path = tmp_path / "applicability-state.json"

    from backend.tests.test_durable_crash_recovery_v2 import (
        build_runtime,
    )

    store = build_runtime()[2]
    state = store.capture_state()

    if pending_operation is not None:
        state["pending_operation"] = pending_operation

    sealed = seal(
        state,
        generation=1,
        phase=phase,
    )

    path.write_text(
        json.dumps(sealed),
        encoding="utf-8",
    )

    return path


def _applicability_service() -> StateRecoveryServiceV2:
    from backend.tests.test_durable_crash_recovery_v2 import (
        build_runtime,
    )

    store = build_runtime()[2]

    return StateRecoveryServiceV2(
        execution_state_store=store,
    )


def test_committed_checkpoint_does_not_require_pending_reconciliation(
    tmp_path,
) -> None:
    """
    COMMITTED without a pending operation belongs to ordinary
    recovery and does not require pending reconciliation.
    """

    path = _write_applicability_checkpoint(
        tmp_path,
        phase="COMMITTED",
        pending_operation=None,
    )

    recovery = _applicability_service()

    assert (
        recovery.pending_reconciliation_required(
            file_path=path,
        )
        is False
    )


def test_pending_checkpoint_requires_pending_reconciliation(
    tmp_path,
) -> None:
    """
    PENDING with operation evidence requires reconciliation.
    """

    path = _write_applicability_checkpoint(
        tmp_path,
        phase="PENDING",
        pending_operation={
            "operation_id": "ph1-req008",
            "status": "PENDING",
        },
    )

    recovery = _applicability_service()

    assert (
        recovery.pending_reconciliation_required(
            file_path=path,
        )
        is True
    )


def test_contradictory_checkpoint_fails_closed(
    tmp_path,
) -> None:
    """
    PENDING durability without pending-operation evidence is
    contradictory and must fail closed.
    """

    path = _write_applicability_checkpoint(
        tmp_path,
        phase="PENDING",
        pending_operation=None,
    )

    recovery = _applicability_service()

    with pytest.raises(ValueError) as exc_info:
        recovery.pending_reconciliation_required(
            file_path=path,
        )

    assert "pending" in str(exc_info.value).lower()
