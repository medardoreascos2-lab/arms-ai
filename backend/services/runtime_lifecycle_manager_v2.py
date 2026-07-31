from __future__ import annotations

from pathlib import Path

from backend.services.graceful_shutdown_service_v2 import (
    GracefulShutdownServiceV2,
)
from backend.services.startup_coordinator_v2 import (
    StartupCoordinatorV2,
)


class RuntimeLifecycleManagerV2:
    """
    Orquesta el ciclo de vida principal del runtime de ARMS AI.

    Responsabilidades:

    - coordinar un inicio limpio;
    - coordinar un inicio con recuperación;
    - impedir arranques o cierres simultáneos;
    - coordinar el apagado seguro;
    - exponer el estado global del runtime;
    - conservar los últimos reportes de inicio y apagado.

    La recuperación concreta pertenece a StartupCoordinatorV2.
    La persistencia final pertenece a GracefulShutdownServiceV2.
    """

    STATUS_IDLE = "IDLE"
    STATUS_STARTING = "STARTING"
    STATUS_RUNNING = "RUNNING"
    STATUS_STOPPING = "STOPPING"
    STATUS_STOPPED = "STOPPED"
    STATUS_FAILED = "FAILED"

    def __init__(
        self,
        *,
        startup_coordinator: StartupCoordinatorV2,
        graceful_shutdown_service: (
            GracefulShutdownServiceV2
        ),
    ) -> None:
        self.startup_coordinator = startup_coordinator
        self.graceful_shutdown_service = (
            graceful_shutdown_service
        )

        self._status = self.STATUS_IDLE

        self._last_startup_report: (
            dict[str, object] | None
        ) = None

        self._last_shutdown_report: (
            dict[str, object] | None
        ) = None

    def get_status(
        self,
    ) -> str:
        return self._status

    def get_last_startup_report(
        self,
    ) -> dict[str, object] | None:
        if self._last_startup_report is None:
            return None

        return dict(
            self._last_startup_report
        )

    def get_last_shutdown_report(
        self,
    ) -> dict[str, object] | None:
        if self._last_shutdown_report is None:
            return None

        return dict(
            self._last_shutdown_report
        )

    def _ensure_can_start(
        self,
    ) -> None:
        if self._status == self.STATUS_STARTING:
            raise RuntimeError(
                "El runtime ya está iniciando."
            )

        if self._status == self.STATUS_RUNNING:
            raise RuntimeError(
                "El runtime ya está en ejecución."
            )

        if self._status == self.STATUS_STOPPING:
            raise RuntimeError(
                "El runtime se está apagando."
            )

    def _ensure_can_shutdown(
        self,
    ) -> None:
        if self._status == self.STATUS_STARTING:
            raise RuntimeError(
                "No se puede apagar el runtime "
                "mientras está iniciando."
            )

        if self._status == self.STATUS_STOPPING:
            raise RuntimeError(
                "El runtime ya se está apagando."
            )

        if self._status == self.STATUS_IDLE:
            raise RuntimeError(
                "El runtime todavía no ha iniciado."
            )

        if self._status == self.STATUS_STOPPED:
            raise RuntimeError(
                "El runtime ya está detenido."
            )

    def start_clean(
        self,
    ) -> dict[str, object]:
        self._ensure_can_start()
        self._status = self.STATUS_STARTING

        try:
            startup_report = (
                self.startup_coordinator
                .startup_clean()
            )

            report: dict[str, object] = {
                "success": True,
                "mode": startup_report.get(
                    "mode",
                    "CLEAN",
                ),
                "status": self.STATUS_RUNNING,
                "startup_report": dict(
                    startup_report
                ),
                "error": None,
            }

            self._status = self.STATUS_RUNNING
            self._last_startup_report = report

            return dict(report)

        except Exception as exc:
            coordinator_report = (
                self.startup_coordinator
                .get_startup_report()
            )

            report = {
                "success": False,
                "mode": "FAILED",
                "status": self.STATUS_FAILED,
                "startup_report": (
                    dict(coordinator_report)
                    if coordinator_report is not None
                    else None
                ),
                "error": {
                    "type": type(exc).__name__,
                    "message": str(exc),
                },
            }

            self._status = self.STATUS_FAILED
            self._last_startup_report = report

            raise

    def start_from(
        self,
        *,
        file_path: str | Path,
        recover_if_available: bool = True,
    ) -> dict[str, object]:
        self._ensure_can_start()
        self._status = self.STATUS_STARTING

        try:
            startup_report = (
                self.startup_coordinator
                .startup_from(
                    file_path=file_path,
                    recover_if_available=(
                        recover_if_available
                    ),
                )
            )

            report: dict[str, object] = {
                "success": True,
                "mode": startup_report.get(
                    "mode",
                ),
                "status": self.STATUS_RUNNING,
                "startup_report": dict(
                    startup_report
                ),
                "error": None,
            }

            self._status = self.STATUS_RUNNING
            self._last_startup_report = report

            return dict(report)

        except Exception as exc:
            coordinator_report = (
                self.startup_coordinator
                .get_startup_report()
            )

            report = {
                "success": False,
                "mode": "FAILED",
                "status": self.STATUS_FAILED,
                "startup_report": (
                    dict(coordinator_report)
                    if coordinator_report is not None
                    else None
                ),
                "error": {
                    "type": type(exc).__name__,
                    "message": str(exc),
                },
            }

            self._status = self.STATUS_FAILED
            self._last_startup_report = report

            raise

    def shutdown_to(
        self,
        *,
        file_path: str | Path,
    ) -> dict[str, object]:
        self._ensure_can_shutdown()
        self._status = self.STATUS_STOPPING

        try:
            shutdown_report = (
                self.graceful_shutdown_service
                .shutdown_to(
                    file_path=file_path,
                )
            )

            report: dict[str, object] = {
                "success": True,
                "status": self.STATUS_STOPPED,
                "shutdown_report": dict(
                    shutdown_report
                ),
                "error": None,
            }

            self._status = self.STATUS_STOPPED
            self._last_shutdown_report = report

            return dict(report)

        except Exception as exc:
            service_report = (
                self.graceful_shutdown_service
                .get_last_shutdown_report()
            )

            report = {
                "success": False,
                "status": self.STATUS_FAILED,
                "shutdown_report": (
                    dict(service_report)
                    if service_report is not None
                    else None
                ),
                "error": {
                    "type": type(exc).__name__,
                    "message": str(exc),
                },
            }

            self._status = self.STATUS_FAILED
            self._last_shutdown_report = report

            raise
