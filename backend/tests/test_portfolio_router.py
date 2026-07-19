from fastapi.testclient import TestClient

from backend.api.app import create_app


def build_payload():
    return {
        "returns": {
            "A": [0.01, 0.02, 0.03, 0.04],
            "B": [0.02, 0.01, 0.03, 0.05],
            "C": [0.03, 0.01, 0.02, 0.04],
        },
        "volatilities": {
            "A": 0.10,
            "B": 0.20,
            "C": 0.30,
        },
        "expected_returns": {
            "A": 0.08,
            "B": 0.12,
            "C": 0.18,
        },
        "risk_free_rate": 0.02,
    }


def test_post_analyze_returns_200():
    client = TestClient(
        create_app()
    )

    response = client.post(
        "/portfolio/analyze",
        json=build_payload(),
    )

    assert response.status_code == 200


def test_post_analyze_returns_strategy():
    client = TestClient(
        create_app()
    )

    response = client.post(
        "/portfolio/analyze",
        json=build_payload(),
    )

    payload = response.json()

    assert payload["strategy"]
    assert payload["risk_level"]
    assert "target_weights" in payload


def test_invalid_request_returns_422():
    client = TestClient(
        create_app()
    )

    response = client.post(
        "/portfolio/analyze",
        json={},
    )

    assert response.status_code == 422


def test_post_optimize_returns_200():
    client = TestClient(
        create_app()
    )

    response = client.post(
        "/portfolio/optimize",
        json=build_payload(),
    )

    assert response.status_code == 200


def test_post_optimize_returns_all_strategies():
    client = TestClient(
        create_app()
    )

    response = client.post(
        "/portfolio/optimize",
        json=build_payload(),
    )

    payload = response.json()

    assert "minimum_variance" in payload
    assert "maximum_sharpe" in payload
    assert "risk_parity" in payload
    assert payload["selected_strategy"]


def test_post_optimize_rejects_invalid_request():
    client = TestClient(
        create_app()
    )

    response = client.post(
        "/portfolio/optimize",
        json={},
    )

    assert response.status_code == 422


def test_post_rebalance_returns_200():
    client = TestClient(
        create_app()
    )

    response = client.post(
        "/portfolio/rebalance",
        json={
            "current_weights": {
                "A": 50.0,
                "B": 30.0,
                "C": 20.0,
            },
            "target_weights": {
                "A": 40.0,
                "B": 40.0,
                "C": 20.0,
            },
        },
    )

    assert response.status_code == 200


def test_post_rebalance_returns_trades():
    client = TestClient(
        create_app()
    )

    response = client.post(
        "/portfolio/rebalance",
        json={
            "current_weights": {
                "A": 50.0,
                "B": 30.0,
                "C": 20.0,
            },
            "target_weights": {
                "A": 40.0,
                "B": 40.0,
                "C": 20.0,
            },
        },
    )

    payload = response.json()

    assert payload["turnover"] == 10.0
    assert payload["trades"]["A"] == -10.0
    assert payload["trades"]["B"] == 10.0


def test_post_rebalance_rejects_invalid_request():
    client = TestClient(
        create_app()
    )

    response = client.post(
        "/portfolio/rebalance",
        json={},
    )

    assert response.status_code == 422
