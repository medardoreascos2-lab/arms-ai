from fastapi.testclient import TestClient

from backend.api.app import create_app


def test_controller_routes_are_registered():

    app = create_app()

    client = TestClient(app)

    response = client.get(
        "/openapi.json"
    )

    assert response.status_code == 200

    paths = response.json()["paths"]

    assert (
        "/api/v2/backtesting/controller/status"
        in paths
    )

    assert (
        "/api/v2/backtesting/controller/start"
        in paths
    )

    assert (
        "/api/v2/backtesting/controller/stop"
        in paths
    )


def test_controller_status_endpoint_not_404():

    app = create_app()

    client = TestClient(app)

    response = client.get(
        "/api/v2/backtesting/controller/status"
    )

    assert response.status_code != 404


def test_controller_start_endpoint_not_404():

    app = create_app()

    client = TestClient(app)

    response = client.post(
        "/api/v2/backtesting/controller/start"
    )

    assert response.status_code != 404

    if response.status_code == 200:

        client.post(
            "/api/v2/backtesting/controller/stop"
        )


def test_controller_stop_endpoint_not_404():

    app = create_app()

    client = TestClient(app)

    response = client.post(
        "/api/v2/backtesting/controller/stop"
    )

    assert response.status_code != 404
