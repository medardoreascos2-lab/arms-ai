from pathlib import Path

import pytest

from backend.services.runtime_lifecycle_manager_v2 import (
    RuntimeLifecycleManagerV2,
)


class FakeStartupCoordinator:
    def __init__(self) -> None:
        self.clean_calls = 0
        self.from_calls: list[dict[str, object]] = []
        self.clean_error: Exception | None = None
        self.from_error: Exception | None = None
        self.last_report: dict[str, object] | None = None

    def startup_clean(
        self,
    ) -> dict[str, object]:
        self.clean_calls += 1

        if self.clean_error is not None:
            self.last_report = {
                "success": False,
                "mode": "FAILED",
            }
            raise self.clean_error

        self.last_report = {
            "success": True,
            "mode": "CLEAN",
            "status": "READY",
        }

        return dict(self.last_report)

    def startup_from(
        self,
        *,
        file_path,
        recover_if_available=True,
    ) -> dict[str, object]:
        self.from_calls.append(
            {
                "file_path": file_path,
                "recover_if_available": (
                    recover_if_available
                ),
            }
        )

        if self.from_error is not None:
            self.last_report = {
                "success": False,
                "mode": "FAILED",
            }
            raise self.from_error

        self.last_report = {
            "success": True,
            "mode": "RECOVERY",
            "status": "RECOVERED",
        }

        return dict(self.last_report)

    def get_startup_report(
        self,
    ) -> dict[str, object] | None:
        if self.last_report is None:
            return None

        return dict(self.last_report)


class FakeGracefulShutdownService:
    def __init__(self) -> None:
        self.calls: list[object] = []
        self.error: Exception | None = None
        self.last_report: dict[str, object] | None = None

    def shutdown_to(
        self,
        *,
        file_path,
    ) -> dict[str, object]:
        self.calls.append(file_path)

        if self.error is not None:
            self.last_report = {
                "success": False,
                "status": "FAILED",
            }
            raise self.error

        self.last_report = {
            "success": True,
            "status": "STOPPED",
            "snapshot_path": str(file_path),
        }

        return dict(self.last_report)

    def get_last_shutdown_report(
        self,
    ) -> dict[str, object] | None:
        if self.last_report is None:
            return None

        return dict(self.last_report)


def build_manager():
    startup = FakeStartupCoordinator()
    shutdown = FakeGracefulShutdownService()

    manager = RuntimeLifecycleManagerV2(
        startup_coordinator=startup,
        graceful_shutdown_service=shutdown,
    )

    return manager, startup, shutdown


def test_initial_status_is_idle():
    manager, _, _ = build_manager()

    assert (
        manager.get_status()
        == RuntimeLifecycleManagerV2.STATUS_IDLE
    )


def test_initial_reports_are_none():
    manager, _, _ = build_manager()

    assert manager.get_last_startup_report() is None
    assert manager.get_last_shutdown_report() is None


def test_start_clean_transitions_runtime_to_running():
    manager, startup, _ = build_manager()

    report = manager.start_clean()

    assert startup.clean_calls == 1
    assert report["success"] is True
    assert report["mode"] == "CLEAN"
    assert report["status"] == "RUNNING"

    assert (
        manager.get_status()
        == RuntimeLifecycleManagerV2.STATUS_RUNNING
    )


def test_start_from_delegates_recovery_arguments(
    tmp_path: Path,
):
    manager, startup, _ = build_manager()
    snapshot = tmp_path / "runtime.json"

    report = manager.start_from(
        file_path=snapshot,
        recover_if_available=False,
    )

    assert startup.from_calls == [
        {
            "file_path": snapshot,
            "recover_if_available": False,
        }
    ]

    assert report["success"] is True
    assert report["mode"] == "RECOVERY"

    assert (
        manager.get_status()
        == RuntimeLifecycleManagerV2.STATUS_RUNNING
    )


def test_runtime_rejects_second_start():
    manager, _, _ = build_manager()

    manager.start_clean()

    with pytest.raises(
        RuntimeError,
        match="ya está en ejecución",
    ):
        manager.start_clean()


def test_runtime_rejects_start_while_starting():
    manager, _, _ = build_manager()

    manager._status = (
        RuntimeLifecycleManagerV2.STATUS_STARTING
    )

    with pytest.raises(
        RuntimeError,
        match="ya está iniciando",
    ):
        manager.start_clean()


