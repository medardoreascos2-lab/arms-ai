from __future__ import annotations

from fastapi import (
    APIRouter,
    HTTPException,
    status,
)

from backend.api.schemas.backtesting import (
    BacktestingRunRequest,
)
from backend.backtesting.backtesting_job_manager_v2 import (
    BacktestingJobManagerV2,
)
from backend.backtesting.backtesting_job_queue_v2 import (
    BacktestingJobQueueV2,
)
from backend.backtesting.backtesting_job_task_v2 import (
    BacktestingJobTaskV2,
)
from backend.models.candle import Candle


def create_backtesting_jobs_router_v2(
    *,
    job_manager: BacktestingJobManagerV2,
    job_queue: BacktestingJobQueueV2 | None = None,
    worker=None,
) -> APIRouter:
    """
    Router REST para administrar trabajos de Backtesting.
    """

    if not isinstance(
        job_manager,
        BacktestingJobManagerV2,
    ):
        raise TypeError(
            "job_manager debe ser BacktestingJobManagerV2."
        )

    if (
        job_queue is not None
        and not isinstance(
            job_queue,
            BacktestingJobQueueV2,
        )
    ):
        raise TypeError(
            "job_queue debe ser "
            "BacktestingJobQueueV2."
        )

    if (
        job_queue is not None
        and job_queue.job_manager
        is not job_manager
    ):
        raise ValueError(
            "job_queue debe utilizar "
            "el mismo job_manager."
        )

    if (
        worker is not None
        and not callable(
            getattr(
                worker,
                "process_next",
                None,
            )
        )
    ):
        raise TypeError(
            "worker debe implementar process_next()."
        )

    router = APIRouter(
        prefix="/api/v2/backtesting/jobs",
        tags=["backtesting-jobs-v2"],
    )

    @router.post(
        "",
        status_code=status.HTTP_201_CREATED,
    )
    def create_job(
        request: BacktestingRunRequest,
    ):

        job = job_manager.create_job()

        try:
            candles = [
                Candle(
                    symbol=candle.symbol,
                    timeframe=candle.timeframe,
                    timestamp=candle.timestamp,
                    open=candle.open,
                    high=candle.high,
                    low=candle.low,
                    close=candle.close,
                    volume=candle.volume,
                )
                for candle in request.candles
            ]

            task = BacktestingJobTaskV2(
                job=job,
                candles=candles,
                output_directory=(
                    request.output_directory
                ),
            )

            if job_queue is not None:
                job_queue.enqueue(
                    task
                )

        except Exception:
            job_manager.delete_job(
                job.job_id
            )
            raise

        payload = job.to_dict()

        payload["task"] = task.to_dict()

        return payload

    @router.get("")
    def list_jobs():

        return [
            job.to_dict()
            for job in job_manager.list_jobs()
        ]

    @router.post("/process-next")
    def process_next_job():

        if worker is None:
            raise HTTPException(
                status_code=503,
                detail=(
                    "backtesting_worker_not_configured"
                ),
            )

        processed_job = worker.process_next()

        return {
            "processed": (
                processed_job is not None
            ),
            "job_id": (
                processed_job.job_id
                if processed_job is not None
                else None
            ),
        }

    @router.get("/{job_id}")
    def get_job(
        job_id: str,
    ):

        job = job_manager.get_job(
            job_id
        )

        if job is None:
            raise HTTPException(
                status_code=404,
                detail="job_not_found",
            )

        return job.to_dict()

    @router.delete("/{job_id}")
    def delete_job(
        job_id: str,
    ):

        if job_queue is not None:
            job_queue.remove(
                job_id
            )

        job = job_manager.delete_job(
            job_id
        )

        if job is None:
            raise HTTPException(
                status_code=404,
                detail="job_not_found",
            )

        return {
            "deleted": True,
            "job_id": job.job_id,
        }

    return router
