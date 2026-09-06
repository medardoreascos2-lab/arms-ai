from __future__ import annotations

from datetime import datetime
from datetime import timezone
from pathlib import Path

from backend.services.certified_economic_news_snapshot_loader_v2 import (
    CertifiedEconomicNewsSnapshotLoaderV2,
)
from backend.services.certified_economic_news_snapshot_v2 import (
    CertifiedEconomicNewsSnapshotV2,
)
from backend.services.economic_news_runtime_provider_v2 import (
    EconomicNewsRuntimeProviderV2,
)


class CertifiedEconomicNewsDataLifecycleV2:
    """
    Atomic lifecycle for certified economic-news runtime data.

    Candidate snapshots are fully loaded and validated before
    replacing the active runtime state.

    Failed activation preserves the previous valid provider,
    snapshot, path, and runtime status.
    """

    STATUS_EMPTY = "EMPTY"
    STATUS_READY = "READY"
    STATUS_FAILED = "FAILED"

    def __init__(
        self,
        *,
        loader: (
            CertifiedEconomicNewsSnapshotLoaderV2 | None
        ) = None,
    ) -> None:
        self.loader = (
            loader
            if loader is not None
            else CertifiedEconomicNewsSnapshotLoaderV2()
        )

        if not isinstance(
            self.loader,
            CertifiedEconomicNewsSnapshotLoaderV2,
        ):
            raise TypeError(
                "loader must be "
                "CertifiedEconomicNewsSnapshotLoaderV2."
            )

        self._status = self.STATUS_EMPTY

        self._active_path: Path | None = None

        self._active_snapshot: (
            CertifiedEconomicNewsSnapshotV2 | None
        ) = None

        self._active_provider = (
            EconomicNewsRuntimeProviderV2(
                snapshot=None,
            )
        )

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
        elif not isinstance(
            file_path,
            Path,
        ):
            raise TypeError(
                "file_path debe ser str o Path."
            )

        path = Path(
            file_path
        ).expanduser()

        if (
            path.exists()
            and path.is_dir()
        ):
            raise IsADirectoryError(
                "La ruta certificada es un directorio: "
                f"{path}"
            )

        return path

    def get_status(
        self,
    ) -> str:
        return self._status

    def get_active_provider(
        self,
    ) -> EconomicNewsRuntimeProviderV2:
        return self._active_provider

    def get_active_snapshot(
        self,
    ) -> CertifiedEconomicNewsSnapshotV2 | None:
        return self._active_snapshot

    def get_active_path(
        self,
    ) -> Path | None:
        return self._active_path

    def get_last_activation_report(
        self,
    ) -> dict[str, object] | None:
        if self._last_activation_report is None:
            return None

        return dict(
            self._last_activation_report
        )

    def create_runtime_checkpoint(
        self,
    ) -> dict[str, object]:
        return {
            "status": self._status,
            "active_provider": self._active_provider,
            "active_snapshot": self._active_snapshot,
            "active_path": self._active_path,
            "last_activation_report": (
                None
                if self._last_activation_report is None
                else dict(
                    self._last_activation_report
                )
            ),
        }

    def restore_runtime_checkpoint(
        self,
        *,
        checkpoint: dict[str, object],
    ) -> None:
        if not isinstance(
            checkpoint,
            dict,
        ):
            raise TypeError(
                "checkpoint debe ser dict."
            )

        required = {
            "status",
            "active_provider",
            "active_snapshot",
            "active_path",
            "last_activation_report",
        }

        if set(checkpoint) != required:
            raise ValueError(
                "checkpoint de economic news inválido."
            )

        status = checkpoint["status"]
        provider = checkpoint["active_provider"]
        snapshot = checkpoint["active_snapshot"]
        active_path = checkpoint["active_path"]
        report = checkpoint[
            "last_activation_report"
        ]

        if status not in {
            self.STATUS_EMPTY,
            self.STATUS_READY,
            self.STATUS_FAILED,
        }:
            raise ValueError(
                "checkpoint status inválido."
            )

        if not isinstance(
            provider,
            EconomicNewsRuntimeProviderV2,
        ):
            raise TypeError(
                "checkpoint provider inválido."
            )

        if (
            snapshot is not None
            and not isinstance(
                snapshot,
                CertifiedEconomicNewsSnapshotV2,
            )
        ):
            raise TypeError(
                "checkpoint snapshot inválido."
            )

        if (
            active_path is not None
            and not isinstance(
                active_path,
                Path,
            )
        ):
            raise TypeError(
                "checkpoint active_path inválido."
            )

        if (
            report is not None
            and not isinstance(
                report,
                dict,
            )
        ):
            raise TypeError(
                "checkpoint report inválido."
            )

        self._status = status
        self._active_provider = provider
        self._active_snapshot = snapshot
        self._active_path = active_path
        self._last_activation_report = (
            None
            if report is None
            else dict(report)
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

        previous_provider = (
            self._active_provider
        )
        previous_snapshot = (
            self._active_snapshot
        )
        previous_path = (
            self._active_path
        )
        previous_status = (
            self._status
        )

        try:
            candidate_snapshot = (
                self.loader.load_from_file(
                    file_path=path,
                )
            )

            candidate_provider = (
                EconomicNewsRuntimeProviderV2(
                    snapshot=candidate_snapshot,
                )
            )

            report: dict[str, object] = {
                "success": True,
                "status": self.STATUS_READY,
                "started_at": started_at,
                "completed_at": self._utc_now(),
                "source": str(path),
                "snapshot_version": (
                    candidate_snapshot
                    .snapshot_version
                ),
                "coverage_start": (
                    candidate_snapshot
                    .coverage_start
                    .isoformat()
                ),
                "coverage_end": (
                    candidate_snapshot
                    .coverage_end
                    .isoformat()
                ),
                "high_impact_events": len(
                    candidate_snapshot
                    .high_impact_events
                ),
                "error": None,
            }

            self._active_provider = (
                candidate_provider
            )
            self._active_snapshot = (
                candidate_snapshot
            )
            self._active_path = path
            self._status = self.STATUS_READY
            self._last_activation_report = (
                report
            )

            return dict(report)

        except Exception as exc:
            self._active_provider = (
                previous_provider
            )
            self._active_snapshot = (
                previous_snapshot
            )
            self._active_path = (
                previous_path
            )
            self._status = (
                previous_status
            )

            report = {
                "success": False,
                "status": self.STATUS_FAILED,
                "started_at": started_at,
                "completed_at": self._utc_now(),
                "source": str(path),
                "snapshot_version": None,
                "coverage_start": None,
                "coverage_end": None,
                "high_impact_events": None,
                "error": {
                    "type": type(exc).__name__,
                    "message": str(exc),
                },
            }

            self._last_activation_report = (
                report
            )

            raise
