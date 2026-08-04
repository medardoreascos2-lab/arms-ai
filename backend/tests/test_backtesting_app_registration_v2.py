from fastapi.testclient import TestClient

from backend.api.app import create_app


def test_backtesting_jobs_router_registered():

    app = create_app()

    client = TestClient(app)

    response = client.get(
        "/openapi.json"
    )

    assert response.status_code == 200

    paths = response.json()["paths"]

    assert (
        "/api/v2/backtesting/jobs"
        in paths
    )


def test_backtesting_run_router_registered():

    app = create_app()

    client = TestClient(app)

    response = client.get(
        "/openapi.json"
    )

    assert response.status_code == 200

    paths = response.json()["paths"]

    assert (
        "/api/v2/backtesting/run"
        in paths
    )


def test_jobs_endpoint_not_404():

    app = create_app()

    client = TestClient(app)

    response = client.post(
        "/api/v2/backtesting/jobs"
    )

    assert response.status_code != 404


def test_backtesting_endpoint_not_404():

    app = create_app()

    client = TestClient(app)

    response = client.post(
        "/api/v2/backtesting/run",
        json={
            "candles": [],
        },
    )

    assert response.status_code != 404
