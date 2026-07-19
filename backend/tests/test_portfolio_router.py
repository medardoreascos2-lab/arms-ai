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
