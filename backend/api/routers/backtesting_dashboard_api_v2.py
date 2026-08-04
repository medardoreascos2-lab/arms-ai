from __future__ import annotations

from fastapi import APIRouter

from backend.backtesting.backtesting_job_manager_v2 import (
    BacktestingJobManagerV2,
)
from backend.backtesting.backtesting_job_v2 import (
    BacktestingJobStatusV2,
)


def create_backtesting_dashboard_router_v2(
    *,
    controller,
    job_manager: BacktestingJobManagerV2 | None = None,
) -> APIRouter:
    """
    Router REST para exponer un resumen operativo
    del subsistema de backtesting.
    """

    if not callable(
        getattr(
            controller,
            "status",
            None,
        )
    ):
        raise TypeError(
            "controller debe implementar status()."
        )

    if (
        job_manager is not None
        and not isinstance(
            job_manager,
            BacktestingJobManagerV2,
        )
    ):
        raise TypeError(
            "job_manager debe ser "
            "BacktestingJobManagerV2."
        )

    router = APIRouter(
        prefix="/api/v2/backtesting",
        tags=[
            "backtesting-dashboard-v2",
        ],
    )

    @router.get("/dashboard")
    def get_dashboard():

        payload = {
            "controller": (
                controller.status()
            ),
        }

        if job_manager is not None:

            jobs = job_manager.list_jobs()

            counts = {
                "registered": len(jobs),
                "pending": 0,
                "running": 0,
                "completed": 0,
                "failed": 0,
            }

            for job in jobs:

                if (
                    job.status
                    == BacktestingJobStatusV2.PENDING
                ):
                    counts["pending"] += 1

                elif (
                    job.status
                    == BacktestingJobStatusV2.RUNNING
                ):
                    counts["running"] += 1

                elif (
                    job.status
                    == BacktestingJobStatusV2.COMPLETED
                ):
                    counts["completed"] += 1

                elif (
                    job.status
                    == BacktestingJobStatusV2.FAILED
                ):
                    counts["failed"] += 1

            payload["jobs"] = counts

        return payload

    return router
