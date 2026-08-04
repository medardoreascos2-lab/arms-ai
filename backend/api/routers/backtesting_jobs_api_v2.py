from __future__ import annotations

from fastapi import (
    APIRouter,
    HTTPException,
    status,
)

from backend.backtesting.backtesting_job_manager_v2 import (
    BacktestingJobManagerV2,
)


def create_backtesting_jobs_router_v2(
    *,
    job_manager: BacktestingJobManagerV2,
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

    router = APIRouter(
        prefix="/api/v2/backtesting/jobs",
        tags=["backtesting-jobs-v2"],
    )

    @router.post(
        "",
        status_code=status.HTTP_201_CREATED,
    )
    def create_job():

        job = job_manager.create_job()

        return job.to_dict()

    @router.get("")
    def list_jobs():

        return [
            job.to_dict()
            for job in job_manager.list_jobs()
        ]

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
