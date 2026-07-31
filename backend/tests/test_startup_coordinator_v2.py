from __future__ import annotations

from pathlib import Path

import pytest

from backend.services.startup_coordinator_v2 import (
    StartupCoordinatorV2,
)


class FakeStateRecoveryService:
    def __init__(
        self,
        *,
        snapshot_available: bool = False,
    ) -> None:
        self.snapshot_available = snapshot_available
        self.has_saved_state_calls: list[Path] = []
        self.recover_from_calls: list[Path] = []

        self.has_saved_state_error: Exception | None = None
        self.recover_from_error: Exception | None = None

        self.recovery_report: dict[str, object] = {
            "success": True,
            "source": "snapshot.json",
            "schema_version": "2.0",
            "recovered": {
                "active_positions": 2,
                "active_protections": 1,
                "active_oco_groups": 1,
            },
            "error": None,
        }

        self.last_recovery_report: (
            dict[str, object] | None
        ) = None

    def has_saved_state(
        self,
        *,
        file_path: str | Path,
    ) -> bool:
        path = Path(file_path)
        self.has_saved_state_calls.append(path)

        if self.has_saved_state_error is not None:
            raise self.has_saved_state_error

        return self.snapshot_available

    def recover_from(
        self,
        *,
        file_path: str | Path,
    ) -> dict[str, object]:
        path = Path(file_path)
        self.recover_from_calls.append(path)

        if self.recover_from_error is not None:
            self.last_recovery_report = {
                "success": False,
                "source": str(path),
                "error": {
                    "type": type(
                        self.recover_from_error
                    ).__name__,
                    "message": str(
                        self.recover_from_error
                    ),
                },
            }
            raise self.recover_from_error

        report = dict(self.recovery_report)
        report["source"] = str(path)

        self.last_recovery_report = report
        return dict(report)

    def get_last_recovery_report(
        self,
    ) -> dict[str, object] | None:
        if self.last_recovery_report is None:
            return None

        return dict(self.last_recovery_report)


def build_coordinator(
    recovery_service: (
        FakeStateRecoveryService | None
    ) = None,
) -> tuple[
    StartupCoordinatorV2,
    FakeStateRecoveryService,
]:
    service = (
        recovery_service
        if recovery_service is not None
        else FakeStateRecoveryService()
    )

    coordinator = StartupCoordinatorV2(
        state_recovery_service=service,  # type: ignore[arg-type]
    )

    return coordinator, service


def test_initial_status_is_idle():
    coordinator, _ = build_coordinator()

    assert coordinator.get_status() == (
        StartupCoordinatorV2.STATUS_IDLE
    )


def test_initial_startup_report_is_none():
    coordinator, _ = build_coordinator()

    assert coordinator.get_startup_report() is None


def test_startup_clean_returns_ready_report():
    coordinator, service = build_coordinator()

    report = coordinator.startup_clean()

    assert report["success"] is True
    assert report["mode"] == "CLEAN"
    assert report["status"] == (
        StartupCoordinatorV2.STATUS_READY
    )
    assert report["snapshot_path"] is None
    assert report["snapshot_found"] is False
    assert report["recovery_attempted"] is False
    assert report["recovery_report"] is None
    assert report["error"] is None
    assert isinstance(report["started_at"], str)
    assert isinstance(report["completed_at"], str)

    assert coordinator.get_status() == (
        StartupCoordinatorV2.STATUS_READY
    )
    assert service.has_saved_state_calls == []
    assert service.recover_from_calls == []


def test_startup_clean_stores_report_as_copy():
    coordinator, _ = build_coordinator()

    returned = coordinator.startup_clean()
    stored = coordinator.get_startup_report()

    assert stored == returned
    assert stored is not returned


def test_startup_from_without_snapshot_starts_clean(
    tmp_path: Path,
):
    coordinator, service = build_coordinator()
    snapshot = tmp_path / "snapshot.json"

    report = coordinator.startup_from(
        file_path=snapshot,
    )

    assert report["success"] is True
    assert report["mode"] == "CLEAN"
    assert report["status"] == (
        StartupCoordinatorV2.STATUS_READY
    )
    assert report["snapshot_path"] == str(snapshot)
    assert report["snapshot_found"] is False
    assert report["recovery_attempted"] is False
    assert report["recovery_report"] is None

    assert coordinator.get_status() == (
        StartupCoordinatorV2.STATUS_READY
    )
    assert service.has_saved_state_calls == [
        snapshot
    ]
    assert service.recover_from_calls == []


