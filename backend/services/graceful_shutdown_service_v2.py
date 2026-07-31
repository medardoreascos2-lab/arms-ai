from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from backend.services.execution_state_store_v2 import (
    ExecutionStateStoreV2,
)


class GracefulShutdownServiceV2:
    """
    Coordina el cierre seguro del motor de ejecución.

    Responsabilidades:

    - impedir cierres simultáneos;
    - bloquear nuevas operaciones cuando exista un callback;
    - guardar el snapshot final mediante ExecutionStateStoreV2;
    - generar y conservar un reporte del apagado;
    - registrar fallos sin ocultar la excepción original.
    """

    STATUS_RUNNING = "RUNNING"
    STATUS_STOPPING = "STOPPING"
    STATUS_STOPPED = "STOPPED"
    STATUS_FAILED = "FAILED"

    def __init__(
        self,
        *,
        execution_state_store: ExecutionStateStoreV2,
        block_new_operations: (
            Callable[[], object] | None
        ) = None,
    ) -> None:
        self.execution_state_store = (
            execution_state_store
        )
        self.block_new_operations = (
            block_new_operations
        )

        self._status = self.STATUS_RUNNING
        self._last_shutdown_report: (
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
        if isinstance(file_path, str):
            if not file_path.strip():
                raise ValueError(
                    "file_path es obligatorio."
                )

        path = Path(file_path).expanduser()

        if path.exists() and path.is_dir():
            raise IsADirectoryError(
                f"La ruta del snapshot es un "
                f"directorio: {path}"
            )

        return path

    def get_status(
        self,
    ) -> str:
        return self._status

    def get_last_shutdown_report(
        self,
    ) -> dict[str, object] | None:
        if self._last_shutdown_report is None:
            return None

        return dict(
            self._last_shutdown_report
        )

    def shutdown_to(
        self,
        *,
        file_path: str | Path,
    ) -> dict[str, object]:
        if self._status == self.STATUS_STOPPING:
            raise RuntimeError(
                "El apagado ya está en progreso."
            )

        path = self._normalize_path(
            file_path
        )
        started_at = self._utc_now()

        self._status = self.STATUS_STOPPING

        operations_blocked = False
        block_result: object | None = None

        try:
            if self.block_new_operations is not None:
                block_result = (
                    self.block_new_operations()
                )
                operations_blocked = True

            save_report = (
                self.execution_state_store
                .save_to_file(
                    file_path=path,
                )
            )

            report: dict[str, object] = {
                "success": True,
                "status": self.STATUS_STOPPED,
                "started_at": started_at,
                "completed_at": self._utc_now(),
                "snapshot_path": str(path),
                "operations_blocked": (
                    operations_blocked
                ),
                "block_result": block_result,
                "save_report": dict(
                    save_report
                ),
                "error": None,
            }

            self._status = self.STATUS_STOPPED
            self._last_shutdown_report = report

            return dict(report)

        except Exception as exc:
            report = {
                "success": False,
                "status": self.STATUS_FAILED,
                "started_at": started_at,
                "completed_at": self._utc_now(),
                "snapshot_path": str(path),
                "operations_blocked": (
                    operations_blocked
                ),
                "block_result": block_result,
                "save_report": None,
                "error": {
                    "type": type(exc).__name__,
                    "message": str(exc),
                },
            }

            self._status = self.STATUS_FAILED
            self._last_shutdown_report = report

            raise
