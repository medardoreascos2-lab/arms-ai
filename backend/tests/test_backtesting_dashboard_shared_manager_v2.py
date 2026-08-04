from fastapi.testclient import TestClient

from backend.api.app import create_app


def test_dashboard_uses_shared_job_manager():

    app = create_app()

    manager = app.state.backtesting_job_manager_v2

    manager.create_job(job_id="pending")

    running = manager.create_job(job_id="running")
    running.start()

    completed = manager.create_job(job_id="completed")
    completed.start()
    completed.finish(
        report_directory="reports/completed",
    )

    failed = manager.create_job(job_id="failed")
    failed.start()
    failed.fail("failure")

    client = TestClient(app)

    response = client.get(
        "/api/v2/backtesting/dashboard"
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["jobs"] == {
        "registered": 4,
        "pending": 1,
        "running": 1,
        "completed": 1,
        "failed": 1,
    }
