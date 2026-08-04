from __future__ import annotations

from threading import RLock

from backend.backtesting.backtesting_job_queue_v2 import (
    BacktestingJobQueueV2,
)


class BacktestingWorkerV2:
    """
    Worker síncrono que procesa jobs pendientes
    desde BacktestingJobQueueV2.
    """

    def __init__(
        self,
        *,
        queue: BacktestingJobQueueV2,
        executor,
    ) -> None:

        if not isinstance(
            queue,
            BacktestingJobQueueV2,
        ):
            raise TypeError(
                "queue debe ser "
                "BacktestingJobQueueV2."
            )

        if not callable(
            getattr(
                executor,
                "execute",
                None,
            )
        ):
            raise TypeError(
                "executor debe implementar execute()."
            )

        self.queue = queue
        self.executor = executor

        self._processed_jobs = 0
        self._last_processed_job = None
        self._last_result = None

        self._lock = RLock()

    def process_next(
        self,
        *,
        candles,
        output_directory,
    ):

        job = self.queue.dequeue()

        if job is None:
            return None

        try:
            result = self.executor.execute(
                job=job,
                candles=candles,
                output_directory=output_directory,
            )

            with self._lock:
                self._processed_jobs += 1
                self._last_processed_job = job
                self._last_result = result

            return job

        except Exception:

            with self._lock:
                self._processed_jobs += 1
                self._last_processed_job = job
                self._last_result = None

            raise

    def process_all(
        self,
        *,
        candles,
        output_directory,
    ) -> list:

        processed_jobs = []

        while True:

            job = self.process_next(
                candles=candles,
                output_directory=output_directory,
            )

            if job is None:
                break

            processed_jobs.append(
                job
            )

        return processed_jobs

    @property
    def processed_jobs(
        self,
    ) -> int:

        with self._lock:
            return self._processed_jobs

    @property
    def last_processed_job(
        self,
    ):

        with self._lock:
            return self._last_processed_job

    @property
    def last_result(
        self,
    ):

        with self._lock:
            return self._last_result
