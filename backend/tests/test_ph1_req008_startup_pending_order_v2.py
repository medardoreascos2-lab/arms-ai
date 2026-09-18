from __future__ import annotations

import inspect

from backend.services.startup_coordinator_v2 import StartupCoordinatorV2


def test_startup_classifies_pending_before_recovery_or_reconciliation() -> None:
    source = inspect.getsource(StartupCoordinatorV2.startup_from)

    applicability = source.find("pending_reconciliation_required")
    recovery = source.find("recover_from")
    reconciliation = source.find("reconcile_pending_from")

    assert applicability >= 0, (
        "PH1-REQ-008: startup must classify whether persisted state "
        "requires pending reconciliation."
    )

    assert recovery >= 0
    assert reconciliation >= 0

    assert applicability < recovery, (
        "PH1-REQ-008: applicability classification must happen "
        "before ordinary recovery."
    )

    assert applicability < reconciliation, (
        "PH1-REQ-008: applicability classification must happen "
        "before pending reconciliation."
    )


def test_startup_pending_decision_controls_reconciliation() -> None:
    source = inspect.getsource(StartupCoordinatorV2.startup_from)

    applicability = source.find("pending_reconciliation_required")
    reconciliation = source.find("reconcile_pending_from")

    assert applicability >= 0
    assert reconciliation > applicability

    decision_region = source[applicability:reconciliation]

    assert "if" in decision_region, (
        "PH1-REQ-008: reconciliation must be conditional on "
        "the applicability decision."
    )
