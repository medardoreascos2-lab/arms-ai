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


class ProcessedJob:

    job_id = "job-001"


class FakeWorker:

    def __init__(self):

        self.called = False

    def process_next(
        self,
    ):

        self.called = True

        return ProcessedJob()


def test_process_next_endpoint():

    manager = BacktestingJobManagerV2()

    queue = BacktestingJobQueueV2(
        job_manager=manager,
    )

    worker = FakeWorker()

    app = FastAPI()

    app.include_router(
        create_backtesting_jobs_router_v2(
            job_manager=manager,
            job_queue=queue,
            worker=worker,
        )
    )

    client = TestClient(app)

    response = client.post(
        "/api/v2/backtesting/jobs/process-next"
    )

    assert response.status_code == 200
    assert worker.called

    assert response.json() == {
        "processed": True,
        "job_id": "job-001",
    }
