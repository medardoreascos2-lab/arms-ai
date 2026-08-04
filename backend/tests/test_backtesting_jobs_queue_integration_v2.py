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
from backend.backtesting.backtesting_job_task_v2 import (
    BacktestingJobTaskV2,
)


def valid_payload():

    return {
        "candles": [
            {
                "symbol": "NQ",
                "timeframe": "5m",
                "timestamp": (
                    "2026-08-04T09:30:00Z"
                ),
                "open": 21000.0,
                "high": 21010.0,
                "low": 20995.0,
                "close": 21005.0,
                "volume": 1000.0,
            },
        ],
        "output_directory": "reports/test",
    }


def test_new_job_is_enqueued():

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

    client = TestClient(app)

    response = client.post(
        "/api/v2/backtesting/jobs",
        json=valid_payload(),
    )

    assert response.status_code == 201

    task = queue.dequeue()

    assert isinstance(
        task,
        BacktestingJobTaskV2,
    )

    assert (
        task.job.job_id
        == response.json()["job_id"]
    )

    assert task.candle_count == 1
    assert task.output_directory == "reports/test"
