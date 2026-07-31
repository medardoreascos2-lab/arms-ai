from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.services.execution_state_store_v2 import (
    ExecutionStateStoreV2,
)


class StateRecoveryServiceV2:
    """
    Orquesta la validación y recuperación del estado
    persistido del motor de ejecución.

    La lectura, validación y restauración concreta son
    responsabilidad de ExecutionStateStoreV2.
    """

    def __init__(
        self,
        *,
        execution_state_store: ExecutionStateStoreV2,
    ) -> None:
        self.execution_state_store = execution_state_store
        self._last_recovery_report: (
            dict[str, object] | None
        ) = None

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(
            timezone.utc
        ).isoformat()

    @staticmethod
    def _normalize_path(
        file_path: str | Path,
    ) -> Path:
        path = Path(file_path).expanduser()

        if not str(path).strip():
            raise ValueError(
                "file_path es obligatorio."
            )

        return path

    @staticmethod
    def _build_counts(
        state: dict[str, object],
    ) -> dict[str, int]:
        active_positions = state.get(
            "active_positions",
            [],
        )

        protective_registry = state.get(
            "protective_registry",
            {},
        )

        oco_manager = state.get(
            "oco_manager",
            {},
        )

        if not isinstance(
            active_positions,
            list,
        ):
            active_positions = []

        if not isinstance(
            protective_registry,
            dict,
        ):
            protective_registry = {}

        if not isinstance(
            oco_manager,
            dict,
        ):
            oco_manager = {}

        protections = protective_registry.get(
            "protections",
            [],
        )

        groups = oco_manager.get(
            "groups",
            [],
        )

        if not isinstance(protections, list):
            protections = []

        if not isinstance(groups, list):
            groups = []

        return {
            "active_positions": len(
                active_positions
            ),
            "active_protections": len(
                protections
            ),
            "active_oco_groups": len(
                groups
            ),
        }

    def has_saved_state(
        self,
        *,
        file_path: str | Path,
    ) -> bool:
        path = self._normalize_path(
            file_path
        )

        return (
            path.exists()
            and path.is_file()
            and path.stat().st_size > 0
        )

    def validate_saved_state(
        self,
        *,
        file_path: str | Path,
    ) -> dict[str, object]:
        path = self._normalize_path(
            file_path
        )

        state = (
            self.execution_state_store
            .load_from_file(
                file_path=path,
            )
        )

        return (
            self.execution_state_store
            .validate_state(
                state=state,
            )
        )

    def recover(
        self,
        *,
        state: dict[str, object],
    ) -> dict[str, object]:
        started_at = self._utc_now()

        try:
            validated_state = (
                self.execution_state_store
                .validate_state(
                    state=state,
                )
            )

            restore_result = (
                self.execution_state_store
                .restore_state(
                    state=validated_state,
                )
            )

            report: dict[str, object] = {
                "success": True,
                "source": "memory",
                "started_at": started_at,
                "completed_at": self._utc_now(),
                "schema_version": (
                    validated_state.get(
                        "schema_version"
                    )
                ),
                "captured_at": (
                    validated_state.get(
                        "captured_at"
                    )
                ),
                "recovered": self._build_counts(
                    validated_state
                ),
                "restore_result": (
                    dict(restore_result)
                    if isinstance(
                        restore_result,
                        dict,
                    )
                    else restore_result
                ),
                "error": None,
            }

            self._last_recovery_report = report
            return dict(report)

        except Exception as exc:
            report = {
                "success": False,
                "source": "memory",
                "started_at": started_at,
                "completed_at": self._utc_now(),
                "schema_version": (
                    state.get("schema_version")
                    if isinstance(state, dict)
                    else None
                ),
                "captured_at": (
                    state.get("captured_at")
                    if isinstance(state, dict)
                    else None
                ),
                "recovered": {
                    "active_positions": 0,
                    "active_protections": 0,
                    "active_oco_groups": 0,
                },
                "restore_result": None,
                "error": {
                    "type": type(exc).__name__,
                    "message": str(exc),
                },
            }

            self._last_recovery_report = report
            raise

    def recover_from(
        self,
        *,
        file_path: str | Path,
    ) -> dict[str, object]:
        path = self._normalize_path(
            file_path
        )
        started_at = self._utc_now()

        try:
            state = (
                self.execution_state_store
                .load_from_file(
                    file_path=path,
                )
            )

            validated_state = (
                self.execution_state_store
                .validate_state(
                    state=state,
                )
            )

            restore_result = (
                self.execution_state_store
                .restore_state(
                    state=validated_state,
                )
            )

            report: dict[str, object] = {
                "success": True,
                "source": str(path),
                "started_at": started_at,
                "completed_at": self._utc_now(),
                "schema_version": (
                    validated_state.get(
                        "schema_version"
                    )
                ),
                "captured_at": (
                    validated_state.get(
                        "captured_at"
                    )
                ),
                "recovered": self._build_counts(
                    validated_state
                ),
                "restore_result": (
                    dict(restore_result)
                    if isinstance(
                        restore_result,
                        dict,
                    )
                    else restore_result
                ),
                "error": None,
            }

            self._last_recovery_report = report
            return dict(report)

        except Exception as exc:
            report = {
                "success": False,
                "source": str(path),
                "started_at": started_at,
                "completed_at": self._utc_now(),
                "schema_version": None,
                "captured_at": None,
                "recovered": {
                    "active_positions": 0,
                    "active_protections": 0,
                    "active_oco_groups": 0,
                },
                "restore_result": None,
                "error": {
                    "type": type(exc).__name__,
                    "message": str(exc),
                },
            }

            self._last_recovery_report = report
            raise

    def get_last_recovery_report(
        self,
    ) -> dict[str, object] | None:
        if self._last_recovery_report is None:
            return None

        return dict(
            self._last_recovery_report
        )

    def clear_saved_state(
        self,
        *,
        file_path: str | Path,
        missing_ok: bool = True,
    ) -> bool:
        path = self._normalize_path(
            file_path
        )

        if not path.exists():
            if missing_ok:
                return False

            raise FileNotFoundError(
                f"No existe el snapshot: {path}"
            )

        if not path.is_file():
            raise ValueError(
                "El snapshot debe ser un archivo."
            )

        path.unlink()
        return True
