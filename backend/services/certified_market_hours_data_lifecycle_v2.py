from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from backend.services.certified_market_hours_runtime_provider_v2 import (
    CertifiedMarketHoursRuntimeProviderV2,
)
from backend.services.certified_market_hours_snapshot_loader_v2 import (
    CertifiedMarketHoursSnapshotLoaderV2,
)


class CertifiedMarketHoursDataLifecycleV2:
    """
    Validates and activates certified market-hours snapshots.

    Activation is fail-safe:
    a candidate snapshot is fully loaded and validated before
    it can replace the currently active runtime provider.
    """

    STATUS_EMPTY = "EMPTY"
    STATUS_READY = "READY"
    STATUS_FAILED = "FAILED"

    def __init__(
        self,
        *,
        loader: CertifiedMarketHoursSnapshotLoaderV2 | None = None,
    ) -> None:
        self.loader = (
            loader
            if loader is not None
            else CertifiedMarketHoursSnapshotLoaderV2()
        )

        if not isinstance(
            self.loader,
            CertifiedMarketHoursSnapshotLoaderV2,
        ):
            raise TypeError(
                "loader debe ser "
                "CertifiedMarketHoursSnapshotLoaderV2."
            )

        self._status = self.STATUS_EMPTY
        self._active_provider: (
            CertifiedMarketHoursRuntimeProviderV2 | None
        ) = None
        self._active_path: Path | None = None
        self._last_activation_report: (
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
        elif not isinstance(file_path, Path):
            raise TypeError(
                "file_path debe ser str o Path."
            )

        path = Path(file_path).expanduser()

        if path.exists() and path.is_dir():
            raise IsADirectoryError(
                f"La ruta certificada es un directorio: {path}"
            )

        return path

    def get_status(self) -> str:
        return self._status

    def get_active_provider(
        self,
    ) -> CertifiedMarketHoursRuntimeProviderV2 | None:
        return self._active_provider

    def get_active_path(self) -> Path | None:
        return self._active_path

    def get_last_activation_report(
        self,
    ) -> dict[str, object] | None:
        if self._last_activation_report is None:
            return None

        return dict(
            self._last_activation_report
        )

    def activate_from_file(
        self,
        *,
        file_path: str | Path,
    ) -> dict[str, object]:
        path = self._normalize_path(
            file_path
        )
        started_at = self._utc_now()

        previous_provider = self._active_provider
        previous_path = self._active_path
        previous_status = self._status

        try:
            (
                calendar_snapshot,
                special_hours_snapshot,
            ) = self.loader.load_from_file(
                file_path=path,
            )

            candidate_provider = (
                CertifiedMarketHoursRuntimeProviderV2(
                    calendar_snapshot=calendar_snapshot,
                    special_hours_snapshot=(
                        special_hours_snapshot
                    ),
                )
            )

            report: dict[str, object] = {
                "success": True,
                "status": self.STATUS_READY,
                "started_at": started_at,
                "completed_at": self._utc_now(),
                "source": str(path),
                "covered_dates": len(
                    calendar_snapshot.covered_dates
                ),
                "closed_dates": len(
                    calendar_snapshot.closed_dates
                ),
                "special_hours": len(
                    special_hours_snapshot.windows
                ),
                "error": None,
            }

            self._active_provider = candidate_provider
            self._active_path = path
            self._status = self.STATUS_READY
            self._last_activation_report = report

            return dict(report)

        except Exception as exc:
            self._active_provider = previous_provider
            self._active_path = previous_path
            self._status = previous_status

            report = {
                "success": False,
                "status": self.STATUS_FAILED,
                "started_at": started_at,
                "completed_at": self._utc_now(),
                "source": str(path),
                "covered_dates": None,
                "closed_dates": None,
                "special_hours": None,
                "error": {
                    "type": type(exc).__name__,
                    "message": str(exc),
                },
            }

            self._last_activation_report = report
            raise
