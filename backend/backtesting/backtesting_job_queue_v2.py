from __future__ import annotations

from collections import deque
from threading import RLock

from backend.backtesting.backtesting_job_manager_v2 import (
    BacktestingJobManagerV2,
)
from backend.backtesting.backtesting_job_task_v2 import (
    BacktestingJobTaskV2,
)
from backend.backtesting.backtesting_job_v2 import (
    BacktestingJobStatusV2,
)


class BacktestingJobQueueV2:
    """
    Cola FIFO segura para trabajos de backtesting.
    """

    def __init__(
        self,
        *,
        job_manager: BacktestingJobManagerV2,
    ) -> None:

        if not isinstance(
            job_manager,
            BacktestingJobManagerV2,
        ):
            raise TypeError(
                "job_manager debe ser "
                "BacktestingJobManagerV2."
            )

        self.job_manager = job_manager

        self._queue: deque[
            BacktestingJobTaskV2
        ] = deque()

        self._queued_job_ids: set[str] = set()

        self._lock = RLock()

    def enqueue(
        self,
        task: BacktestingJobTaskV2,
    ) -> BacktestingJobTaskV2:

        if not isinstance(
            task,
            BacktestingJobTaskV2,
        ):
            raise TypeError(
                "task debe ser BacktestingJobTaskV2."
            )

        job = task.job

        if (
            job.status
            != BacktestingJobStatusV2.PENDING
        ):
            raise ValueError(
                "Solo un job PENDING puede "
                "entrar en la cola."
            )

        registered_job = (
            self.job_manager.get_job(
                job.job_id
            )
        )

        if registered_job is not job:
            raise ValueError(
                "El job debe estar registrado "
                "en job_manager."
            )

        with self._lock:

            if (
                job.job_id
                in self._queued_job_ids
            ):
                raise ValueError(
                    "El job ya está en la cola."
                )

            self._queue.append(
                task
            )

            self._queued_job_ids.add(
                job.job_id
            )

        return task

    def dequeue(
        self,
    ) -> BacktestingJobTaskV2 | None:

        with self._lock:

            if not self._queue:
                return None

            job = self._queue.popleft()

            self._queued_job_ids.discard(
                job.job.job_id
            )

            return job

    def peek(
        self,
    ) -> BacktestingJobTaskV2 | None:

        with self._lock:

            if not self._queue:
                return None

            return self._queue[0]

    def remove(
        self,
        job_id,
    ) -> BacktestingJobTaskV2 | None:

        normalized_job_id = str(
            job_id
        ).strip()

        if not normalized_job_id:
            raise ValueError(
                "job_id no puede estar vacío."
            )

        with self._lock:

            for task in self._queue:

                if (
                    task.job.job_id
                    == normalized_job_id
                ):
                    self._queue.remove(
                        task
                    )

                    self._queued_job_ids.discard(
                        normalized_job_id
                    )

                    return task

        return None

    def contains(
        self,
        job_id,
    ) -> bool:

        normalized_job_id = str(
            job_id
        ).strip()

        if not normalized_job_id:
            raise ValueError(
                "job_id no puede estar vacío."
            )

        with self._lock:
            return (
                normalized_job_id
                in self._queued_job_ids
            )

    def clear(
        self,
    ) -> None:

        with self._lock:
            self._queue.clear()
            self._queued_job_ids.clear()

    def __len__(
        self,
    ) -> int:

        with self._lock:
            return len(
                self._queue
            )
