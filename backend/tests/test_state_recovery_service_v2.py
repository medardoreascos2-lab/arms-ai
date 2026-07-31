from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from backend.services.state_recovery_service_v2 import (
    StateRecoveryServiceV2,
)


def build_valid_state() -> dict[str, object]:
    return {
        "schema_version": "2.0",
        "captured_at": "2026-07-30T12:00:00+00:00",
        "active_positions": [
            {
                "position_id": "position-1",
                "status": "OPEN",
            },
            {
                "position_id": "position-2",
                "status": "OPEN",
            },
        ],
        "protective_registry": {
            "protections": [
                {
                    "protection_id": "protection-1",
                    "status": "ACTIVE",
                },
            ],
        },
        "oco_manager": {
            "groups": [
                {
                    "oco_group_id": "oco-1",
                    "status": "ACTIVE",
                },
            ],
        },
        "summary": {
            "active_positions": 2,
            "active_protections": 1,
            "active_oco_groups": 1,
        },
    }


class FakeExecutionStateStore:
    def __init__(
        self,
        *,
        loaded_state: dict[str, object] | None = None,
        restore_result: dict[str, object] | None = None,
    ) -> None:
        self.loaded_state = (
            loaded_state
            if loaded_state is not None
            else build_valid_state()
        )
        self.restore_result = (
            restore_result
            if restore_result is not None
            else {
                "restored_positions": 2,
                "restored_protections": 1,
                "restored_oco_groups": 1,
            }
        )

        self.load_calls: list[Path] = []
        self.validate_calls: list[dict[str, object]] = []
        self.restore_calls: list[dict[str, object]] = []

        self.load_error: Exception | None = None
        self.validate_error: Exception | None = None
        self.restore_error: Exception | None = None

    def load_from_file(
        self,
        *,
        file_path: str | Path,
    ) -> dict[str, object]:
        self.load_calls.append(
            Path(file_path)
        )

        if self.load_error is not None:
            raise self.load_error

        return dict(self.loaded_state)

    def validate_state(
        self,
        *,
        state: dict[str, object],
    ) -> dict[str, object]:
        self.validate_calls.append(
            dict(state)
        )

        if self.validate_error is not None:
            raise self.validate_error

        return dict(state)

    def restore_state(
        self,
        *,
        state: dict[str, object],
    ) -> dict[str, object]:
        self.restore_calls.append(
            dict(state)
        )

        if self.restore_error is not None:
            raise self.restore_error

        return dict(self.restore_result)


def build_service(
    store: FakeExecutionStateStore | None = None,
) -> tuple[
    StateRecoveryServiceV2,
    FakeExecutionStateStore,
]:
    state_store = (
        store
        if store is not None
        else FakeExecutionStateStore()
    )

    service = StateRecoveryServiceV2(
        execution_state_store=state_store,  # type: ignore[arg-type]
    )

    return service, state_store


def test_get_last_recovery_report_returns_none_initially():
    service, _ = build_service()

    assert service.get_last_recovery_report() is None


def test_has_saved_state_returns_true_for_non_empty_file(
    tmp_path: Path,
):
    service, _ = build_service()
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text(
        "{}",
        encoding="utf-8",
    )

    assert service.has_saved_state(
        file_path=snapshot,
    ) is True


def test_has_saved_state_returns_false_for_missing_file(
    tmp_path: Path,
):
    service, _ = build_service()

    assert service.has_saved_state(
        file_path=tmp_path / "missing.json",
    ) is False


def test_has_saved_state_returns_false_for_empty_file(
    tmp_path: Path,
):
    service, _ = build_service()
    snapshot = tmp_path / "empty.json"
    snapshot.touch()

    assert service.has_saved_state(
        file_path=snapshot,
    ) is False


def test_has_saved_state_returns_false_for_directory(
    tmp_path: Path,
):
    service, _ = build_service()

    assert service.has_saved_state(
        file_path=tmp_path,
    ) is False


def test_validate_saved_state_loads_and_validates_file(
    tmp_path: Path,
):
    service, store = build_service()
    snapshot = tmp_path / "snapshot.json"

    validated = service.validate_saved_state(
        file_path=snapshot,
    )

    assert validated["schema_version"] == "2.0"
    assert store.load_calls == [snapshot]
    assert len(store.validate_calls) == 1
    assert store.restore_calls == []


def test_validate_saved_state_propagates_validation_error(
    tmp_path: Path,
):
    store = FakeExecutionStateStore()
    store.validate_error = ValueError(
        "snapshot inválido"
    )
    service, _ = build_service(store)

    with pytest.raises(
        ValueError,
        match="snapshot inválido",
    ):
        service.validate_saved_state(
            file_path=tmp_path / "snapshot.json",
        )


