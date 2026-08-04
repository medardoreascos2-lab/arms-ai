from __future__ import annotations

from threading import RLock
from uuid import uuid4

from backend.backtesting.backtesting_job_v2 import (
    BacktestingJobV2,
)


class BacktestingJobManagerV2:
    """
    Administra el ciclo de vida y almacenamiento
    en memoria de los trabajos de backtesting.
    """

    def __init__(self) -> None:

        self._jobs: dict[
            str,
            BacktestingJobV2,
        ] = {}

        self._lock = RLock()

    @staticmethod
    def _normalize_job_id(
        job_id,
    ) -> str:

        normalized_job_id = str(
            job_id
        ).strip()

        if not normalized_job_id:
            raise ValueError(
                "job_id no puede estar vacío."
            )

        return normalized_job_id

    def create_job(
        self,
        *,
        job_id: str | None = None,
    ) -> BacktestingJobV2:

        normalized_job_id = (
            self._normalize_job_id(
                job_id
            )
            if job_id is not None
            else str(
                uuid4()
            )
        )

        job = BacktestingJobV2(
            job_id=normalized_job_id,
        )

        self.register_job(
            job
        )

        return job

    def register_job(
        self,
        job: BacktestingJobV2,
    ) -> BacktestingJobV2:

        if not isinstance(
            job,
            BacktestingJobV2,
        ):
            raise TypeError(
                "job debe ser BacktestingJobV2."
            )

        with self._lock:

            if job.job_id in self._jobs:
                raise ValueError(
                    "Ya existe un job con "
                    f"job_id={job.job_id}."
                )

            self._jobs[
                job.job_id
            ] = job

        return job

    def get_job(
        self,
        job_id,
    ) -> BacktestingJobV2 | None:

        normalized_job_id = (
            self._normalize_job_id(
                job_id
            )
        )

        with self._lock:
            return self._jobs.get(
                normalized_job_id
            )

    def list_jobs(
        self,
    ) -> list[BacktestingJobV2]:

        with self._lock:
            return list(
                self._jobs.values()
            )

    def delete_job(
        self,
        job_id,
    ) -> BacktestingJobV2 | None:

        normalized_job_id = (
            self._normalize_job_id(
                job_id
            )
        )

        with self._lock:
            return self._jobs.pop(
                normalized_job_id,
                None,
            )

    def clear(
        self,
    ) -> None:

        with self._lock:
            self._jobs.clear()

    def __len__(
        self,
    ) -> int:

        with self._lock:
            return len(
                self._jobs
            )
