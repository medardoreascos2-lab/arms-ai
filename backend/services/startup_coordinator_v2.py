from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from backend.services.state_recovery_service_v2 import (
    StateRecoveryServiceV2,
)


class StartupCoordinatorV2:
    """
    Coordina el arranque del motor de ejecución.

    Decide entre:

    - inicio limpio;
    - recuperación desde snapshot;
    - arranque fallido.

    La restauración concreta del estado corresponde a
    StateRecoveryServiceV2.
    """

    STATUS_IDLE = "IDLE"
    STATUS_STARTING = "STARTING"
    STATUS_READY = "READY"
    STATUS_RECOVERED = "RECOVERED"
    STATUS_FAILED = "FAILED"

    def __init__(
        self,
        *,
        state_recovery_service: StateRecoveryServiceV2,
    ) -> None:
        self.state_recovery_service = (
            state_recovery_service
        )
        self._status = self.STATUS_IDLE
        self._last_startup_report: (
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

    def get_status(
        self,
    ) -> str:
        return self._status

    def get_startup_report(
        self,
    ) -> dict[str, object] | None:
        if self._last_startup_report is None:
            return None

        return dict(
            self._last_startup_report
        )

    def startup_clean(
        self,
    ) -> dict[str, object]:
        started_at = self._utc_now()
        self._status = self.STATUS_STARTING

        report: dict[str, object] = {
            "success": True,
            "mode": "CLEAN",
            "status": self.STATUS_READY,
            "started_at": started_at,
            "completed_at": self._utc_now(),
            "snapshot_path": None,
            "snapshot_found": False,
            "recovery_attempted": False,
            "recovery_report": None,
            "error": None,
        }

        self._status = self.STATUS_READY
        self._last_startup_report = report

        return dict(report)

    def startup_from(
        self,
        *,
        file_path: str | Path,
        recover_if_available: bool = True,
    ) -> dict[str, object]:
        path = self._normalize_path(
            file_path
        )
        started_at = self._utc_now()

        self._status = self.STATUS_STARTING

        try:
            snapshot_found = (
                self.state_recovery_service
                .has_saved_state(
                    file_path=path,
                )
            )

            if (
                not snapshot_found
                or not recover_if_available
            ):
                report: dict[str, object] = {
                    "success": True,
                    "mode": "CLEAN",
                    "status": self.STATUS_READY,
                    "started_at": started_at,
                    "completed_at": self._utc_now(),
                    "snapshot_path": str(path),
                    "snapshot_found": snapshot_found,
                    "recovery_attempted": False,
                    "recovery_report": None,
                    "error": None,
                }

                self._status = self.STATUS_READY
                self._last_startup_report = report

                return dict(report)

            recovery_report = (
                self.state_recovery_service
                .recover_from(
                    file_path=path,
                )
            )

            report = {
                "success": True,
                "mode": "RECOVERY",
                "status": self.STATUS_RECOVERED,
                "started_at": started_at,
                "completed_at": self._utc_now(),
                "snapshot_path": str(path),
                "snapshot_found": True,
                "recovery_attempted": True,
                "recovery_report": dict(
                    recovery_report
                ),
                "error": None,
            }

            self._status = self.STATUS_RECOVERED
            self._last_startup_report = report

            return dict(report)

        except Exception as exc:
            report = {
                "success": False,
                "mode": "FAILED",
                "status": self.STATUS_FAILED,
                "started_at": started_at,
                "completed_at": self._utc_now(),
                "snapshot_path": str(path),
                "snapshot_found": None,
                "recovery_attempted": True,
                "recovery_report": (
                    self.state_recovery_service
                    .get_last_recovery_report()
                ),
                "error": {
                    "type": type(exc).__name__,
                    "message": str(exc),
                },
            }

            self._status = self.STATUS_FAILED
            self._last_startup_report = report

            raise
