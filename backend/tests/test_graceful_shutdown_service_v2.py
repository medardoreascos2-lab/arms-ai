from __future__ import annotations

from pathlib import Path

import pytest

from backend.services.graceful_shutdown_service_v2 import (
    GracefulShutdownServiceV2,
)


class FakeExecutionStateStore:
    def __init__(self) -> None:
        self.save_calls: list[Path] = []
        self.save_error: Exception | None = None
        self.save_report: dict[str, object] = {
            "saved": True,
            "file_path": "snapshot.json",
            "schema_version": "2.0",
            "bytes_written": 512,
            "summary": {
                "active_positions": 2,
                "active_protections": 1,
                "active_oco_groups": 1,
            },
        }

    def save_to_file(
        self,
        *,
        file_path: str | Path,
    ) -> dict[str, object]:
        path = Path(file_path)
        self.save_calls.append(path)

        if self.save_error is not None:
            raise self.save_error

        report = dict(self.save_report)
        report["file_path"] = str(path)

        return report


def build_service(
    *,
    state_store: FakeExecutionStateStore | None = None,
    block_new_operations=None,
) -> tuple[
    GracefulShutdownServiceV2,
    FakeExecutionStateStore,
]:
    store = (
        state_store
        if state_store is not None
        else FakeExecutionStateStore()
    )

    service = GracefulShutdownServiceV2(
        execution_state_store=store,  # type: ignore[arg-type]
        block_new_operations=block_new_operations,
    )

    return service, store


def test_initial_status_is_running():
    service, _ = build_service()

    assert service.get_status() == (
        GracefulShutdownServiceV2.STATUS_RUNNING
    )


def test_initial_shutdown_report_is_none():
    service, _ = build_service()

    assert service.get_last_shutdown_report() is None


def test_shutdown_to_saves_snapshot_successfully(
    tmp_path: Path,
):
    service, store = build_service()
    snapshot = tmp_path / "state" / "snapshot.json"

    report = service.shutdown_to(
        file_path=snapshot,
    )

    assert report["success"] is True
    assert report["status"] == (
        GracefulShutdownServiceV2.STATUS_STOPPED
    )
    assert report["snapshot_path"] == str(snapshot)
    assert report["operations_blocked"] is False
    assert report["block_result"] is None
    assert report["error"] is None

    save_report = report["save_report"]

    assert isinstance(save_report, dict)
    assert save_report["saved"] is True
    assert save_report["file_path"] == str(snapshot)
    assert save_report["schema_version"] == "2.0"

    assert store.save_calls == [snapshot]
    assert service.get_status() == (
        GracefulShutdownServiceV2.STATUS_STOPPED
    )


def test_shutdown_executes_block_callback_before_save(
    tmp_path: Path,
):
    events: list[str] = []

    class OrderedStateStore(FakeExecutionStateStore):
        def save_to_file(
            self,
            *,
            file_path: str | Path,
        ) -> dict[str, object]:
            events.append("save")
            return super().save_to_file(
                file_path=file_path,
            )

    store = OrderedStateStore()

    def block_operations():
        events.append("block")
        return {
            "blocked": True,
            "reason": "shutdown",
        }

    service, _ = build_service(
        state_store=store,
        block_new_operations=block_operations,
    )
    snapshot = tmp_path / "snapshot.json"

    report = service.shutdown_to(
        file_path=snapshot,
    )

    assert events == ["block", "save"]
    assert report["operations_blocked"] is True
    assert report["block_result"] == {
        "blocked": True,
        "reason": "shutdown",
    }


def test_shutdown_records_save_failure(
    tmp_path: Path,
):
    store = FakeExecutionStateStore()
    store.save_error = OSError(
        "snapshot write failed"
    )

    service, _ = build_service(
        state_store=store,
    )
    snapshot = tmp_path / "snapshot.json"

    with pytest.raises(
        OSError,
        match="snapshot write failed",
    ):
        service.shutdown_to(
            file_path=snapshot,
        )

    report = service.get_last_shutdown_report()

    assert report is not None
    assert report["success"] is False
    assert report["status"] == (
        GracefulShutdownServiceV2.STATUS_FAILED
    )
    assert report["snapshot_path"] == str(snapshot)
    assert report["operations_blocked"] is False
    assert report["save_report"] is None
    assert report["error"] == {
        "type": "OSError",
        "message": "snapshot write failed",
    }

    assert service.get_status() == (
        GracefulShutdownServiceV2.STATUS_FAILED
    )


