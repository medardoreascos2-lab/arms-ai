from __future__ import annotations

from threading import RLock

from backend.backtesting.backtesting_job_queue_v2 import (
    BacktestingJobQueueV2,
)
from backend.backtesting.backtesting_job_task_v2 import (
    BacktestingJobTaskV2,
)


class BacktestingWorkerV2:
    """
    Procesa BacktestingJobTaskV2 pendientes
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
        self._last_processed_task = None
        self._last_result = None

        self._lock = RLock()

    def process_next(
        self,
    ):

        task = self.queue.dequeue()

        if task is None:
            return None

        if not isinstance(
            task,
            BacktestingJobTaskV2,
        ):
            raise TypeError(
                "queue.dequeue() debe devolver "
                "BacktestingJobTaskV2."
            )

        try:
            result = self.executor.execute(
                job=task.job,
                candles=task.candles,
                output_directory=(
                    task.output_directory
                ),
            )

            with self._lock:
                self._processed_jobs += 1
                self._last_processed_job = task.job
                self._last_processed_task = task
                self._last_result = result

            return task.job

        except Exception:

            with self._lock:
                self._processed_jobs += 1
                self._last_processed_job = task.job
                self._last_processed_task = task
                self._last_result = None

            raise

    def process_all(
        self,
    ) -> list:

        processed_jobs = []

        while True:

            job = self.process_next()

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
    def last_processed_task(
        self,
    ):

        with self._lock:
            return self._last_processed_task

    @property
    def last_result(
        self,
    ):

        with self._lock:
            return self._last_result

    def status(
        self,
    ):
        """
        Estado operativo del worker
        para consumo del dashboard.
        """

        return {
            "is_running": getattr(
                self,
                "is_running",
                False,
            ),
            "iterations": getattr(
                self,
                "iterations",
                0,
            ),
            "last_error": getattr(
                self,
                "last_error",
                None,
            ),
        }