def test_start_failure_is_recorded():
    manager, startup, _ = build_manager()

    startup.clean_error = RuntimeError(
        "startup failed"
    )

    with pytest.raises(
        RuntimeError,
        match="startup failed",
    ):
        manager.start_clean()

    assert (
        manager.get_status()
        == RuntimeLifecycleManagerV2.STATUS_FAILED
    )

    report = manager.get_last_startup_report()

    assert report is not None
    assert report["success"] is False
    assert report["status"] == "FAILED"
    assert report["error"] == {
        "type": "RuntimeError",
        "message": "startup failed",
    }


def test_shutdown_saves_state_and_stops_runtime(
    tmp_path: Path,
):
    manager, _, shutdown = build_manager()
    snapshot = tmp_path / "shutdown.json"

    manager.start_clean()

    report = manager.shutdown_to(
        file_path=snapshot,
    )

    assert shutdown.calls == [snapshot]
    assert report["success"] is True
    assert report["status"] == "STOPPED"

    assert (
        manager.get_status()
        == RuntimeLifecycleManagerV2.STATUS_STOPPED
    )


def test_shutdown_rejects_idle_runtime(
    tmp_path: Path,
):
    manager, _, _ = build_manager()

    with pytest.raises(
        RuntimeError,
        match="todavía no ha iniciado",
    ):
        manager.shutdown_to(
            file_path=tmp_path / "state.json",
        )


def test_shutdown_rejects_second_attempt(
    tmp_path: Path,
):
    manager, _, _ = build_manager()
    snapshot = tmp_path / "state.json"

    manager.start_clean()
    manager.shutdown_to(
        file_path=snapshot,
    )

    with pytest.raises(
        RuntimeError,
        match="ya está detenido",
    ):
        manager.shutdown_to(
            file_path=snapshot,
        )


def test_shutdown_failure_is_recorded(
    tmp_path: Path,
):
    manager, _, shutdown = build_manager()

    shutdown.error = OSError(
        "disk unavailable"
    )

    manager.start_clean()

    with pytest.raises(
        OSError,
        match="disk unavailable",
    ):
        manager.shutdown_to(
            file_path=tmp_path / "state.json",
        )

    assert (
        manager.get_status()
        == RuntimeLifecycleManagerV2.STATUS_FAILED
    )

    report = manager.get_last_shutdown_report()

    assert report is not None
    assert report["success"] is False
    assert report["status"] == "FAILED"
    assert report["error"] == {
        "type": "OSError",
        "message": "disk unavailable",
    }


def test_startup_report_is_returned_as_copy():
    manager, _, _ = build_manager()

    manager.start_clean()

    first = manager.get_last_startup_report()
    assert first is not None

    first["status"] = "MODIFIED"

    second = manager.get_last_startup_report()

    assert second is not None
    assert second["status"] == "RUNNING"


def test_shutdown_report_is_returned_as_copy(
    tmp_path: Path,
):
    manager, _, _ = build_manager()

    manager.start_clean()
    manager.shutdown_to(
        file_path=tmp_path / "state.json",
    )

    first = manager.get_last_shutdown_report()
    assert first is not None

    first["status"] = "MODIFIED"

    second = manager.get_last_shutdown_report()

    assert second is not None
    assert second["status"] == "STOPPED"


def test_runtime_can_restart_after_stopped_state(
    tmp_path: Path,
):
    manager, startup, _ = build_manager()

    manager.start_clean()
    manager.shutdown_to(
        file_path=tmp_path / "state.json",
    )

    report = manager.start_clean()

    assert startup.clean_calls == 2
    assert report["status"] == "RUNNING"

    assert (
        manager.get_status()
        == RuntimeLifecycleManagerV2.STATUS_RUNNING
    )


def test_runtime_can_retry_start_after_failure():
    manager, startup, _ = build_manager()

    startup.clean_error = RuntimeError(
        "temporary startup failure"
    )

    with pytest.raises(RuntimeError):
        manager.start_clean()

    startup.clean_error = None

    report = manager.start_clean()

    assert report["success"] is True
    assert report["status"] == "RUNNING"


def test_runtime_can_retry_shutdown_after_failure(
    tmp_path: Path,
):
    manager, _, shutdown = build_manager()
    snapshot = tmp_path / "state.json"

    manager.start_clean()

    shutdown.error = OSError(
        "temporary save failure"
    )

    with pytest.raises(OSError):
        manager.shutdown_to(
            file_path=snapshot,
        )

    shutdown.error = None

    report = manager.shutdown_to(
        file_path=snapshot,
    )

    assert report["success"] is True
    assert report["status"] == "STOPPED"