def test_shutdown_records_block_callback_failure(
    tmp_path: Path,
):
    def failing_block():
        raise RuntimeError(
            "unable to block operations"
        )

    service, store = build_service(
        block_new_operations=failing_block,
    )
    snapshot = tmp_path / "snapshot.json"

    with pytest.raises(
        RuntimeError,
        match="unable to block operations",
    ):
        service.shutdown_to(
            file_path=snapshot,
        )

    report = service.get_last_shutdown_report()

    assert report is not None
    assert report["success"] is False
    assert report["status"] == (
        GracefulShutdownServiceV2.STATUS_FAILED
    )
    assert report["operations_blocked"] is False
    assert report["block_result"] is None
    assert report["save_report"] is None
    assert report["error"] == {
        "type": "RuntimeError",
        "message": "unable to block operations",
    }

    assert store.save_calls == []
    assert service.get_status() == (
        GracefulShutdownServiceV2.STATUS_FAILED
    )


def test_save_failure_preserves_successful_block_result(
    tmp_path: Path,
):
    store = FakeExecutionStateStore()
    store.save_error = OSError(
        "disk unavailable"
    )

    def block_operations():
        return "TRADING_BLOCKED"

    service, _ = build_service(
        state_store=store,
        block_new_operations=block_operations,
    )
    snapshot = tmp_path / "snapshot.json"

    with pytest.raises(
        OSError,
        match="disk unavailable",
    ):
        service.shutdown_to(
            file_path=snapshot,
        )

    report = service.get_last_shutdown_report()

    assert report is not None
    assert report["operations_blocked"] is True
    assert report["block_result"] == (
        "TRADING_BLOCKED"
    )
    assert report["error"] == {
        "type": "OSError",
        "message": "disk unavailable",
    }


def test_empty_string_path_is_rejected():
    service, store = build_service()

    with pytest.raises(
        ValueError,
        match="file_path es obligatorio",
    ):
        service.shutdown_to(
            file_path="   ",
        )

    assert service.get_status() == (
        GracefulShutdownServiceV2.STATUS_RUNNING
    )
    assert service.get_last_shutdown_report() is None
    assert store.save_calls == []


def test_directory_path_is_rejected(
    tmp_path: Path,
):
    service, store = build_service()

    with pytest.raises(
        IsADirectoryError,
        match="directorio",
    ):
        service.shutdown_to(
            file_path=tmp_path,
        )

    assert service.get_status() == (
        GracefulShutdownServiceV2.STATUS_RUNNING
    )
    assert service.get_last_shutdown_report() is None
    assert store.save_calls == []


def test_shutdown_report_is_returned_as_copy(
    tmp_path: Path,
):
    service, _ = build_service()

    returned = service.shutdown_to(
        file_path=tmp_path / "snapshot.json",
    )
    stored = service.get_last_shutdown_report()

    assert stored == returned
    assert stored is not returned

    assert stored is not None
    stored["success"] = False

    fresh = service.get_last_shutdown_report()

    assert fresh is not None
    assert fresh["success"] is True


def test_shutdown_rejects_concurrent_attempt(
    tmp_path: Path,
):
    service, store = build_service()

    service._status = (  # noqa: SLF001
        GracefulShutdownServiceV2.STATUS_STOPPING
    )

    with pytest.raises(
        RuntimeError,
        match="apagado ya está en progreso",
    ):
        service.shutdown_to(
            file_path=tmp_path / "snapshot.json",
        )

    assert store.save_calls == []
    assert service.get_status() == (
        GracefulShutdownServiceV2.STATUS_STOPPING
    )


def test_service_can_retry_after_failure(
    tmp_path: Path,
):
    store = FakeExecutionStateStore()
    store.save_error = OSError(
        "temporary failure"
    )

    service, _ = build_service(
        state_store=store,
    )
    snapshot = tmp_path / "snapshot.json"

    with pytest.raises(
        OSError,
        match="temporary failure",
    ):
        service.shutdown_to(
            file_path=snapshot,
        )

    assert service.get_status() == (
        GracefulShutdownServiceV2.STATUS_FAILED
    )

    store.save_error = None

    report = service.shutdown_to(
        file_path=snapshot,
    )

    assert report["success"] is True
    assert report["status"] == (
        GracefulShutdownServiceV2.STATUS_STOPPED
    )
    assert service.get_status() == (
        GracefulShutdownServiceV2.STATUS_STOPPED
    )
    assert store.save_calls == [
        snapshot,
        snapshot,
    ]
