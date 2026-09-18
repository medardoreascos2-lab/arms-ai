from __future__ import annotations

import inspect

import pytest

from backend.services.startup_coordinator_v2 import StartupCoordinatorV2


UNSAFE_PENDING_STATUSES = (
    "AMBIGUOUS",
    "CORRUPT",
    "PARTIALLY_EXECUTED",
)


def test_startup_from_has_pending_reconciliation_boundary() -> None:
    source = inspect.getsource(StartupCoordinatorV2.startup_from)

    assert "reconcile_pending_from" in source
    assert "durability.enable" in source


@pytest.mark.parametrize(
    "status",
    UNSAFE_PENDING_STATUSES,
)
def test_unsafe_pending_status_cannot_be_ignored_before_enable(
    status: str,
) -> None:
    """
    PH1-REQ-008 behavioral contract.

    Once startup reconciles a persisted pending operation, an unsafe
    reconciliation result must be evaluated before durability can be
    enabled and startup can be declared recovered.
    """

    source = inspect.getsource(StartupCoordinatorV2.startup_from)

    reconciliation = source.find("reconcile_pending_from")

    assert reconciliation >= 0

    enable = source.find(
        "durability.enable",
        reconciliation,
    )

    assert enable > reconciliation, (
        "startup must have a durability.enable() call after "
        "pending reconciliation"
    )

    decision_region = source[
        reconciliation:enable
    ]

    assert (
        "pending_report" in decision_region
    ), "startup must retain the reconciliation result"

    assert (
        'pending_report.get("resolved", False)'
        in decision_region
    ), (
        f"PH1-REQ-008: startup reaches durability.enable() "
        f"without guarding unresolved pending reconciliation "
        f"({status})."
    )

    assert (
        "raise RuntimeError" in decision_region
    ), (
        f"PH1-REQ-008: unsafe pending reconciliation "
        f"({status}) must stop startup before durability.enable()."
    )
