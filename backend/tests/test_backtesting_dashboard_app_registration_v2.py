from fastapi.testclient import TestClient

from backend.api.app import create_app


def test_dashboard_route_is_registered():

    app = create_app()

    client = TestClient(app)

    response = client.get(
        "/openapi.json"
    )

    assert response.status_code == 200

    paths = response.json()["paths"]

    assert (
        "/api/v2/backtesting/dashboard"
        in paths
    )


def test_dashboard_endpoint_not_404():

    app = create_app()

    client = TestClient(app)

    response = client.get(
        "/api/v2/backtesting/dashboard"
    )

    assert response.status_code != 404


def test_dashboard_uses_shared_controller():

    app = create_app()

    client = TestClient(app)

    response = client.get(
        "/api/v2/backtesting/dashboard"
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload == {
        "controller": (
            app.state
            .backtesting_controller_v2
            .status()
        ),
        "jobs": {
            "registered": 0,
            "pending": 0,
            "running": 0,
            "completed": 0,
            "failed": 0,
        },
        "queue": {
            "pending_tasks": 0,
        },
    }
