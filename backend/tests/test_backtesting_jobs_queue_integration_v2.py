from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routers.backtesting_jobs_api_v2 import (
    create_backtesting_jobs_router_v2,
)
from backend.backtesting.backtesting_job_manager_v2 import (
    BacktestingJobManagerV2,
)
from backend.backtesting.backtesting_job_queue_v2 import (
    BacktestingJobQueueV2,
)


def build_client():

    manager = BacktestingJobManagerV2()

    queue = BacktestingJobQueueV2(
        job_manager=manager,
    )

    app = FastAPI()

    app.include_router(
        create_backtesting_jobs_router_v2(
            job_manager=manager,
            job_queue=queue,
        )
    )

    return (
        TestClient(app),
        manager,
        queue,
    )


def test_new_job_is_enqueued():

    client, manager, queue = build_client()

    response = client.post(
        "/api/v2/backtesting/jobs"
    )

    assert response.status_code == 201

    payload = response.json()

    job = manager.get_job(
        payload["job_id"]
    )

    assert job is not None

    assert len(queue) == 1

    queued = queue.dequeue()

    assert queued.job_id == job.job_id
