from fastapi.testclient import TestClient

from backend.api.app import create_app


def test_metrics_route_is_registered():

    app = create_app()

    client = TestClient(app)

    response = client.get(
        "/openapi.json"
    )

    assert response.status_code == 200

    paths = response.json()["paths"]

    assert (
        "/api/v2/backtesting/metrics"
        in paths
    )


def test_metrics_endpoint_not_404():

    app = create_app()

    client = TestClient(app)

    response = client.get(
        "/api/v2/backtesting/metrics"
    )

    assert response.status_code != 404


def test_metrics_endpoint_structure():

    app = create_app()

    client = TestClient(app)

    response = client.get(
        "/api/v2/backtesting/metrics"
    )

    assert response.status_code == 200

    payload = response.json()

    assert "metrics" in payload