def test_recover_restores_state_from_memory():
    service, store = build_service()
    state = build_valid_state()

    report = service.recover(
        state=state,
    )

    assert report["success"] is True
    assert report["source"] == "memory"
    assert report["schema_version"] == "2.0"
    assert report["captured_at"] == (
        "2026-07-30T12:00:00+00:00"
    )
    assert report["recovered"] == {
        "active_positions": 2,
        "active_protections": 1,
        "active_oco_groups": 1,
    }
    assert report["restore_result"] == {
        "restored_positions": 2,
        "restored_protections": 1,
        "restored_oco_groups": 1,
    }
    assert report["error"] is None
    assert isinstance(
        report["started_at"],
        str,
    )
    assert isinstance(
        report["completed_at"],
        str,
    )

    assert len(store.validate_calls) == 1
    assert len(store.restore_calls) == 1


def test_recover_saves_successful_last_report():
    service, _ = build_service()

    returned_report = service.recover(
        state=build_valid_state(),
    )
    stored_report = (
        service.get_last_recovery_report()
    )

    assert stored_report == returned_report
    assert stored_report is not returned_report


def test_recover_records_failure_report_and_reraises():
    store = FakeExecutionStateStore()
    store.validate_error = ValueError(
        "schema incompatible"
    )
    service, _ = build_service(store)
    state = build_valid_state()

    with pytest.raises(
        ValueError,
        match="schema incompatible",
    ):
        service.recover(
            state=state,
        )

    report = service.get_last_recovery_report()

    assert report is not None
    assert report["success"] is False
    assert report["source"] == "memory"
    assert report["schema_version"] == "2.0"
    assert report["recovered"] == {
        "active_positions": 0,
        "active_protections": 0,
        "active_oco_groups": 0,
    }
    assert report["restore_result"] is None
    assert report["error"] == {
        "type": "ValueError",
        "message": "schema incompatible",
    }


def test_recover_records_restore_failure_and_reraises():
    store = FakeExecutionStateStore()
    store.restore_error = RuntimeError(
        "restore failed"
    )
    service, _ = build_service(store)

    with pytest.raises(
        RuntimeError,
        match="restore failed",
    ):
        service.recover(
            state=build_valid_state(),
        )

    report = service.get_last_recovery_report()

    assert report is not None
    assert report["success"] is False
    assert report["error"] == {
        "type": "RuntimeError",
        "message": "restore failed",
    }


def test_recover_from_loads_validates_and_restores_file(
    tmp_path: Path,
):
    service, store = build_service()
    snapshot = tmp_path / "snapshot.json"

    report = service.recover_from(
        file_path=snapshot,
    )

    assert report["success"] is True
    assert report["source"] == str(snapshot)
    assert report["recovered"] == {
        "active_positions": 2,
        "active_protections": 1,
        "active_oco_groups": 1,
    }

    assert store.load_calls == [snapshot]
    assert len(store.validate_calls) == 1
    assert len(store.restore_calls) == 1


def test_recover_from_records_load_failure_and_reraises(
    tmp_path: Path,
):
    store = FakeExecutionStateStore()
    store.load_error = FileNotFoundError(
        "snapshot no encontrado"
    )
    service, _ = build_service(store)
    snapshot = tmp_path / "missing.json"

    with pytest.raises(
        FileNotFoundError,
        match="snapshot no encontrado",
    ):
        service.recover_from(
            file_path=snapshot,
        )

    report = service.get_last_recovery_report()

    assert report is not None
    assert report["success"] is False
    assert report["source"] == str(snapshot)
    assert report["schema_version"] is None
    assert report["captured_at"] is None
    assert report["error"] == {
        "type": "FileNotFoundError",
        "message": "snapshot no encontrado",
    }


def test_recovery_report_is_returned_as_copy():
    service, _ = build_service()

    service.recover(
        state=build_valid_state(),
    )

    first_report = (
        service.get_last_recovery_report()
    )
    second_report = (
        service.get_last_recovery_report()
    )

    assert first_report == second_report
    assert first_report is not second_report


def test_clear_saved_state_deletes_existing_file(
    tmp_path: Path,
):
    service, _ = build_service()
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text(
        json.dumps(build_valid_state()),
        encoding="utf-8",
    )

    deleted = service.clear_saved_state(
        file_path=snapshot,
    )

    assert deleted is True
    assert snapshot.exists() is False


def test_clear_saved_state_returns_false_when_missing_allowed(
    tmp_path: Path,
):
    service, _ = build_service()

    deleted = service.clear_saved_state(
        file_path=tmp_path / "missing.json",
        missing_ok=True,
    )

    assert deleted is False


def test_clear_saved_state_raises_when_missing_not_allowed(
    tmp_path: Path,
):
    service, _ = build_service()
    snapshot = tmp_path / "missing.json"

    with pytest.raises(
        FileNotFoundError,
        match="No existe el snapshot",
    ):
        service.clear_saved_state(
            file_path=snapshot,
            missing_ok=False,
        )


def test_clear_saved_state_rejects_directory(
    tmp_path: Path,
):
    service, _ = build_service()

    with pytest.raises(
        ValueError,
        match="debe ser un archivo",
    ):
        service.clear_saved_state(
            file_path=tmp_path,
        )


def test_build_counts_tolerates_missing_optional_collections():
    service, _ = build_service()

    report = service.recover(
        state={
            "schema_version": "2.0",
            "captured_at": None,
        },
    )

    assert report["recovered"] == {
        "active_positions": 0,
        "active_protections": 0,
        "active_oco_groups": 0,
    }