def test_startup_from_recovers_available_snapshot(
    tmp_path: Path,
):
    recovery_service = FakeStateRecoveryService(
        snapshot_available=True,
    )
    coordinator, service = build_coordinator(
        recovery_service
    )
    snapshot = tmp_path / "snapshot.json"

    report = coordinator.startup_from(
        file_path=snapshot,
    )

    assert report["success"] is True
    assert report["mode"] == "RECOVERY"
    assert report["status"] == (
        StartupCoordinatorV2.STATUS_RECOVERED
    )
    assert report["snapshot_path"] == str(snapshot)
    assert report["snapshot_found"] is True
    assert report["recovery_attempted"] is True
    assert report["error"] is None

    recovery_report = report["recovery_report"]

    assert isinstance(recovery_report, dict)
    assert recovery_report["success"] is True
    assert recovery_report["recovered"] == {
        "active_positions": 2,
        "active_protections": 1,
        "active_oco_groups": 1,
    }

    assert coordinator.get_status() == (
        StartupCoordinatorV2.STATUS_RECOVERED
    )
    assert service.has_saved_state_calls == [
        snapshot
    ]
    assert service.recover_from_calls == [
        snapshot
    ]


def test_startup_from_can_disable_recovery(
    tmp_path: Path,
):
    recovery_service = FakeStateRecoveryService(
        snapshot_available=True,
    )
    coordinator, service = build_coordinator(
        recovery_service
    )
    snapshot = tmp_path / "snapshot.json"

    report = coordinator.startup_from(
        file_path=snapshot,
        recover_if_available=False,
    )

    assert report["success"] is True
    assert report["mode"] == "CLEAN"
    assert report["status"] == (
        StartupCoordinatorV2.STATUS_READY
    )
    assert report["snapshot_found"] is True
    assert report["recovery_attempted"] is False
    assert report["recovery_report"] is None

    assert service.has_saved_state_calls == [
        snapshot
    ]
    assert service.recover_from_calls == []


def test_startup_from_records_snapshot_detection_failure(
    tmp_path: Path,
):
    recovery_service = FakeStateRecoveryService()
    recovery_service.has_saved_state_error = (
        RuntimeError("snapshot check failed")
    )

    coordinator, _ = build_coordinator(
        recovery_service
    )
    snapshot = tmp_path / "snapshot.json"

    with pytest.raises(
        RuntimeError,
        match="snapshot check failed",
    ):
        coordinator.startup_from(
            file_path=snapshot,
        )

    report = coordinator.get_startup_report()

    assert report is not None
    assert report["success"] is False
    assert report["mode"] == "FAILED"
    assert report["status"] == (
        StartupCoordinatorV2.STATUS_FAILED
    )
    assert report["snapshot_path"] == str(snapshot)
    assert report["snapshot_found"] is None
    assert report["recovery_attempted"] is True
    assert report["recovery_report"] is None
    assert report["error"] == {
        "type": "RuntimeError",
        "message": "snapshot check failed",
    }

    assert coordinator.get_status() == (
        StartupCoordinatorV2.STATUS_FAILED
    )


def test_startup_from_records_recovery_failure(
    tmp_path: Path,
):
    recovery_service = FakeStateRecoveryService(
        snapshot_available=True,
    )
    recovery_service.recover_from_error = (
        ValueError("invalid snapshot")
    )

    coordinator, service = build_coordinator(
        recovery_service
    )
    snapshot = tmp_path / "snapshot.json"

    with pytest.raises(
        ValueError,
        match="invalid snapshot",
    ):
        coordinator.startup_from(
            file_path=snapshot,
        )

    report = coordinator.get_startup_report()

    assert report is not None
    assert report["success"] is False
    assert report["mode"] == "FAILED"
    assert report["status"] == (
        StartupCoordinatorV2.STATUS_FAILED
    )
    assert report["snapshot_path"] == str(snapshot)
    assert report["recovery_attempted"] is True
    assert report["recovery_report"] == (
        service.get_last_recovery_report()
    )
    assert report["error"] == {
        "type": "ValueError",
        "message": "invalid snapshot",
    }

    assert coordinator.get_status() == (
        StartupCoordinatorV2.STATUS_FAILED
    )


def test_startup_report_is_returned_as_copy():
    coordinator, _ = build_coordinator()

    coordinator.startup_clean()

    first = coordinator.get_startup_report()
    second = coordinator.get_startup_report()

    assert first == second
    assert first is not second


def test_startup_can_transition_from_ready_to_recovered(
    tmp_path: Path,
):
    recovery_service = FakeStateRecoveryService(
        snapshot_available=True,
    )
    coordinator, _ = build_coordinator(
        recovery_service
    )

    clean_report = coordinator.startup_clean()

    assert clean_report["status"] == (
        StartupCoordinatorV2.STATUS_READY
    )

    recovery_report = coordinator.startup_from(
        file_path=tmp_path / "snapshot.json",
    )

    assert recovery_report["status"] == (
        StartupCoordinatorV2.STATUS_RECOVERED
    )
    assert coordinator.get_status() == (
        StartupCoordinatorV2.STATUS_RECOVERED
    )
