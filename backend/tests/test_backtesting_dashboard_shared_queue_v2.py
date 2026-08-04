from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.backtesting.backtesting_job_task_v2 import (
    BacktestingJobTaskV2,
)


def test_dashboard_uses_shared_job_queue():

    app = create_app()

    manager = (
        app.state
        .backtesting_job_manager_v2
    )

    queue = (
        app.state
        .backtesting_job_queue_v2
    )

    job = manager.create_job(
        job_id="queued-job",
    )

    task = BacktestingJobTaskV2(
        job=job,
        candles=[
            object(),
        ],
        output_directory=(
            "reports/queued-job"
        ),
    )

    queue.enqueue(
        task
    )

    client = TestClient(app)

    response = client.get(
        "/api/v2/backtesting/dashboard"
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["queue"] == {
        "pending_tasks": 1,
    }

    assert (
        payload["controller"]
        ["pending_tasks"]
        == 1
    )


def test_dashboard_queue_starts_empty():

    app = create_app()

    client = TestClient(app)

    response = client.get(
        "/api/v2/backtesting/dashboard"
    )

    assert response.status_code == 200

    assert response.json()["queue"] == {
        "pending_tasks": 0,
    }
