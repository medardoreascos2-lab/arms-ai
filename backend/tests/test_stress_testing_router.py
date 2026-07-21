from fastapi.testclient import TestClient

from backend.api.app import create_app


def test_stress_testing_endpoint():
    client = TestClient(
        create_app()
    )

    response = client.post(
        "/portfolio/stress-test",
        json={
            "weights": {
                "AAPL": 0.6,
                "MSFT": 0.4,
            },
            "shocks": {
                "AAPL": -0.30,
                "MSFT": -0.10,
            },
            "initial_value": 1000.0,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["final_value"] == 780.0
    assert body["absolute_loss"] == -220.0
    assert body["percentage_loss"] == -0.22
    assert body["worst_asset"] == "AAPL"
    assert body["best_asset"] == "MSFT"
    assert "asset_impacts" in body


def test_stress_testing_rejects_invalid_weights():
    client = TestClient(
        create_app()
    )

    response = client.post(
        "/portfolio/stress-test",
        json={
            "weights": {
                "AAPL": 0.2,
                "MSFT": 0.2,
            },
            "shocks": {
                "AAPL": -0.30,
                "MSFT": -0.10,
            },
        },
    )

    assert response.status_code == 400
