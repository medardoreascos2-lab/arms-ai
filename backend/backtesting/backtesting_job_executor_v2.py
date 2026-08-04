from __future__ import annotations

from pathlib import Path
from threading import RLock

from backend.backtesting.backtesting_job_v2 import (
    BacktestingJobStatusV2,
    BacktestingJobV2,
)


class BacktestingJobExecutorV2:
    """
    Ejecuta un trabajo de backtesting y administra
    sus transiciones de estado.
    """

    def __init__(
        self,
        *,
        orchestrator,
    ) -> None:

        if not callable(
            getattr(
                orchestrator,
                "run",
                None,
            )
        ):
            raise TypeError(
                "orchestrator debe implementar run()."
            )

        self.orchestrator = orchestrator

        self._results: dict[
            str,
            object,
        ] = {}

        self._lock = RLock()

    @staticmethod
    def _validate_job(
        job,
    ) -> BacktestingJobV2:

        if not isinstance(
            job,
            BacktestingJobV2,
        ):
            raise TypeError(
                "job debe ser BacktestingJobV2."
            )

        return job

    @staticmethod
    def _resolve_report_directory(
        *,
        result,
        output_directory,
    ) -> str:

        result_report_directory = getattr(
            result,
            "report_directory",
            None,
        )

        if result_report_directory is not None:
            normalized = str(
                result_report_directory
            ).strip()

            if normalized:
                return normalized

        return str(
            Path(output_directory)
        )

    def execute(
        self,
        *,
        job: BacktestingJobV2,
        candles,
        output_directory,
    ):

        normalized_job = self._validate_job(
            job
        )

        if (
            normalized_job.status
            != BacktestingJobStatusV2.PENDING
        ):
            raise ValueError(
                "Solo un job PENDING puede ejecutarse."
            )

        normalized_job.start()
        normalized_job.progress = 10.0

        try:
            result = self.orchestrator.run(
                candles=candles,
                output_directory=output_directory,
            )

            normalized_job.progress = 90.0

            report_directory = (
                self._resolve_report_directory(
                    result=result,
                    output_directory=(
                        output_directory
                    ),
                )
            )

            normalized_job.finish(
                report_directory=(
                    report_directory
                ),
            )

            with self._lock:
                self._results[
                    normalized_job.job_id
                ] = result

            return result

        except Exception as exc:
            normalized_job.fail(
                str(exc)
                or exc.__class__.__name__
            )

            raise

    def get_result(
        self,
        job_id,
    ):

        normalized_job_id = str(
            job_id
        ).strip()

        if not normalized_job_id:
            raise ValueError(
                "job_id no puede estar vacío."
            )

        with self._lock:
            return self._results.get(
                normalized_job_id
            )

    def delete_result(
        self,
        job_id,
    ):

        normalized_job_id = str(
            job_id
        ).strip()

        if not normalized_job_id:
            raise ValueError(
                "job_id no puede estar vacío."
            )

        with self._lock:
            return self._results.pop(
                normalized_job_id,
                None,
            )
