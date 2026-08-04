from fastapi.testclient import TestClient

from backend.api.app import create_app


def test_app_exposes_shared_job_queue():

    app = create_app()

    assert hasattr(
        app.state,
        "backtesting_job_queue_v2",
    )

    assert (
        app.state.backtesting_job_queue_v2.job_manager
        is app.state.backtesting_job_manager_v2
    )


def test_created_job_is_enqueued_in_app():

    app = create_app()

    client = TestClient(app)

    response = client.post(
        "/api/v2/backtesting/jobs"
    )

    assert response.status_code == 201

    payload = response.json()

    assert len(
        app.state.backtesting_job_queue_v2
    ) == 1

    queued_job = (
        app.state
        .backtesting_job_queue_v2
        .peek()
    )

    assert queued_job is not None

    assert (
        queued_job.job_id
        == payload["job_id"]
    )
