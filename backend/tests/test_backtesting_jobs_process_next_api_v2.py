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


class FakeWorker:

    def __init__(self):

        self.called = False

    def process_next(
        self,
        *,
        candles,
        output_directory,
    ):

        self.called = True

        return None


def build_client():

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

    return (
        TestClient(app),
        worker,
    )


def test_process_next_endpoint():

    client, worker = build_client()

    response = client.post(
        "/api/v2/backtesting/jobs/process-next"
    )

    assert response.status_code == 200

    assert worker.called

    assert response.json() == {
        "processed": True,
    }
