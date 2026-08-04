from __future__ import annotations

from backend.backtesting.backtesting_job_manager_v2 import (
    BacktestingJobManagerV2,
)
from backend.backtesting.backtesting_job_queue_v2 import (
    BacktestingJobQueueV2,
)


class BacktestingControllerV2:
    """
    Coordina el estado y ciclo de vida del subsistema
    de procesamiento de backtesting.
    """

    def __init__(
        self,
        *,
        job_manager: BacktestingJobManagerV2,
        job_queue: BacktestingJobQueueV2,
        background_worker,
    ) -> None:

        if not isinstance(
            job_manager,
            BacktestingJobManagerV2,
        ):
            raise TypeError(
                "job_manager debe ser "
                "BacktestingJobManagerV2."
            )

        if not isinstance(
            job_queue,
            BacktestingJobQueueV2,
        ):
            raise TypeError(
                "job_queue debe ser "
                "BacktestingJobQueueV2."
            )

        if (
            job_queue.job_manager
            is not job_manager
        ):
            raise ValueError(
                "job_queue debe utilizar "
                "el mismo job_manager."
            )

        if (
            not callable(
                getattr(
                    background_worker,
                    "start",
                    None,
                )
            )
            or not callable(
                getattr(
                    background_worker,
                    "stop",
                    None,
                )
            )
        ):
            raise TypeError(
                "background_worker debe implementar "
                "start() y stop()."
            )

        self.job_manager = job_manager
        self.job_queue = job_queue
        self.background_worker = (
            background_worker
        )

    def start(
        self,
    ):

        return self.background_worker.start()

    def stop(
        self,
        *,
        timeout: float | None = None,
    ) -> None:

        self.background_worker.stop(
            timeout=timeout,
        )

    @property
    def is_running(
        self,
    ) -> bool:

        return bool(
            getattr(
                self.background_worker,
                "is_running",
                False,
            )
        )

    def status(
        self,
    ) -> dict:

        last_error = getattr(
            self.background_worker,
            "last_error",
            None,
        )

        return {
            "is_running": self.is_running,
            "registered_jobs": len(
                self.job_manager
            ),
            "pending_tasks": len(
                self.job_queue
            ),
            "iterations": int(
                getattr(
                    self.background_worker,
                    "iterations",
                    0,
                )
            ),
            "last_error": (
                str(last_error)
                if last_error is not None
                else None
            ),
        }
