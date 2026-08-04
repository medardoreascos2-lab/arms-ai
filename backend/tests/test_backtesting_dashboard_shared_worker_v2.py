from fastapi.testclient import TestClient

from backend.api.app import create_app


def test_dashboard_uses_shared_worker():

    app = create_app()

    worker = (
        app.state
        .backtesting_worker_v2
    )

    client = TestClient(app)

    response = client.get(
        "/api/v2/backtesting/dashboard"
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["worker"] == (
        worker.status()
    )


def test_dashboard_worker_status_structure():

    app = create_app()

    client = TestClient(app)

    response = client.get(
        "/api/v2/backtesting/dashboard"
    )

    assert response.status_code == 200

    worker = (
        response.json()["worker"]
    )

    assert "is_running" in worker
    assert "iterations" in worker
    assert "last_error" in worker
