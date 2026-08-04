from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum


class BacktestingJobStatusV2(str, Enum):
    """
    Estados posibles de un trabajo de backtesting.
    """

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class BacktestingJobV2:
    """
    Representa el ciclo de vida de un trabajo
    de backtesting.
    """

    def __init__(
        self,
        *,
        job_id: str,
    ) -> None:

        normalized_job_id = str(
            job_id
        ).strip()

        if not normalized_job_id:
            raise ValueError(
                "job_id no puede estar vacío."
            )

        self.job_id = normalized_job_id

        self.status = (
            BacktestingJobStatusV2.PENDING
        )

        self._progress = 0.0

        self.created_at = (
            datetime.now(timezone.utc)
        )

        self.started_at = None
        self.finished_at = None

        self.error_message = None
        self.report_directory = None

    @property
    def progress(
        self,
    ) -> float:

        return self._progress

    @progress.setter
    def progress(
        self,
        value,
    ) -> None:

        normalized_value = float(
            value
        )

        if not 0.0 <= normalized_value <= 100.0:
            raise ValueError(
                "progress debe estar entre 0 y 100."
            )

        self._progress = normalized_value

    def start(
        self,
    ) -> None:

        if self.status not in {
            BacktestingJobStatusV2.PENDING,
        }:
            raise ValueError(
                "Solo un job PENDING puede iniciar."
            )

        self.status = (
            BacktestingJobStatusV2.RUNNING
        )

        self.started_at = (
            datetime.now(timezone.utc)
        )

        self.error_message = None

    def finish(
        self,
        *,
        report_directory: str,
    ) -> None:

        if self.status not in {
            BacktestingJobStatusV2.RUNNING,
            BacktestingJobStatusV2.PENDING,
        }:
            raise ValueError(
                "El job no puede finalizar "
                "desde su estado actual."
            )

        normalized_report_directory = str(
            report_directory
        ).strip()

        if not normalized_report_directory:
            raise ValueError(
                "report_directory no puede estar vacío."
            )

        self.status = (
            BacktestingJobStatusV2.COMPLETED
        )

        self.progress = 100.0

        self.report_directory = (
            normalized_report_directory
        )

        self.finished_at = (
            datetime.now(timezone.utc)
        )

        self.error_message = None

    def fail(
        self,
        error_message: str,
    ) -> None:

        normalized_error_message = str(
            error_message
        ).strip()

        if not normalized_error_message:
            raise ValueError(
                "error_message no puede estar vacío."
            )

        self.status = (
            BacktestingJobStatusV2.FAILED
        )

        self.error_message = (
            normalized_error_message
        )

        self.finished_at = (
            datetime.now(timezone.utc)
        )

    def cancel(
        self,
    ) -> None:

        if self.status in {
            BacktestingJobStatusV2.COMPLETED,
            BacktestingJobStatusV2.FAILED,
            BacktestingJobStatusV2.CANCELLED,
        }:
            raise ValueError(
                "El job no puede cancelarse "
                "desde su estado actual."
            )

        self.status = (
            BacktestingJobStatusV2.CANCELLED
        )

        self.finished_at = (
            datetime.now(timezone.utc)
        )

    @staticmethod
    def _serialize_datetime(
        value,
    ):

        if value is None:
            return None

        return value.isoformat()

    def to_dict(
        self,
    ) -> dict:

        return {
            "job_id": self.job_id,
            "status": self.status.value,
            "progress": self.progress,
            "created_at": (
                self._serialize_datetime(
                    self.created_at
                )
            ),
            "started_at": (
                self._serialize_datetime(
                    self.started_at
                )
            ),
            "finished_at": (
                self._serialize_datetime(
                    self.finished_at
                )
            ),
            "error_message": (
                self.error_message
            ),
            "report_directory": (
                self.report_directory
            ),
        }
