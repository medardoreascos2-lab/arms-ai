from fastapi.testclient import TestClient

from backend.api.app import create_app
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


def test_app_exposes_shared_job_queue():

    app = create_app()

    assert (
        app.state.backtesting_job_queue_v2.job_manager
        is app.state.backtesting_job_manager_v2
    )


def test_created_job_is_enqueued_in_app():

    app = create_app()

    client = TestClient(app)

    response = client.post(
        "/api/v2/backtesting/jobs",
        json=valid_payload(),
    )

    assert response.status_code == 201

    task = (
        app.state
        .backtesting_job_queue_v2
        .peek()
    )

    assert isinstance(
        task,
        BacktestingJobTaskV2,
    )

    assert (
        task.job.job_id
        == response.json()["job_id"]
    )
