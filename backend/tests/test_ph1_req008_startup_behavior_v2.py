from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest

from backend.services.startup_coordinator_v2 import StartupCoordinatorV2


class TrackingDurability:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.enabled = False
        self.failed = False
        self.released = False

    def acquire(self, path) -> None:
        self.events.append("acquire")

    def enable(self) -> None:
        self.events.append("enable")
        self.enabled = True

    def fail_closed(self) -> None:
        self.events.append("fail_closed")
        self.failed = True

    def release(self) -> None:
        self.events.append("release")
        self.released = True


class BehavioralRecoveryService:
    def __init__(
        self,
        *,
        pending_required: bool,
        reconciliation_resolved: bool = True,
    ) -> None:
        self.events: list[str] = []
        self.pending_required = pending_required
        self.reconciliation_resolved = reconciliation_resolved

        self.execution_state_store = Mock()
        self.execution_state_store._durability = TrackingDurability(
            self.events
        )

    def has_saved_state(self, *, file_path) -> bool:
        self.events.append("has_saved_state")
        return True

    def pending_reconciliation_required(self, *, file_path) -> bool:
        self.events.append("applicability")
        return self.pending_required

    def reconcile_pending_from(self, *, file_path):
        self.events.append("reconcile")
        return {
            "status": (
                "CONFIRMED_NOT_EXECUTED"
                if self.reconciliation_resolved
                else "AMBIGUOUS"
            ),
            "resolved": self.reconciliation_resolved,
            "restored": False,
        }

    def recover_from(self, *, file_path):
        self.events.append("recover")
        return {
            "success": True,
            "source": str(Path(file_path)),
            "schema_version": "2.0",
            "recovered": {},
            "error": None,
        }

    def get_last_recovery_report(self):
        return None


def _coordinator(service: BehavioralRecoveryService):
    return StartupCoordinatorV2(
        state_recovery_service=service,  # type: ignore[arg-type]
    )


def test_committed_checkpoint_skips_pending_reconciliation(tmp_path) -> None:
    service = BehavioralRecoveryService(
        pending_required=False,
    )
    coordinator = _coordinator(service)

    report = coordinator.startup_from(
        file_path=tmp_path / "state.json",
    )

    assert report["success"] is True
    assert report["status"] == StartupCoordinatorV2.STATUS_RECOVERED
    assert "reconcile" not in service.events
    assert service.events.index("applicability") < service.events.index("recover")
    assert service.events.index("recover") < service.events.index("enable")


def test_pending_checkpoint_reconciles_before_recovery(tmp_path) -> None:
    service = BehavioralRecoveryService(
        pending_required=True,
        reconciliation_resolved=True,
    )
    coordinator = _coordinator(service)

    report = coordinator.startup_from(
        file_path=tmp_path / "state.json",
    )

    assert report["success"] is True
    assert service.events.index("applicability") < service.events.index("reconcile")
    assert service.events.index("reconcile") < service.events.index("recover")
    assert service.events.index("recover") < service.events.index("enable")


def test_unresolved_pending_fails_before_recovery(tmp_path) -> None:
    service = BehavioralRecoveryService(
        pending_required=True,
        reconciliation_resolved=False,
    )
    coordinator = _coordinator(service)

    with pytest.raises(
        RuntimeError,
        match="did not resolve",
    ):
        coordinator.startup_from(
            file_path=tmp_path / "state.json",
        )

    assert "reconcile" in service.events
    assert "recover" not in service.events
    assert coordinator.get_status() == StartupCoordinatorV2.STATUS_FAILED


def test_unresolved_pending_never_enables_durability(tmp_path) -> None:
    service = BehavioralRecoveryService(
        pending_required=True,
        reconciliation_resolved=False,
    )
    coordinator = _coordinator(service)

    with pytest.raises(RuntimeError):
        coordinator.startup_from(
            file_path=tmp_path / "state.json",
        )

    durability = service.execution_state_store._durability

    assert durability.enabled is False
    assert durability.failed is True
    assert durability.released is True
    assert "enable" not in service.events
    assert service.events.index("reconcile") < service.events.index("fail_closed")
